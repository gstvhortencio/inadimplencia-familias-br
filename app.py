"""
Dashboard: inadimplência e endividamento das famílias brasileiras.

Lê apenas as bases agregadas em dados/agregados (geradas por src/gerar_bases.py),
então roda leve em qualquer servidor gratuito.

Local:   python app.py            -> http://127.0.0.1:8050
Render:  gunicorn app:server      (ver render.yaml)
"""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html

RAIZ = Path(__file__).resolve().parent
AGG = RAIZ / "dados" / "agregados"

# ---------------------------------------------------------------- dados
fato = pd.read_csv(AGG / "fato_credito_pf.csv", parse_dates=["mes"])
ocup = pd.read_csv(AGG / "ocupacao_mes.csv", parse_dates=["mes"])
seg = pd.read_csv(AGG / "segmento_mes.csv", parse_dates=["mes"])
nac = pd.read_csv(AGG / "serie_nacional.csv", parse_dates=["mes"]).set_index("mes")
# colunas de texto como categoria: corta a memória pela metade (o plano grátis do Render tem 512 MB)
for _df in (fato, ocup, seg):
    for _c in [c for c in _df.columns if pd.api.types.is_string_dtype(_df[c])]:
        _df[_c] = _df[_c].astype("category")
GEO = json.loads((RAIZ / "assets" / "br_uf.geojson").read_text(encoding="utf-8"))

MESES = sorted(fato["mes"].unique())
MES_INICIAL, MES_FINAL = MESES[0], MESES[-1]
REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]
ORDEM_RENDA = [
    "Até 1 salário mínimo", "Mais de 1 a 2 salários mínimos",
    "Mais de 2 a 3 salários mínimos", "Mais de 3 a 5 salários mínimos",
    "Mais de 5 a 10 salários mínimos", "Mais de 10 a 20 salários mínimos",
    "Acima de 20 salários mínimos",
    # grupos à parte, fora da escada de renda: vão para o fim do gráfico
    "Sem rendimento", "Indisponível",
]
RENDA_CURTA = {  # explícito: não depende da ordem de ORDEM_RENDA
    "Sem rendimento": "Sem renda", "Até 1 salário mínimo": "Até 1 SM",
    "Mais de 1 a 2 salários mínimos": "1 a 2 SM", "Mais de 2 a 3 salários mínimos": "2 a 3 SM",
    "Mais de 3 a 5 salários mínimos": "3 a 5 SM", "Mais de 5 a 10 salários mínimos": "5 a 10 SM",
    "Mais de 10 a 20 salários mínimos": "10 a 20 SM", "Acima de 20 salários mínimos": "Acima de 20 SM",
    "Indisponível": "Indisponível",
}
ESCOPOS = {
    "consumo": ("Famílias: consumo e habitação", ["Consumo e habitação"]),
    "sem_legado": ("Famílias + produtores rurais (pessoa física)", ["Consumo e habitação", "Rural"]),
    "tudo": ("Famílias + produtores rurais + saldo legado de cartão",
             ["Consumo e habitação", "Rural", "Legado"]),
}

# ---------------------------------------------------------------- estilo
AZUL, LARANJA, CINZA, CINZA_CLARO = "#2a78d6", "#eb6834", "#a8a69d", "#d9d7cf"
TEXTO, TEXTO_2, GRADE, FUNDO = "#0b0b0b", "#52514e", "#ebeae6", "#fcfcfb"
SEQ_AZUL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

LAYOUT_BASE = dict(
    font=dict(family="Inter, system-ui, sans-serif", size=13, color=TEXTO),
    paper_bgcolor=FUNDO, plot_bgcolor=FUNDO,
    separators=",.",  # vírgula decimal e ponto de milhar (padrão brasileiro)
    margin=dict(l=10, r=20, t=10, b=10),
    hoverlabel=dict(bgcolor="white", bordercolor=GRADE, font=dict(size=13, color=TEXTO)),
    xaxis=dict(gridcolor=GRADE, zeroline=False, linecolor=GRADE, tickfont=dict(color=TEXTO_2)),
    yaxis=dict(gridcolor=GRADE, zeroline=False, linecolor=GRADE, tickfont=dict(color=TEXTO_2)),
    legend=dict(orientation="h", y=1.08, x=0, font=dict(color=TEXTO_2)),
)


_BORDA = "1px solid #e2e0d9"
_ABA_BASE = {"borderLeft": _BORDA, "borderRight": _BORDA, "borderBottom": _BORDA,
             "padding": "10px"}
ABA = dict(
    style={**_ABA_BASE, "borderTop": _BORDA, "background": "#efeee9", "color": "#52514e",
           "fontWeight": 500},
    selected_style={**_ABA_BASE, "borderTop": f"3px solid {AZUL}", "background": "#fcfcfb",
                    "color": "#0b0b0b", "fontWeight": 600},
)


def estilo(fig: go.Figure, altura: int = 380, **extra) -> go.Figure:
    fig.update_layout(**{**LAYOUT_BASE, "height": altura})
    fig.update_layout(**extra)  # sobrescreve o padrão quando necessário
    return fig


def fmt_mes(m) -> str:
    nomes = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    m = pd.Timestamp(m)
    return f"{nomes[m.month - 1]}/{m.year}"


def br(x: float, casas: int = 1) -> str:
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------- cálculos
def filtrar(df: pd.DataFrame, escopo: str, regioes) -> pd.DataFrame:
    d = df[df["escopo"].isin(ESCOPOS[escopo][1])]
    if regioes and "regiao" in d.columns:
        d = d[d["regiao"].isin(regioes)]
    return d


def taxa_por(df: pd.DataFrame, chaves) -> pd.DataFrame:
    g = df.groupby(chaves, as_index=False, observed=True)[["carteira_ativa_mi", "carteira_inadimplida_mi"]].sum()
    for c in chaves:  # categorias voltam a texto para ordenar e rotular sem surpresas
        if isinstance(g[c].dtype, pd.CategoricalDtype):
            g[c] = g[c].astype(str)
    g["taxa"] = 100 * g["carteira_inadimplida_mi"] / g["carteira_ativa_mi"]
    return g


def ipca_acumulado(ate) -> float:
    """IPCA acumulado do mês seguinte ao inicial até `ate` (para deflacionar saldos)."""
    s = nac["ipca_mensal"].loc[MES_INICIAL:ate].iloc[1:]
    return float((1 + s / 100).prod() - 1)


# ---------------------------------------------------------------- componentes
def kpi(titulo, valor, detalhe, id_=None):
    ids = lambda sufixo: {"id": f"{id_}-{sufixo}"} if id_ else {}  # noqa: E731
    return html.Div(className="kpi", children=[
        html.Div(titulo, className="kpi-titulo"),
        html.Div(valor, className="kpi-valor", **ids("valor")),
        html.Div(detalhe, className="kpi-detalhe", **ids("detalhe")),
    ])


def como_ler(itens):
    """Quadro de instruções de leitura de um gráfico (estilo embutido: não depende do CSS)."""
    caixa = {"background": "#f4f7fb", "border": "1px solid #dde7f4", "borderRadius": "8px",
             "padding": "10px 14px 4px", "margin": "4px 0 10px"}
    titulo = {"fontSize": "11.5px", "fontWeight": 700, "textTransform": "uppercase",
              "letterSpacing": ".05em", "color": AZUL, "marginBottom": "4px"}
    item = {"fontSize": "13.5px", "lineHeight": "1.5", "marginBottom": "3px"}
    return html.Div(className="como-ler", style=caixa, children=[
        html.Div("Como ler", style=titulo),
        html.Ul(style={"margin": "0 0 6px", "paddingLeft": "18px"},
                children=[html.Li(dcc.Markdown(i, className="md-inline", style={"display": "inline"}),
                                  style=item) for i in itens]),
    ])


def cartao(titulo, subtitulo, grafico_id, nota=None, leitura=None):
    filhos = [html.H3(titulo), html.P(subtitulo, className="sub")]
    if leitura:
        filhos.append(como_ler(leitura))
    filhos.append(dcc.Graph(id=grafico_id, config={"displayModeBar": False}))
    if nota:
        filhos.append(html.P(nota, className="nota", id=f"{grafico_id}-nota"))
    return html.Div(className="cartao", children=filhos)


# ---------------------------------------------------------------- números da página inicial
def _taxa_mes(df, escopos, mes):
    d = df[(df["escopo"].isin(escopos)) & (df["mes"] == mes)]
    return 100 * d["carteira_inadimplida_mi"].sum() / d["carteira_ativa_mi"].sum()


T_CONS_INI = _taxa_mes(fato, ["Consumo e habitação"], MES_INICIAL)
T_CONS_FIM = _taxa_mes(fato, ["Consumo e habitação"], MES_FINAL)
T_TOT_INI = _taxa_mes(fato, ["Consumo e habitação", "Rural", "Legado"], MES_INICIAL)
T_TOT_FIM = _taxa_mes(fato, ["Consumo e habitação", "Rural", "Legado"], MES_FINAL)
_cons_fim = fato[(fato["escopo"] == "Consumo e habitação") & (fato["mes"] == MES_FINAL)]
CART_CONS_TRI = _cons_fim["carteira_ativa_mi"].sum() / 1e6
INAD_CONS_BI = _cons_fim["carteira_inadimplida_mi"].sum() / 1e3

_hab = fato[(fato["grupo_produto"] == "Habitacional") & (fato["mes"] == MES_FINAL)]
HAB_TRI = _hab["carteira_ativa_mi"].sum() / 1e6
HAB_TAXA = 100 * _hab["carteira_inadimplida_mi"].sum() / _hab["carteira_ativa_mi"].sum()
T_SEMLEG_INI = _taxa_mes(fato, ["Consumo e habitação", "Rural"], MES_INICIAL)
T_SEMLEG_FIM = _taxa_mes(fato, ["Consumo e habitação", "Rural"], MES_FINAL)
_aum = fato.groupby(["escopo", "mes"], observed=True)["carteira_inadimplida_mi"].sum().unstack()
_aum = (_aum[MES_FINAL] - _aum[MES_INICIAL])
AUM_TOTAL_BI = _aum.sum() / 1e3
AUM_RURAL_BI = _aum["Rural"] / 1e3
AUM_LEGADO_BI = _aum["Legado"] / 1e3
PART_RURAL = 100 * _aum["Rural"] / _aum.sum()
PART_LEGADO = 100 * _aum["Legado"] / _aum.sum()

_serie_cons = (fato[fato["escopo"] == "Consumo e habitação"]
               .groupby("mes")[["carteira_ativa_mi", "carteira_inadimplida_mi"]].sum())
_serie_cons = 100 * _serie_cons["carteira_inadimplida_mi"] / _serie_cons["carteira_ativa_mi"]
_jur = nac["juros_credito_livre_pf"].reindex(_serie_cons.index)
CORR_NIVEL = _serie_cons.corr(_jur)
CORR_VAR = _serie_cons.diff().corr(_jur.diff())
VAR_INAD_FIM = 100 * (_serie_cons.iloc[-1] / _serie_cons.iloc[0] - 1)
VAR_JUR_FIM = 100 * (_jur.iloc[-1] / _jur.iloc[0] - 1)
SELIC_PICO = nac["selic_meta"].loc[:MES_FINAL].max()
SELIC_FIM = nac["selic_meta"].loc[MES_FINAL]


md_ = lambda t: dcc.Markdown(t, className="md")  # noqa: E731
_valid = nac[["inad_scr_livre", "inadimplencia_credito_livre_pf"]].dropna()
CORR_VALID = _valid["inad_scr_livre"].corr(_valid["inadimplencia_credito_livre_pf"])
CORR_VAR_VALID = _valid["inad_scr_livre"].diff().corr(_valid["inadimplencia_credito_livre_pf"].diff())
_dif = (_valid["inad_scr_livre"] - _valid["inadimplencia_credito_livre_pf"]).abs()
DIF_MEDIA = _dif.mean()
DIF_FIM = _dif.iloc[-1]
# período em que as séries praticamente coincidem: até o mês anterior à primeira diferença >= 0,2 p.p.
_inicio_div = _dif[_dif.ge(0.2)].index.min() if _dif.ge(0.2).any() else None
_colado = _dif[_dif.index < _inicio_div] if _inicio_div is not None else _dif
MES_COLADO = _colado.index.max()
DIF_MAX_COLADO = _colado.max()
N_LINHAS_MI = "3,9"  # linhas PF no período (ver notebooks/01_limpeza_e_preparacao.ipynb)


def figura_validacao() -> go.Figure:
    rot = [fmt_mes(m) for m in _valid.index]
    fig = go.Figure()
    fig.add_scatter(x=rot, y=_valid["inad_scr_livre"], name="Nosso cálculo (SCR.data, só crédito livre)",
                    mode="lines+markers", line=dict(color=AZUL, width=2), marker=dict(size=6),
                    hovertemplate="%{y:.2f}%<extra>nosso cálculo</extra>")
    fig.add_scatter(x=rot, y=_valid["inadimplencia_credito_livre_pf"],
                    name="Taxa oficial do Banco Central (crédito livre)", mode="lines",
                    line=dict(color=CINZA, width=2),
                    hovertemplate="%{y:.2f}%<extra>oficial</extra>")
    estilo(fig, 320, yaxis_ticksuffix="%", yaxis_rangemode="tozero", hovermode="x unified",
           xaxis_type="category")
    return fig


def figura_indices() -> go.Figure:
    """Variação % de cada série desde o primeiro mês, num eixo só.

    Taxa de inadimplência (~4%) e juros (~60% a.a.) têm escalas muito diferentes; comparar a
    variação relativa de cada uma desde o início coloca as duas na mesma régua sem eixo duplo."""
    var_inad = 100 * (_serie_cons / _serie_cons.iloc[0] - 1)
    var_jur = 100 * (_jur / _jur.iloc[0] - 1)
    rot = [fmt_mes(m) for m in _serie_cons.index]
    fig = go.Figure()
    fig.add_scatter(
        x=rot, y=var_inad, name="Inadimplência (consumo e habitação)", mode="lines+markers",
        line=dict(color=AZUL, width=2), marker=dict(size=6),
        customdata=[br(v, 2) for v in _serie_cons],
        hovertemplate="%{customdata}% da carteira em atraso (%{y:+.0f}% desde o início)"
                      "<extra>inadimplência</extra>")
    fig.add_scatter(
        x=rot, y=var_jur, name="Juros médios cobrados das famílias", mode="lines",
        line=dict(color=CINZA, width=2, dash="dot"),
        customdata=[[br(v, 1), br(100 * ((1 + v / 100) ** (1 / 12) - 1), 1)] for v in _jur],
        hovertemplate="%{customdata[0]}% ao ano, ≈ %{customdata[1]}% ao mês "
                      "(%{y:+.0f}% desde o início)<extra>juros</extra>")
    fig.add_hline(y=0, line=dict(color=CINZA, width=1))
    estilo(fig, 320, hovermode="x unified", xaxis_type="category", yaxis_ticksuffix="%",
           yaxis_title=f"Variação desde {fmt_mes(MES_INICIAL)}")
    return fig


def tabela(cabecalho, linhas, larguras=None):
    """Tabela com espaçamento embutido (não depende do CSS externo)."""
    borda = "1px solid #e2e0d9"
    th = {"textAlign": "left", "padding": "10px 16px", "borderBottom": f"2px solid {CINZA_CLARO}",
          "color": TEXTO_2, "fontSize": "12.5px", "fontWeight": 600, "textTransform": "uppercase",
          "letterSpacing": ".03em", "verticalAlign": "bottom"}
    td = {"padding": "12px 16px", "borderBottom": borda, "verticalAlign": "top",
          "fontSize": "14px", "lineHeight": "1.5"}
    larguras = larguras or [None] * len(cabecalho)
    return html.Table(
        style={"width": "100%", "borderCollapse": "collapse", "margin": "6px 0 14px"},
        children=[
            html.Thead(html.Tr([html.Th(c, style={**th, **({"width": w} if w else {})})
                                for c, w in zip(cabecalho, larguras)])),
            html.Tbody([html.Tr([html.Td(c, style=td) for c in linha]) for linha in linhas]),
        ])


def _faixa(ini, fim):
    """Taxa inicial → final numa linha só."""
    return html.Span(f"{br(ini, 2)}% → {br(fim, 2)}%", style={"whiteSpace": "nowrap"})


def topico(titulo, *filhos):
    return html.Div(className="cartao texto", children=[html.H3(titulo), *filhos])


def pagina_inicial():
    md = lambda t: dcc.Markdown(t, className="md")  # noqa: E731
    return html.Div(className="inicio", children=[
        topico("Sobre este painel",
               md(f"""
As famílias brasileiras nunca deveram tanto: a dívida com bancos equivale a
**{br(ultimo['endividamento_familias'])}% da renda de um ano**, e **{br(ultimo['comprometimento_renda'])}%
da renda do mês** vai para juros e parcelas ({fmt_mes(mes_endiv)}). Com {len(MESES)} meses de dados
públicos do Banco Central, este painel mostra **onde, com quem e em qual tipo de crédito** os atrasos
estão crescendo. Os filtros do topo valem para todas as abas.
""")),
        topico("O que os dados mostram",
               md(f"""
1. **A inadimplência subiu de {br(T_CONS_INI, 2)}% para {br(T_CONS_FIM, 2)}%** no crédito de consumo e
   habitação, sem nenhum mês de alívio relevante.
2. **O rotativo do cartão é o epicentro:** 21% de inadimplência, quase o dobro do início. Cheque
   especial e cartão parcelado vêm logo atrás.
3. **Renda baixa e variável concentram o risco:** quem ganha até 1 salário mínimo atrasa cerca de
   três vezes mais que quem ganha de 10 a 20. Autônomos e MEIs estão acima da média.
4. **Fintechs e financeiras cresceram e pioraram juntas:** as fintechs dobraram a carteira e a
   inadimplência foi de 11% para 21%.
5. **O Norte lidera; a Paraíba tem a segunda menor taxa do país** e a menor alta.
""")),
        html.Div(children=[
            topico("O que é a taxa de inadimplência",
                   md(f"""
É a **parte do dinheiro emprestado que está há mais de 90 dias sem pagamento**: de cada R$ 100
devidos, R$ {br(T_CONS_FIM, 2)} estão em atraso ({fmt_mes(MES_FINAL)}).

- **Mede dinheiro, não pessoas.** Para contar gente há outras pesquisas: a Serasa aponta
  84,2 milhões de pessoas com alguma conta atrasada, incluindo água e luz, e a CNC, 29,8% das famílias.
  As maiores dívidas (imóvel, consignado) são as que menos atrasam, por isso a fatia em reais é menor.
- Fica abaixo da taxa oficial do **crédito livre** (comparada na aba *Fontes e método*) porque
  inclui o financiamento imobiliário, um crédito enorme e com pouco atraso.
""")),
            topico("Os três escopos do filtro",
                   md(f"""
O filtro **Escopo do crédito** define quais empréstimos entram na conta. O painel abre nas famílias;
as outras duas opções servem de comparação (taxas de {fmt_mes(MES_INICIAL)} → {fmt_mes(MES_FINAL)}):

- **Famílias: consumo e habitação** ({br(T_CONS_INI, 2)}% → {br(T_CONS_FIM, 2)}%): cartão, cheque especial,
  crédito pessoal, consignado, veículos e imóveis.
- **+ produtores rurais** ({br(T_SEMLEG_INI, 2)}% → {br(T_SEMLEG_FIM, 2)}%): crédito que o produtor toma no
  próprio CPF para plantar, colher e comprar máquinas. Não é orçamento de família e passou por uma
  crise própria do agro, responsável por R$ {br(AUM_RURAL_BI, 0)} bi do aumento do saldo em atraso.
- **+ saldo legado de cartão** ({br(T_TOT_INI, 2)}% → {br(T_TOT_FIM, 2)}%): dívidas antigas de cartão que
  não foram reclassificadas nas categorias atuais ("não migrado"), quase 80% em atraso. Mais
  R$ {br(AUM_LEGADO_BI, 0)} bi do aumento.
""")),
        ]),
        topico("Os números do topo medem coisas diferentes",
               tabela(["Indicador", "Conta", "Leitura"], [
                   [html.Strong("Dívida total × renda do ano"), "saldo devedor ÷ renda de 12 meses",
                    f"Quem ganha R$ 100 mil por ano deve R$ {br(ultimo['endividamento_familias'], 1)} mil, "
                    "boa parte em financiamento de imóvel."],
                   [html.Strong("Renda do mês que vai para dívidas"), "juros + parcelas ÷ renda do mês",
                    f"De cada R$ 100 recebidos, R$ {br(ultimo['comprometimento_renda'], 0)} pagam dívidas."],
                   [html.Strong("Dívida em atraso"), "atraso acima de 90 dias ÷ total emprestado",
                    f"De cada R$ 100 emprestados, R$ {br(T_CONS_FIM, 2)} estão em atraso."],
               ], larguras=["26%", "30%", "44%"]),
               md("""
Juntos: as famílias devem muito, pagam muito todo mês e a maioria consegue pagar, mas a fatia que
não consegue está crescendo. Os dois primeiros são números nacionais do Banco Central e não mudam
com os filtros.
""")),
        topico("Juros e inadimplência: correlação não é causa",
               md(f"""
O gráfico mostra quanto cada série variou desde {fmt_mes(MES_INICIAL)} (zero = ponto de partida).
As duas sobem juntas, com correlação de **{br(CORR_NIVEL, 2)}**. Mas duas séries que só sobem sempre
parecem ligadas. Mês a mês, a relação cai para **{br(CORR_VAR, 2)}**, e a inadimplência seguiu subindo
mesmo com a Selic já em queda. **Com {len(MESES)} meses, não dá para afirmar que os juros antecipam a
inadimplência.** Teste outras defasagens na aba Evolução.
"""),
               dcc.Graph(figure=figura_indices(), config={"displayModeBar": False})),
    ])


app = Dash(__name__, title="Inadimplência das famílias · Brasil")
server = app.server  # usado pelo gunicorn no Render

ultimo = nac.dropna(subset=["endividamento_familias"]).iloc[-1]
mes_endiv = nac.dropna(subset=["endividamento_familias"]).index[-1]

app.layout = html.Div(className="pagina", children=[
    html.Header([
        html.H1("Inadimplência das famílias brasileiras"),
        html.P(f"Crédito a pessoas físicas no SCR.data (Banco Central), {fmt_mes(MES_INICIAL)} a "
               f"{fmt_mes(MES_FINAL)}, com séries do SGS. Projeto de parceria EBAC × Semantix.",
               className="sub"),
    ]),

    html.Div(className="filtros", children=[
        html.Div([html.Label("Escopo do crédito"),
                  dcc.Dropdown(id="f-escopo", value="consumo", clearable=False, searchable=False,
                               options=[{"label": v[0], "value": k} for k, v in ESCOPOS.items()])]),
        html.Div([html.Label("Região"),
                  dcc.Dropdown(id="f-regiao", multi=True, placeholder="Brasil inteiro", searchable=False,
                               options=REGIOES)]),
        html.Div([html.Label("Mês de referência"),
                  dcc.Dropdown(id="f-mes", value=str(MES_FINAL.date()), clearable=False, searchable=False,
                               options=[{"label": fmt_mes(m), "value": str(pd.Timestamp(m).date())}
                                        for m in reversed(MESES)])]),
    ]),

    html.Div(className="kpis", children=[
        kpi("Dívida em atraso (inadimplência)", "", "", "k-taxa"),
        kpi("Variação desde " + fmt_mes(MES_INICIAL), "", "", "k-var"),
        kpi("Total emprestado (escopo do filtro)", "", "", "k-cart"),
        kpi("Dívida total × renda do ano", f"{br(ultimo['endividamento_familias'])}%",
            f"quem ganha R$ 100 mil por ano deve, em média, R$ {br(ultimo['endividamento_familias'], 1)} mil "
            f"· Brasil, {fmt_mes(mes_endiv)}"),
        kpi("Renda do mês que vai para dívidas", f"{br(ultimo['comprometimento_renda'])}%",
            f"de cada R$ 100 recebidos, R$ {br(ultimo['comprometimento_renda'], 0)} pagam juros e parcelas "
            f"· Brasil, {fmt_mes(mes_endiv)}"),
    ]),

    dcc.Tabs(className="abas", value="inicio", children=[
        dcc.Tab(**ABA, label="Comece aqui", value="inicio", children=[pagina_inicial()]),
        dcc.Tab(**ABA, label="Evolução", children=[
            html.Div(className="duas iguais", children=[
                topico("SCR.data: de onde vem a inadimplência",
                       dcc.Markdown(f"""
O **SCR** (Sistema de Informações de Crédito) é o cadastro em que bancos, financeiras, fintechs e
cooperativas registram todo empréstimo acima de R$ 200. O **SCR.data** é a versão aberta dessa base,
publicada todo mês pelo Banco Central **sem identificar ninguém**: cada linha soma os saldos de muitas
operações parecidas (mesmo estado, produto, faixa de renda, ocupação e tipo de instituição).

É dele que vêm quase todos os gráficos deste painel. Ele cobre **todo** o crédito às pessoas
físicas, cerca de R$ {br(fato.loc[fato.mes == MES_FINAL, 'carteira_ativa_mi'].sum() / 1e6, 1)} trilhões
em {fmt_mes(MES_FINAL)}, e permite abrir a inadimplência por qualquer um desses recortes. O gráfico
abaixo mostra a taxa calculada a partir dele.
""", className="md")),
                topico("SGS: juros e números do topo",
                       dcc.Markdown("""
O **SGS** (Sistema Gerenciador de Séries Temporais) é o banco de séries econômicas oficiais do Banco
Central. Ele traz **números prontos para o Brasil inteiro**, sem abertura por estado ou renda, e entra
como contexto do que o SCR.data não tem:

- **Juros médios cobrados das famílias:** usados no gráfico de juros e inadimplência, mais abaixo.
- **Dívida total × renda** e **renda que vai para dívidas:** os dois últimos indicadores do topo.
- **IPCA:** desconta a inflação no crescimento das carteiras (aba Crescimento × risco).

O SGS também tem a taxa oficial de inadimplência, que serviu para **conferir o cálculo deste
projeto** (veja a aba *Fontes e método*).
""", className="md")),
            ]),
            cartao("A inadimplência subiu mês a mês",
                   "Parcela da carteira de crédito com atraso acima de 90 dias, mês a mês.",
                   "g-evolucao",
                   leitura=[
                       "Cada ponto é um mês, do mais antigo (**esquerda**) ao mais recente (**direita**).",
                       "Quanto **mais alta** a linha, maior a parcela da dívida em atraso. Linha **subindo** = piora.",
                       "A linha muda conforme os filtros de **escopo** e **região**.",
                       "A linha vertical marca o mês de referência escolhido no filtro.",
                   ]),
            html.Div(className="duas", children=[
                cartao("Juros e inadimplência andam juntos no nível",
                       "Cada ponto é um mês: os juros daquele período contra a inadimplência alguns meses depois.",
                       "g-juros",
                       leitura=[
                           "Mais à **direita** = juros mais altos; mais **acima** = inadimplência maior.",
                           "Se os pontos sobem da **esquerda-baixo** para a **direita-cima**, as duas séries "
                           "andam juntas. O canto inferior esquerdo é o começo do período; o superior direito, o fim.",
                           "Use o controle ao lado para mudar quantos meses antes os juros são medidos e veja se "
                           "o padrão se mantém. Andar junto **não prova** que uma causa a outra: a explicação "
                           "está na aba *Comece aqui*.",
                       ]),
                html.Div(className="cartao", children=[
                    html.H3("Defasagem dos juros"),
                    html.P("Quantos meses antes os juros são medidos.", className="sub"),
                    dcc.Slider(id="f-lag", min=0, max=6, step=1, value=3,
                               marks={i: f"{i} m" for i in range(7)}),
                    html.Div(id="txt-juros", className="destaque"),
                ]),
            ]),
        ]),
        dcc.Tab(**ABA, label="Produtos", children=[
            cartao("Onde a inadimplência é maior e onde mais subiu",
                   "Taxa de inadimplência de cada tipo de crédito, no início do período e no mês de referência.",
                   "g-produtos",
                   leitura=[
                       "Cada linha é um tipo de crédito, ordenados do mais arriscado (**topo**) ao menos arriscado (**base**).",
                       f"**Círculo vazio** = {fmt_mes(MES_INICIAL)}. **Círculo cheio** = mês de referência, com o valor ao lado.",
                       "Mais à **direita** = maior parcela da dívida em atraso.",
                       "Quanto **mais longa** a barra cinza entre os dois círculos, mais o produto piorou. "
                       "Se o círculo cheio estiver à **esquerda** do vazio, o produto melhorou.",
                   ]),
        ]),
        dcc.Tab(**ABA, label="Estados", children=[
            html.Div(className="duas", children=[
                cartao("Mapa da inadimplência", "Taxa de inadimplência de cada estado no mês de referência.",
                       "g-mapa",
                       leitura=[
                           "Quanto **mais escuro** o estado, maior a inadimplência; quanto mais claro, menor.",
                           "A barra de cores à **direita** mostra a escala. Ela se ajusta ao filtro, então compare "
                           "os estados entre si, não com outro filtro.",
                           "Passe o mouse sobre um estado para ver o valor exato.",
                       ]),
                cartao("Ranking dos estados", "Do estado com maior inadimplência (topo) ao de menor (base).",
                       "g-ufs",
                       leitura=[
                           f"**Círculo vazio** = {fmt_mes(MES_INICIAL)}; **círculo cheio** = mês de referência.",
                           "Mais à **direita** = mais inadimplência. Barra cinza mais longa = estado que mais piorou.",
                           "A **Paraíba** aparece em azul para facilitar a comparação.",
                       ]),
            ]),
        ]),
        dcc.Tab(**ABA, label="Perfil do tomador", children=[
            html.Div(className="duas", children=[
                cartao("Renda", "Taxa de inadimplência por faixa de renda mensal, no mês de referência.",
                       "g-renda",
                       nota="A classificação de renda na base do Banco Central oscila muito entre meses "
                            "(saldos migram entre 'Sem rendimento', 'Até 1 SM' e 'Indisponível'), "
                            "por isso o gráfico compara faixas num mesmo mês, sem tendência.",
                       leitura=[
                           "Barras **azuis**: a escada de renda, da menor (**esquerda**) à maior (**direita**). "
                           "SM = salário mínimo. Barra **mais alta** = maior parcela da dívida em atraso.",
                           "Barras **cinza**, depois da linha pontilhada: dois grupos à parte, que não têm lugar na "
                           "escada. **Sem renda** são clientes que declararam não ter renda (por exemplo, "
                           "estudantes ou desempregados); **Indisponível**, os que não tiveram a renda informada pelo banco.",
                           "Os dois entram em todos os totais do painel, mas seus saldos mudam muito de um mês "
                           "para o outro, então a taxa deles é instável.",
                       ]),
                cartao("Ocupação", "Taxa de inadimplência por tipo de ocupação, no mês de referência.",
                       "g-ocup",
                       leitura=[
                           "Barra **mais longa** = mais inadimplência. A ordem vai da maior (**topo**) à menor (**base**).",
                           "A barra **cinza** (\"Outros\") reúne quem não tem ocupação identificada na base.",
                       ]),
            ]),
        ]),
        dcc.Tab(**ABA, label="Crescimento × risco", children=[
            html.Div(className="filtros", children=[
                html.Div([html.Label("Comparar por"),
                          dcc.RadioItems(id="f-dim", value="grupo_produto", inline=True,
                                         options=[{"label": " Produto", "value": "grupo_produto"},
                                                  {"label": " Tipo de instituição", "value": "segmento"}])]),
            ]),
            cartao("Quem cresceu e piorou ao mesmo tempo",
                   f"Quanto cada carteira cresceu desde {fmt_mes(MES_INICIAL)}, já descontada a inflação, e "
                   "quanto a inadimplência dela mudou.", "g-scatter",
                   leitura=[
                       "À **direita** da linha vertical: a carteira cresceu acima da inflação. À **esquerda**: encolheu.",
                       "**Acima** da linha horizontal: a inadimplência piorou. **Abaixo**: melhorou.",
                       "**Acima e à direita** = cresceu rápido e piorou junto: o sinal de alerta de crédito "
                       "concedido com critérios frouxos.",
                       "**Acima e à esquerda** = encolheu e mesmo assim piorou: um choque no setor (é o caso do "
                       "crédito dos produtores rurais, visível ao incluí-los no filtro de escopo).",
                       "**Abaixo e à direita** = cresceu sem piorar: crescimento saudável.",
                       "O **tamanho da bolha** é o tamanho da carteira. Passe o mouse para ver os números.",
                   ]),
        ]),
        dcc.Tab(**ABA, label="Fontes e método", children=[
            topico("O cálculo confere com o número oficial",
                   md_(f"""
Toda a inadimplência deste painel foi calculada do zero, a partir de {N_LINHAS_MI} milhões de linhas
brutas do SCR.data. Para conferir, refizemos a conta num **recorte equivalente** ao da taxa oficial do
Banco Central: só o **crédito livre**, em que banco e cliente negociam juros e destino do dinheiro
(cartão, cheque especial, crédito pessoal, inclusive consignado, e veículos). Ficam de fora os créditos
**direcionados**, com regras do governo (financiamento imobiliário, rural, BNDES). No SCR.data, o
crédito livre foi identificado pela coluna de origem do recurso ("sem destinação específica").
"""),
                   como_ler([
                       "**Linha azul:** nosso cálculo, só com crédito livre. **Linha cinza:** a taxa oficial do "
                       "Banco Central (série 21112 do SGS).",
                       "Quanto mais **coladas** as linhas, mais o cálculo confere. A distância entre elas, em "
                       f"média, é de **{br(DIF_MEDIA, 2)} ponto percentual**.",
                       f"Até {fmt_mes(MES_COLADO)}, as linhas praticamente coincidem (diferença de no máximo "
                       f"{br(DIF_MAX_COLADO, 2)} ponto). Depois, nosso cálculo "
                       f"passa a ficar um pouco acima, chegando a {br(DIF_FIM, 1)} ponto em {fmt_mes(MES_FINAL)}. "
                       "A causa não aparece nos dados abertos.",
                       "As **variações de um mês para o outro** também andam juntas (correlação de "
                       f"**{br(CORR_VAR_VALID, 2)}**): quando a taxa oficial sobe, a nossa sobe junto.",
                   ]),
                   dcc.Graph(figure=figura_validacao(), config={"displayModeBar": False}),
                   md_(f"""
A taxa da aba *Evolução* fica mais baixa que esta por dois motivos. No padrão do painel, ela
**inclui** o financiamento imobiliário (R$ {br(HAB_TRI, 2)} trilhão com só {br(HAB_TAXA, 1)}% de atraso) e
**exclui** o saldo legado de cartão, que faz parte do crédito livre e tem quase 80% de atraso.
""")),
            html.Div(className="cartao texto", children=[
            dcc.Markdown(f"""
**Fonte principal.** [SCR.data](https://dadosabertos.bcb.gov.br/dataset/scr_data), base aberta do
Sistema de Informações de Crédito do Banco Central. Recorte: pessoas físicas, {fmt_mes(MES_INICIAL)}
a {fmt_mes(MES_FINAL)}.

**Taxa de inadimplência** = carteira inadimplida ÷ carteira ativa. No SCR.data, a carteira
inadimplida soma o saldo inteiro das operações com atraso acima de 90 dias, não só as parcelas
atrasadas.

**Escopos.** O padrão, *Famílias: consumo e habitação*, exclui o crédito de produtores rurais
pessoa física (crédito à produção agropecuária, que explica mais de um quarto do aumento do saldo
inadimplido no período) e o saldo legado de cartão "não migrado", um estoque antigo com inadimplência
perto de 80% que distorceria os agregados. Os dois podem ser incluídos pelo filtro para comparação.

**Séries complementares (SGS/BCB).** Juros do crédito livre PF (20740), Selic (432), IPCA (433),
inadimplência do crédito livre PF (21112, usada na validação acima), endividamento (29037) e
comprometimento de renda (29034).

**Código:** coleta, EDA e este app no repositório do projeto no GitHub.
"""),
        ])]),
    ]),
    html.Footer("Gustavo Hortencio da Silva · dados públicos do Banco Central · valores nominais em R$, "
                "exceto onde indicado"),
])


# ---------------------------------------------------------------- callbacks
@app.callback(
    Output("k-taxa-valor", "children"), Output("k-taxa-detalhe", "children"),
    Output("k-var-valor", "children"), Output("k-var-detalhe", "children"),
    Output("k-cart-valor", "children"), Output("k-cart-detalhe", "children"),
    Output("g-evolucao", "figure"),
    Input("f-escopo", "value"), Input("f-regiao", "value"), Input("f-mes", "value"),
)
def evolucao(escopo, regioes, mes):
    mes = pd.Timestamp(mes)
    s = taxa_por(filtrar(fato, escopo, regioes), ["mes"]).set_index("mes")
    t_ref, t_ini = s.loc[mes, "taxa"], s["taxa"].iloc[0]
    cart = s.loc[mes, "carteira_ativa_mi"] / 1e6
    inad = s.loc[mes, "carteira_inadimplida_mi"] / 1e3

    fig = go.Figure()
    rotulos = [fmt_mes(m) for m in s.index]
    fig.add_scatter(x=rotulos, y=s["taxa"], name="Inadimplência calculada (crédito do filtro)", mode="lines+markers",
                    line=dict(color=AZUL, width=2), marker=dict(size=7),
                    hovertemplate="%{y:.2f}%<extra>calculada</extra>")
    fig.add_vline(x=fmt_mes(mes), line=dict(color=CINZA_CLARO, width=1))
    estilo(fig, 360, yaxis_ticksuffix="%", yaxis_rangemode="tozero", hovermode="x unified",
           xaxis_type="category", showlegend=False)
    return (f"{br(t_ref, 2)}%",
            f"de cada R$ 100 emprestados, R$ {br(t_ref, 2)} estão há mais de 90 dias sem pagamento "
            f"· {fmt_mes(mes)}",
            f"{'+' if t_ref >= t_ini else ''}{br(t_ref - t_ini, 2)} p.p.",
            f"era {br(t_ini, 2)}% em {fmt_mes(MES_INICIAL)}",
            f"R$ {br(cart, 2)} tri", f"saldo devedor no escopo do filtro; R$ {br(inad, 1)} bi em atraso", fig)


@app.callback(Output("g-juros", "figure"), Output("txt-juros", "children"),
              Input("f-escopo", "value"), Input("f-regiao", "value"), Input("f-lag", "value"))
def juros(escopo, regioes, lag):
    s = taxa_por(filtrar(fato, escopo, regioes), ["mes"]).set_index("mes")["taxa"]
    j = nac["juros_credito_livre_pf"].shift(lag)
    d = pd.DataFrame({"taxa": s, "juros": j}).dropna()
    r_nivel = d["taxa"].corr(d["juros"])
    r_var = d["taxa"].diff().corr(d["juros"].diff())
    fig = go.Figure(go.Scatter(
        x=d["juros"], y=d["taxa"], mode="markers", text=[fmt_mes(m) for m in d.index],
        marker=dict(size=10, color=AZUL, line=dict(color="white", width=2)),
        customdata=[br(100 * ((1 + v / 100) ** (1 / 12) - 1), 1) for v in d["juros"]],
        hovertemplate="%{text}<br>juros: %{x:.1f}% ao ano (≈ %{customdata}% ao mês)"
                      "<br>inadimplência: %{y:.2f}%<extra></extra>"))
    estilo(fig, 340, xaxis_ticksuffix="%", yaxis_ticksuffix="%",
           xaxis_title=f"Juros médios cobrados das famílias, {lag} {'mês' if lag == 1 else 'meses'} antes (% ao ano)",
           yaxis_title="Inadimplência (% da carteira)")
    texto = [
        html.P([html.Strong(f"Correlação no nível: {br(r_nivel, 2)}"),
                f" ({len(d)} meses)."]),
        html.P([html.Strong(f"Correlação das variações mensais: {br(r_var, 2)}.")]),
        html.P("As duas séries sobem no período, e isso infla a correlação no nível. Mês a mês, "
               "a relação é fraca e muda de sinal conforme a defasagem: com menos de dois anos de "
               "dados, não dá para afirmar que os juros antecipam a inadimplência. É uma pista, "
               "não uma conclusão.", className="sub"),
    ]
    return fig, texto


def haltere(g: pd.DataFrame, rotulo: str, destaque=None, altura=None) -> go.Figure:
    """Gráfico de halteres: início (vazio) e referência (cheio) por categoria."""
    g = g.sort_values("ref")
    cores = [AZUL if (destaque is None or c == destaque) else CINZA for c in g[rotulo]]
    fig = go.Figure()
    for _, r in g.iterrows():
        fig.add_shape(type="line", x0=r["ini"], x1=r["ref"], y0=r[rotulo], y1=r[rotulo],
                      line=dict(color=CINZA_CLARO, width=3), layer="below")
    fig.add_scatter(x=g["ini"], y=g[rotulo], mode="markers", name=fmt_mes(MES_INICIAL),
                    marker=dict(size=10, color="white", line=dict(color=cores, width=2)),
                    hovertemplate="%{y}: %{x:.2f}%<extra>" + fmt_mes(MES_INICIAL) + "</extra>")
    fig.add_scatter(x=g["ref"], y=g[rotulo], mode="markers+text", name="Referência",
                    marker=dict(size=11, color=cores),
                    text=[f"{br(v, 1)}%" for v in g["ref"]], textposition="middle right",
                    textfont=dict(color=TEXTO_2, size=11),
                    hovertemplate="%{y}: %{x:.2f}%<extra>referência</extra>")
    estilo(fig, altura or max(320, 28 * len(g) + 60), showlegend=False,
           xaxis_ticksuffix="%", xaxis_rangemode="tozero")
    fig.update_xaxes(range=[0, max(g["ref"].max(), g["ini"].max()) * 1.18])
    return fig


def comparar(df, chave, escopo, regioes, mes):
    d = filtrar(df, escopo, regioes)
    a = taxa_por(d[d["mes"] == MES_INICIAL], [chave]).set_index(chave)["taxa"]
    b = taxa_por(d[d["mes"] == pd.Timestamp(mes)], [chave]).set_index(chave)["taxa"]
    return pd.DataFrame({"ini": a, "ref": b}).dropna().reset_index()


@app.callback(Output("g-produtos", "figure"),
              Input("f-escopo", "value"), Input("f-regiao", "value"), Input("f-mes", "value"))
def produtos(escopo, regioes, mes):
    return haltere(comparar(fato, "grupo_produto", escopo, regioes, mes), "grupo_produto")


def cor_sequencial(v: float, vmin: float, vmax: float) -> str:
    """Interpola a rampa azul (claro = menor, escuro = maior)."""
    t_ = 0 if vmax == vmin else (v - vmin) / (vmax - vmin)
    pos = t_ * (len(SEQ_AZUL) - 1)
    i = min(int(pos), len(SEQ_AZUL) - 2)
    f = pos - i
    a, b = SEQ_AZUL[i], SEQ_AZUL[i + 1]
    rgb = [round(int(a[k:k + 2], 16) * (1 - f) + int(b[k:k + 2], 16) * f) for k in (1, 3, 5)]
    return "#" + "".join(f"{c:02x}" for c in rgb)


def mapa_uf(valores: pd.Series) -> go.Figure:
    """Mapa coroplético desenhado como polígonos num plano comum.

    Não depende de mapas-base nem de CDN (funciona offline e em qualquer host)."""
    vmin, vmax = valores.min(), valores.max()
    fig = go.Figure()
    for feat in GEO["features"]:
        uf = feat["id"]
        if uf not in valores.index:
            continue
        v = valores[uf]
        geom = feat["geometry"]
        poligonos = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        xs, ys = [], []
        for pol in poligonos:
            anel = pol[0]  # só o contorno externo
            xs += [p[0] for p in anel] + [None]
            ys += [p[1] for p in anel] + [None]
        fig.add_scatter(x=xs, y=ys, fill="toself", mode="lines", name=uf,
                        fillcolor=cor_sequencial(v, vmin, vmax),
                        line=dict(color="white", width=1),
                        hoveron="fills", hoverinfo="text",
                        text=f"{feat['properties']['nome']} ({uf}): {br(v, 2)}%")
    # legenda de cor: um marcador invisível que carrega a escala
    fig.add_scatter(x=[None], y=[None], mode="markers", showlegend=False, hoverinfo="skip",
                    marker=dict(colorscale=[[i / (len(SEQ_AZUL) - 1), h] for i, h in enumerate(SEQ_AZUL)],
                                cmin=vmin, cmax=vmax, color=[vmin], showscale=True,
                                colorbar=dict(ticksuffix="%", thickness=12, len=0.6, outlinewidth=0,
                                              tickfont=dict(color=TEXTO_2))))
    estilo(fig, 560, showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1.03)
    return fig


@app.callback(Output("g-mapa", "figure"), Output("g-ufs", "figure"),
              Input("f-escopo", "value"), Input("f-regiao", "value"), Input("f-mes", "value"))
def estados(escopo, regioes, mes):
    c = comparar(fato, "uf", escopo, regioes, mes)
    mapa = mapa_uf(c.set_index("uf")["ref"])
    return mapa, haltere(c, "uf", destaque="PB", altura=760)


@app.callback(Output("g-renda", "figure"), Output("g-ocup", "figure"),
              Input("f-escopo", "value"), Input("f-regiao", "value"), Input("f-mes", "value"))
def perfil(escopo, regioes, mes):
    mes = pd.Timestamp(mes)
    r = taxa_por(filtrar(fato, escopo, regioes).query("mes == @mes"), ["renda"])
    r["ordem"] = r["renda"].map({k: i for i, k in enumerate(ORDEM_RENDA)})
    r = r.sort_values("ordem")
    cores = [CINZA if x in ("Indisponível", "Sem rendimento") else AZUL for x in r["renda"]]
    f1 = go.Figure(go.Bar(x=r["renda"].map(RENDA_CURTA), y=r["taxa"], marker_color=cores,
                          marker_cornerradius=4, text=[f"{br(v, 1)}%" for v in r["taxa"]],
                          textposition="outside", textfont=dict(color=TEXTO_2),
                          hovertemplate="%{x}: %{y:.2f}%<extra></extra>"))
    estilo(f1, 380, yaxis_ticksuffix="%", bargap=0.35, yaxis_range=[0, r["taxa"].max() * 1.28])
    # separa visualmente a escada de renda dos dois grupos à parte
    n_escada = int((~r["renda"].isin(["Sem rendimento", "Indisponível"])).sum())
    if n_escada < len(r):
        f1.add_vline(x=n_escada - 0.5, line=dict(color=CINZA, width=1, dash="dot"))
        f1.add_annotation(x=n_escada - 0.5, y=1, yref="paper", text="grupos à parte", showarrow=False,
                          xanchor="left", yanchor="top", xshift=6, font=dict(size=11, color=TEXTO_2))

    o = taxa_por(filtrar(ocup, escopo, None).query("mes == @mes"), ["ocupacao"]).sort_values("taxa")
    cores_o = [CINZA if x == "Outros" else AZUL for x in o["ocupacao"]]
    f2 = go.Figure(go.Bar(y=o["ocupacao"], x=o["taxa"], orientation="h", marker_color=cores_o,
                          marker_cornerradius=4, text=[f"{br(v, 1)}%" for v in o["taxa"]],
                          textposition="outside", textfont=dict(color=TEXTO_2), cliponaxis=False,
                          hovertemplate="%{y}: %{x:.2f}%<extra></extra>"))
    estilo(f2, 380, xaxis_ticksuffix="%", bargap=0.35, xaxis_range=[0, o["taxa"].max() * 1.2],
           margin=dict(l=10, r=40, t=10, b=10))
    return f1, f2


@app.callback(Output("g-scatter", "figure"),
              Input("f-escopo", "value"), Input("f-mes", "value"), Input("f-dim", "value"))
def crescimento(escopo, mes, dim):
    mes = pd.Timestamp(mes)
    base = fato if dim == "grupo_produto" else seg
    d = filtrar(base, escopo, None)
    a = taxa_por(d[d["mes"] == MES_INICIAL], [dim]).set_index(dim)
    b = taxa_por(d[d["mes"] == mes], [dim]).set_index(dim)
    x = 100 * ((b["carteira_ativa_mi"] / a["carteira_ativa_mi"]) / (1 + ipca_acumulado(mes)) - 1)
    y = b["taxa"] - a["taxa"]
    g = pd.DataFrame({"x": x, "y": y, "cart": b["carteira_ativa_mi"] / 1e3}).dropna()
    g = g[g["cart"] >= 1]  # ignora categorias com menos de R$ 1 bi
    tamanho = 12 + 40 * (g["cart"] / g["cart"].max()) ** 0.5
    fig = go.Figure(go.Scatter(
        x=g["x"], y=g["y"], mode="markers+text", text=g.index, textposition="top center",
        textfont=dict(color=TEXTO_2, size=11),
        marker=dict(size=tamanho, color=AZUL, opacity=0.75, line=dict(color="white", width=2)),
        customdata=g["cart"],
        hovertemplate="%{text}<br>crescimento real: %{x:.1f}%<br>variação da taxa: %{y:+.2f} p.p."
                      "<br>carteira: R$ %{customdata:,.0f} bi<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=CINZA, width=1))
    fig.add_vline(x=0, line=dict(color=CINZA, width=1))
    estilo(fig, 520, xaxis_ticksuffix="%", yaxis_ticksuffix=" p.p.",
           xaxis_title="Crescimento da carteira acima da inflação (%)",
           yaxis_title="Mudança na inadimplência (pontos percentuais)")
    # rótulos dos quadrantes, nos cantos da área do gráfico
    for x, y, ax, ay, txt in [(1, 1, "right", "top", "cresceu e piorou"),
                              (0, 1, "left", "top", "encolheu e piorou"),
                              (1, 0, "right", "bottom", "cresceu sem piorar"),
                              (0, 0, "left", "bottom", "encolheu e melhorou")]:
        fig.add_annotation(xref="paper", yref="paper", x=x, y=y, xanchor=ax, yanchor=ay, text=txt,
                           showarrow=False, font=dict(size=11, color=CINZA), bgcolor="rgba(252,252,251,0.8)")
    return fig


if __name__ == "__main__":
    app.run(debug=True)
