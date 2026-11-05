"""
Gera as bases agregadas (CSVs leves) usadas pelo Looker Studio e pelo
dashboard em Dash. Os Parquets brutos ficam fora do Git; só estes
agregados entram no repositório.

Uso: python src/gerar_bases.py
Saída: dados/agregados/*.csv
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import transformacao as t  # noqa: E402

SAIDA = t.PASTA_DADOS / "agregados"

# Escopo analítico de cada grupo de produto. "Consumo" é o foco do projeto
# (endividamento das famílias); rural é crédito à produção, e o saldo não
# migrado de cartão é um estoque legado com inadimplência ~80%.
ESCOPO_SQL = """
CASE
  WHEN grupo_produto = 'Rural' THEN 'Rural'
  WHEN grupo_produto = 'Cartão: saldo não migrado (legado)' THEN 'Legado'
  ELSE 'Consumo e habitação'
END
"""

METRICAS = """
    ROUND(SUM(carteira_ativa) / 1e6, 3)           AS carteira_ativa_mi,
    ROUND(SUM(carteira_inadimplencia) / 1e6, 3)   AS carteira_inadimplida_mi,
    ROUND(SUM(vencido_acima_de_90_dias) / 1e6, 3) AS vencido_90d_mi
"""


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    con = t.conectar()

    bases = {
        # Tabela-fato do Looker: mês × UF × produto × renda
        "fato_credito_pf": f"""
            SELECT mes, uf, regiao, grupo_produto, {ESCOPO_SQL} AS escopo, renda, {METRICAS}
            FROM pf GROUP BY ALL ORDER BY mes, uf, grupo_produto, renda""",
        "ocupacao_mes": f"""
            SELECT mes, ocupacao, grupo_produto, {ESCOPO_SQL} AS escopo, {METRICAS}
            FROM pf GROUP BY ALL ORDER BY mes, ocupacao, grupo_produto""",
        "segmento_mes": f"""
            SELECT mes, segmento, grupo_produto, {ESCOPO_SQL} AS escopo, {METRICAS}
            FROM pf GROUP BY ALL ORDER BY mes, segmento, grupo_produto""",
    }
    for nome, sql in bases.items():
        df = con.sql(sql).df()
        df.to_csv(SAIDA / f"{nome}.csv", index=False, encoding="utf-8")
        print(f"{nome}.csv: {len(df):,} linhas")

    # Série nacional: taxas do SCR.data + séries do SGS, uma linha por mês
    nac = con.sql(f"""
        SELECT mes,
            100 * SUM(carteira_inadimplencia) / SUM(carteira_ativa) AS inad_scr_total,
            100 * SUM(carteira_inadimplencia) FILTER (WHERE {ESCOPO_SQL} = 'Consumo e habitação')
                / SUM(carteira_ativa) FILTER (WHERE {ESCOPO_SQL} = 'Consumo e habitação') AS inad_scr_consumo,
            -- mesmo recorte da série oficial 21112 (crédito livre), para validar o cálculo
            100 * SUM(carteira_inadimplencia) FILTER (WHERE origem = 'Sem destinação específica')
                / SUM(carteira_ativa) FILTER (WHERE origem = 'Sem destinação específica') AS inad_scr_livre,
            SUM(carteira_ativa) / 1e9 AS carteira_ativa_bi
        FROM pf GROUP BY mes ORDER BY mes""").df().set_index("mes")
    nac.index = nac.index.astype("datetime64[ns]")
    sgs = t.ler_sgs(ate=nac.index.max())
    nac = nac.join(sgs).round(4)
    nac.index.name = "mes"
    nac.to_csv(SAIDA / "serie_nacional.csv", encoding="utf-8")
    print(f"serie_nacional.csv: {len(nac)} meses")


if __name__ == "__main__":
    main()
