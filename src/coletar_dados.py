"""
Coleta dos dados do projeto: inadimplência e endividamento das famílias.

1. Baixa os zips anuais do SCR.data (Banco Central) e lê cada CSV mensal
   direto de dentro do zip, sem descompactar.
2. Mantém só pessoas físicas (PF) e salva um Parquet por mês.
3. Baixa as séries complementares do SGS (juros, Selic, IPCA, inadimplência).

Requisitos: pip install pandas pyarrow requests
"""
import io
import time
import zipfile
from pathlib import Path

import random

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ANOS = [2025, 2026]
PASTA = Path(__file__).resolve().parents[1] / "dados"  # funciona rodando de qualquer pasta
URL_SCR = "https://www.bcb.gov.br/pda/desig/scrdata_{ano}.zip"
URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

# Prevenção de derrubadas: o servidor do BCB costuma cortar downloads longos
# ou muitas requisições seguidas. Estes parâmetros controlam a "gentileza".
TENTATIVAS = 10            # tentativas por arquivo antes de desistir
ESPERA_BASE = 5            # segundos de espera após a 1ª falha
ESPERA_MAXIMA = 120        # teto da espera entre tentativas
PAUSA_ENTRE_ARQUIVOS = 15  # respiro entre um zip anual e o próximo
PAUSA_ENTRE_SERIES = 2     # respiro entre chamadas à API do SGS
TAMANHO_BLOCO = 256 * 1024 # leitura em blocos menores = menos dado perdido na queda

COLUNAS = [
    "data_base", "uf", "segmento", "cliente", "cnae_ocupacao", "porte",
    "modalidade", "submodalidade", "origem", "indexador", "numero_de_operacoes",
    "carteira_a_vencer", "vencido_de_15_ate_90_dias", "vencido_acima_de_90_dias",
    "carteira_vencida", "carteira_ativa", "carteira_inadimplencia", "ativo_problematico",
]

SERIES_SGS = {
    20740: "juros_credito_livre_pf",
    432: "selic_meta",
    433: "ipca_mensal",
    21112: "inadimplencia_credito_livre_pf",
    21129: "inadimplencia_cartao_pf",
    29037: "endividamento_familias",
    29038: "endividamento_exceto_habitacional",
    29034: "comprometimento_renda",
    29035: "comprometimento_renda_exceto_habitacional",
}


def criar_sessao() -> requests.Session:
    """Sessão reaproveitável: mantém a conexão aberta (menos handshakes) e
    repete sozinha requisições que voltam com erro temporário do servidor
    (429 = muitas requisições, 5xx = instabilidade), respeitando o
    cabeçalho Retry-After quando o servidor pede para esperar."""
    sessao = requests.Session()
    sessao.headers.update({"User-Agent": "Mozilla/5.0 (projeto academico EBAC)"})
    retry = Retry(
        total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"], respect_retry_after_header=True,
    )
    sessao.mount("https://", HTTPAdapter(max_retries=retry))
    return sessao


SESSAO = criar_sessao()


def esperar(tentativa: int) -> None:
    """Backoff exponencial com variação aleatória: 5 s, 10 s, 20 s, 40 s...
    até o teto. A variação evita bater no servidor sempre no mesmo ritmo."""
    segundos = min(ESPERA_MAXIMA, ESPERA_BASE * 2 ** (tentativa - 1))
    segundos *= random.uniform(0.8, 1.2)
    print(f"  aguardando {segundos:.0f} s antes de tentar de novo...")
    time.sleep(segundos)


def zip_valido(caminho: Path) -> bool:
    try:
        with zipfile.ZipFile(caminho) as z:
            return any(n.lower().endswith(".csv") for n in z.namelist())
    except zipfile.BadZipFile:
        return False


def baixar_zip(ano: int, tentativas: int = TENTATIVAS) -> Path:
    """Baixa o zip do ano retomando de onde parou se a conexão cair.

    O download vai para um arquivo .part e só vira .zip depois de completo
    e validado, então um download interrompido nunca é confundido com pronto.
    """
    url = URL_SCR.format(ano=ano)
    destino = PASTA / "zips" / f"scrdata_{ano}.zip"
    parcial = destino.with_suffix(".zip.part")
    destino.parent.mkdir(parents=True, exist_ok=True)

    if destino.exists():
        if zip_valido(destino):
            print(f"{destino.name} já baixado")
            return destino
        print(f"{destino.name} está incompleto ou corrompido; baixando de novo")
        destino.rename(parcial)  # aproveita o que já veio

    for tentativa in range(1, tentativas + 1):
        ja_baixado = parcial.stat().st_size if parcial.exists() else 0
        cabecalhos = {}
        if ja_baixado:
            cabecalhos["Range"] = f"bytes={ja_baixado}-"
        try:
            with SESSAO.get(url, headers=cabecalhos, stream=True, timeout=(15, 60)) as r:
                if r.status_code == 416:  # nada mais a baixar
                    break
                r.raise_for_status()
                if ja_baixado and r.status_code != 206:
                    ja_baixado = 0  # servidor ignorou o Range: recomeça
                total = ja_baixado + int(r.headers.get("Content-Length", 0))
                modo = "ab" if ja_baixado else "wb"
                with open(parcial, modo) as f:
                    for bloco in r.iter_content(chunk_size=TAMANHO_BLOCO):
                        f.write(bloco)
                        ja_baixado += len(bloco)
                        if total:
                            print(f"\r  {url.rsplit('/', 1)[-1]}: {ja_baixado / 1e6:,.0f} de "
                                  f"{total / 1e6:,.0f} MB", end="")
            print()
            break
        except (requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            print(f"\n  Conexão caiu (tentativa {tentativa}/{tentativas}): {type(e).__name__}")
            esperar(tentativa)
    else:
        raise RuntimeError(f"Não consegui baixar {url} depois de {tentativas} tentativas")

    if not zip_valido(parcial):
        raise RuntimeError(f"{parcial.name} baixou, mas o zip não abre. Apague-o e rode de novo.")
    parcial.rename(destino)
    return destino


def ler_csv_mensal(arquivo) -> pd.DataFrame:
    """Lê um CSV do SCR.data em blocos, mantendo só PF (economiza memória)."""
    partes = []
    for bloco in pd.read_csv(
        arquivo, sep=";", decimal=",", encoding="utf-8-sig",
        usecols=COLUNAS, dtype={"numero_de_operacoes": str}, chunksize=200_000,
    ):
        partes.append(bloco[bloco["cliente"] == "PF"])
    df = pd.concat(partes, ignore_index=True)
    df["data_base"] = pd.to_datetime(df["data_base"])
    # -1 = número de operações suprimido; vira ausente para não entrar em somas
    df["numero_de_operacoes"] = pd.to_numeric(df["numero_de_operacoes"]).where(lambda s: s >= 0)
    for c in ["uf", "segmento", "cnae_ocupacao", "porte", "modalidade",
              "submodalidade", "origem", "indexador"]:
        df[c] = df[c].astype("category")
    return df.drop(columns="cliente")


def processar_zip(caminho_zip: Path) -> None:
    saida = PASTA / "scr_pf"
    saida.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(caminho_zip) as z:
        csvs = sorted(n for n in z.namelist() if n.lower().endswith(".csv"))
        print(f"{caminho_zip.name}: {len(csvs)} arquivos mensais")
        for nome in csvs:
            alvo = saida / (Path(nome).stem + ".parquet")
            if alvo.exists():
                continue
            with z.open(nome) as f:
                df = ler_csv_mensal(io.TextIOWrapper(f, encoding="utf-8-sig"))
            df.to_parquet(alvo, index=False)
            print(f"  {nome} -> {alvo.name} ({len(df):,} linhas PF)")


def baixar_sgs(inicio="01/01/2024", fim="31/12/2026") -> pd.DataFrame:
    series = []
    for codigo, nome in SERIES_SGS.items():
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                r = SESSAO.get(URL_SGS.format(codigo=codigo),
                               params={"formato": "json", "dataInicial": inicio, "dataFinal": fim},
                               timeout=(15, 60))
                r.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                print(f"  SGS {codigo} falhou (tentativa {tentativa}/{TENTATIVAS}): {type(e).__name__}")
                if tentativa == TENTATIVAS:
                    raise
                esperar(tentativa)
        time.sleep(PAUSA_ENTRE_SERIES)
        s = pd.DataFrame(r.json())
        s["data"] = pd.to_datetime(s["data"], dayfirst=True)
        s["valor"] = pd.to_numeric(s["valor"])
        # Selic é diária: fica o último valor de cada mês
        s = s.set_index("data")["valor"].resample("ME").last().rename(nome)
        series.append(s)
        print(f"SGS {codigo} ({nome}): {s.notna().sum()} meses")
    sgs = pd.concat(series, axis=1)
    sgs.to_parquet(PASTA / "sgs.parquet")
    return sgs


if __name__ == "__main__":
    PASTA.mkdir(exist_ok=True)
    for i, ano in enumerate(ANOS):
        if i:
            print(f"Pausa de {PAUSA_ENTRE_ARQUIVOS} s antes do próximo arquivo...")
            time.sleep(PAUSA_ENTRE_ARQUIVOS)
        processar_zip(baixar_zip(ano))
    baixar_sgs()
    pf = pd.read_parquet(PASTA / "scr_pf")
    print(f"\nTotal: {len(pf):,} linhas PF, de {pf.data_base.min():%m/%Y} a {pf.data_base.max():%m/%Y}")
