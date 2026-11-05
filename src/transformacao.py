"""
Transformações compartilhadas pelo notebook de EDA, pela geração das bases
do Looker Studio e pelo dashboard em Dash.

Mantém num só lugar:
- o agrupamento das ~50 submodalidades do SCR.data em grupos de produto;
- o mapeamento UF -> região;
- a ordem das faixas de renda;
- o cálculo da taxa de inadimplência.
"""
from pathlib import Path

import duckdb
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PASTA_DADOS = RAIZ / "dados"

REGIOES = {
    "Norte": ["AC", "AM", "AP", "PA", "RO", "RR", "TO"],
    "Nordeste": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
    "Centro-Oeste": ["DF", "GO", "MS", "MT"],
    "Sudeste": ["ES", "MG", "RJ", "SP"],
    "Sul": ["PR", "RS", "SC"],
}
UF_REGIAO = {uf: reg for reg, ufs in REGIOES.items() for uf in ufs}

ORDEM_RENDA = [
    "Sem rendimento", "Até 1 salário mínimo", "Mais de 1 a 2 salários mínimos",
    "Mais de 2 a 3 salários mínimos", "Mais de 3 a 5 salários mínimos",
    "Mais de 5 a 10 salários mínimos", "Mais de 10 a 20 salários mínimos",
    "Acima de 20 salários mínimos", "Indisponível",
]
RENDA_CURTA = {
    "Sem rendimento": "Sem renda", "Até 1 salário mínimo": "Até 1 SM",
    "Mais de 1 a 2 salários mínimos": "1 a 2 SM", "Mais de 2 a 3 salários mínimos": "2 a 3 SM",
    "Mais de 3 a 5 salários mínimos": "3 a 5 SM", "Mais de 5 a 10 salários mínimos": "5 a 10 SM",
    "Mais de 10 a 20 salários mínimos": "10 a 20 SM", "Acima de 20 salários mínimos": "Acima de 20 SM",
    "Indisponível": "Indisponível",
}

# Grupo de produto em SQL (CASE), aplicado sobre modalidade/submodalidade.
# A ordem dos WHEN importa: o primeiro que casar vence.
GRUPO_PRODUTO_SQL = """
CASE
  WHEN submodalidade = 'Cartão de crédito - não migrado' THEN 'Cartão: saldo não migrado (legado)'
  WHEN submodalidade = 'Crédito rotativo vinculado a cartão de crédito' THEN 'Cartão: rotativo'
  WHEN submodalidade LIKE 'Cartão de crédito - compra à vista%' THEN 'Cartão: à vista e parcelado lojista'
  WHEN submodalidade LIKE 'Cartão de crédito - compra%' THEN 'Cartão: parcelado pelo emissor e saque'
  WHEN submodalidade = 'Cheque especial' THEN 'Cheque especial'
  WHEN submodalidade LIKE 'Crédito pessoal - com consignação%' THEN 'Crédito pessoal consignado'
  WHEN submodalidade LIKE 'Crédito pessoal - sem consignação%' THEN 'Crédito pessoal não consignado'
  WHEN submodalidade IN ('Aquisição de bens - veículos automotores',
                         'Arrendamento financeiro de veículos automotores') THEN 'Veículos'
  WHEN modalidade = 'Financiamentos imobiliários' THEN 'Habitacional'
  WHEN submodalidade = 'Home Equity' THEN 'Home equity'
  WHEN modalidade LIKE 'Financiamentos rurais%' OR submodalidade = 'Financiamentos agroindustriais' THEN 'Rural'
  ELSE 'Outros'
END
"""

GRUPOS_CAROS = [
    "Cartão: rotativo", "Cheque especial", "Cartão: parcelado pelo emissor e saque",
    "Crédito pessoal não consignado",
]


def conectar(pasta_scr: Path = PASTA_DADOS / "scr_pf") -> duckdb.DuckDBPyConnection:
    """Abre o DuckDB com a view `pf` (PF tratado) sobre todos os Parquets mensais."""
    con = duckdb.connect()
    ufs = ", ".join(f"('{uf}', '{reg}')" for uf, reg in UF_REGIAO.items())
    con.sql(f"CREATE TEMP TABLE uf_regiao(uf VARCHAR, regiao VARCHAR); INSERT INTO uf_regiao VALUES {ufs}")
    con.sql(f"""
        CREATE VIEW pf AS
        SELECT
            CAST(s.data_base AS DATE)              AS mes,
            s.uf, r.regiao,
            CAST(s.segmento AS VARCHAR)            AS segmento,
            CAST(s.cnae_ocupacao AS VARCHAR)       AS ocupacao,
            CAST(s.porte AS VARCHAR)               AS renda,
            CAST(s.modalidade AS VARCHAR)          AS modalidade,
            CAST(s.submodalidade AS VARCHAR)       AS submodalidade,
            CAST(s.origem AS VARCHAR)              AS origem,
            {GRUPO_PRODUTO_SQL} AS grupo_produto,
            s.carteira_ativa, s.carteira_inadimplencia,
            s.vencido_de_15_ate_90_dias, s.vencido_acima_de_90_dias, s.ativo_problematico
        FROM read_parquet('{pasta_scr.as_posix()}/*.parquet') s
        JOIN uf_regiao r USING (uf)
    """)
    return con


def taxa(df: pd.DataFrame, num: str = "carteira_inadimplencia", den: str = "carteira_ativa") -> pd.Series:
    """Taxa de inadimplência em %: soma do numerador ÷ soma do denominador."""
    return 100 * df[num] / df[den]


def ler_sgs(caminho: Path = PASTA_DADOS / "sgs.parquet", ate=None) -> pd.DataFrame:
    sgs = pd.read_parquet(caminho)
    sgs.index = pd.to_datetime(sgs.index).normalize()
    if ate is not None:
        sgs = sgs.loc[:ate]
    return sgs
