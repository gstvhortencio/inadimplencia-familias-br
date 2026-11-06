"""Gera os notebooks da EDA a partir de células definidas aqui (para versionar o conteúdo
de forma legível). Rode a partir da raiz do repositório:

    python notebooks/_construir_notebooks.py
    jupyter nbconvert --to notebook --execute --inplace notebooks/01_limpeza_e_preparacao.ipynb
    jupyter nbconvert --to notebook --execute --inplace notebooks/02_eda.ipynb
"""
from pathlib import Path

import nbformat as nbf

AQUI = Path(__file__).resolve().parent

SETUP = '''import sys
from pathlib import Path

RAIZ = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(RAIZ / "src"))

import duckdb
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import transformacao as t

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 30)
pd.set_option("display.float_format", lambda x: f"{x:,.2f}")

AZUL, CINZA, CINZA_CLARO, TEXTO_2 = "#2a78d6", "#a8a69d", "#d9d7cf", "#52514e"
plt.rcParams.update({
    "figure.figsize": (10, 4.5), "figure.dpi": 110, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": "#ebeae6",
    "axes.edgecolor": "#d9d7cf", "axes.titleweight": "bold", "axes.titlesize": 13,
    "axes.titlelocation": "left", "xtick.color": TEXTO_2, "ytick.color": TEXTO_2,
    "font.size": 11,
})
pct = mtick.PercentFormatter(decimals=0)

con = t.conectar(RAIZ / "dados" / "scr_pf")
q = lambda sql: con.sql(sql).df()  # noqa: E731
MES_INI, MES_FIM = q("SELECT MIN(mes) a, MAX(mes) b FROM pf").iloc[0]
print(f"Período: {MES_INI:%m/%Y} a {MES_FIM:%m/%Y}")'''


def md(texto):
    return nbf.v4.new_markdown_cell(texto.strip())


def code(texto):
    return nbf.v4.new_code_cell(texto.strip())


# ------------------------------------------------------------------ notebook 01
nb1 = [
    md("""
# 01 · Limpeza e preparação dos dados

**Projeto:** inadimplência e endividamento das famílias brasileiras (parceria EBAC × Semantix).

Este notebook parte dos Parquets mensais gerados por `src/coletar_dados.py` (só pessoas físicas)
e verifica, antes de qualquer análise:

1. estrutura, tipos e valores ausentes;
2. consistência contábil das colunas de saldo;
3. o que significa a coluna `carteira_inadimplencia`;
4. estabilidade das categorias ao longo dos meses;
5. problemas de qualidade que mudam a análise (outliers, reclassificações);
6. validação contra as séries oficiais do Banco Central (SGS).

A limpeza em si (agrupamento de produtos, regiões, escopos) mora em `src/transformacao.py`,
para que notebook, Looker Studio e dashboard usem exatamente as mesmas regras.
"""),
    code(SETUP),
    md("## 1. Estrutura e tipos"),
    code('''bruto = pd.read_parquet(RAIZ / "dados" / "scr_pf")
print(f"{len(bruto):,} linhas × {bruto.shape[1]} colunas")
bruto.dtypes.to_frame("tipo").T'''),
    code('''bruto.head(3).T'''),
    md("""
Cada linha **não é um contrato**: é um agregado de operações que compartilham a mesma combinação de
mês, UF, tipo de instituição, ocupação, faixa de renda, modalidade, origem do recurso e indexador.
Os valores são saldos em reais. Por isso a taxa de inadimplência é sempre calculada como **soma do
saldo inadimplido ÷ soma da carteira ativa**, nunca como média de taxas por linha.
"""),
    md("## 2. Valores ausentes e operações suprimidas"),
    code('''ausentes = bruto.isna().mean().mul(100).round(2)
ausentes[ausentes > 0].to_frame("% ausente")'''),
    md("""
Só `numero_de_operacoes` tem ausentes: no arquivo original elas vêm como **-1**, que o script de
coleta converte em ausente. É o Banco Central suprimindo a contagem quando há poucas operações
(sigilo). Os saldos dessas linhas existem e entram nas somas; só a contagem fica de fora. Por isso
o projeto não usa número de operações como métrica.
"""),
    md("## 3. Consistência contábil"),
    code('''checagens = pd.Series({
    "carteira ativa = a vencer + vencida": np.isclose(
        bruto.carteira_ativa, bruto.carteira_a_vencer + bruto.carteira_vencida, atol=1).mean(),
    "inadimplida >= vencido acima de 90 dias": (
        bruto.carteira_inadimplencia >= bruto.vencido_acima_de_90_dias - 1).mean(),
    "saldos não negativos": (bruto.select_dtypes("number").drop(columns="numero_de_operacoes") >= 0)
        .all(axis=1).mean(),
}).mul(100).round(2)
checagens.to_frame("% das linhas que passam")'''),
    md("""
As identidades contábeis fecham em 100% das linhas. A segunda checagem mostra algo importante:
a carteira inadimplida é **sempre maior ou igual** ao vencido acima de 90 dias. Pela metodologia do
SCR.data, ela soma o **saldo inteiro** das operações com atraso superior a 90 dias (parcelas vencidas
e a vencer), não só o que já venceu. É o conceito usado pelo próprio Banco Central.
"""),
    code('''tot = q("""SELECT mes, SUM(carteira_inadimplencia) inad, SUM(vencido_acima_de_90_dias) v90,
                    SUM(carteira_ativa) ativa FROM pf GROUP BY 1 ORDER BY 1""")
tot["taxa_inadimplencia"] = 100 * tot.inad / tot.ativa
tot["taxa_vencido_90d"] = 100 * tot.v90 / tot.ativa
tot[["mes", "taxa_inadimplencia", "taxa_vencido_90d"]].iloc[[0, -1]]'''),
    md("## 4. Estabilidade das categorias"),
    code('''q("""SELECT mes, COUNT(DISTINCT submodalidade) submodalidades, COUNT(DISTINCT segmento) segmentos,
           COUNT(DISTINCT renda) faixas_renda, COUNT(DISTINCT ocupacao) ocupacoes, COUNT(DISTINCT uf) ufs
    FROM pf GROUP BY 1 ORDER BY 1""").set_index("mes").describe().loc[["min", "max"]]'''),
    md("""
As categorias são estáveis no período. Entre 49 e 52 submodalidades aparecem conforme o mês, mas as
que entram e saem têm saldo desprezível (operações de câmbio). Para a análise, as ~50 submodalidades
foram agrupadas em 12 **grupos de produto** (regra em `src/transformacao.py`):
"""),
    code('''grupos = q("""SELECT grupo_produto, COUNT(DISTINCT submodalidade) submodalidades,
                      SUM(carteira_ativa) / 1e9 carteira_bi
               FROM pf WHERE mes = (SELECT MAX(mes) FROM pf) GROUP BY 1 ORDER BY 3 DESC""")
grupos'''),
    md("## 5. Problemas de qualidade que mudam a análise"),
    md("""
### 5.1 Saldo de cartão "não migrado": um outlier que distorce tudo

A submodalidade `Cartão de crédito - não migrado` é um estoque legado de dívidas de cartão
(registro anterior à padronização das modalidades de cartão). Ela tem inadimplência perto de 80% e
**cresceu no período**, então sozinha empurra a taxa agregada para cima.
"""),
    code('''legado = q("""SELECT mes,
        SUM(carteira_ativa) FILTER (WHERE grupo_produto = 'Cartão: saldo não migrado (legado)') / 1e9 AS carteira_bi,
        100 * SUM(carteira_inadimplencia) FILTER (WHERE grupo_produto = 'Cartão: saldo não migrado (legado)')
            / SUM(carteira_ativa) FILTER (WHERE grupo_produto = 'Cartão: saldo não migrado (legado)') AS taxa,
        100 * SUM(carteira_inadimplencia) / SUM(carteira_ativa) AS taxa_total,
        100 * SUM(carteira_inadimplencia) FILTER (WHERE grupo_produto <> 'Cartão: saldo não migrado (legado)')
            / SUM(carteira_ativa) FILTER (WHERE grupo_produto <> 'Cartão: saldo não migrado (legado)') AS taxa_sem_legado
    FROM pf GROUP BY 1 ORDER BY 1""")
legado.iloc[[0, -1]]'''),
    md("""
**Decisão:** o saldo legado fica fora do escopo principal e é tratado à parte. Ele não representa
crédito novo às famílias, e manter na média faria a análise atribuir a alta a um estoque antigo.

### 5.2 Faixas de renda: reclassificação entre meses

Os saldos das faixas mais baixas oscilam de forma incompatível com a realidade. Bilhões de reais
saem e voltam para "Sem rendimento", "Até 1 SM" e "Indisponível" de um mês para o outro:
"""),
    code('''renda = q("SELECT mes, renda, SUM(carteira_ativa)/1e9 bi FROM pf GROUP BY ALL").pivot(
    index="mes", columns="renda", values="bi")[["Sem rendimento", "Até 1 salário mínimo", "Indisponível"]]
fig, ax = plt.subplots()
for col, cor in zip(renda.columns, [CINZA, AZUL, "#eb6834"]):
    ax.plot(renda.index, renda[col], marker="o", ms=4, lw=2, color=cor, label=col)
ax.set_title("Carteira por faixa de renda (R$ bilhões): saltos de reclassificação")
ax.legend(frameon=False); plt.tight_layout(); plt.show()'''),
    md("""
Em fevereiro/2025 a faixa "Sem rendimento" cai de R$ 117 bi para R$ 11 bi, e em maio/2026 "Até 1 SM"
perde R$ 116 bi num mês, sem nenhum evento econômico que explique. São mudanças de classificação
na fonte. **Decisão:** renda é analisada **dentro de cada mês** (comparação entre faixas), nunca como
tendência ao longo do tempo. As categorias "Sem rendimento" e "Indisponível" aparecem separadas
nos gráficos.

### 5.3 Crédito rural

O crédito rural a pessoas físicas é crédito à **produção** (produtor rural pessoa física), não ao
consumo das famílias. Como veremos na EDA, ele explica uma parte grande da alta do período e
concentra-se em estados do agronegócio. **Decisão:** a análise principal usa o escopo
**"Consumo e habitação"** (sem rural e sem legado). O rural aparece como recorte próprio.
"""),
    md("## 6. Validação contra as séries oficiais do Banco Central"),
    code('''sgs = t.ler_sgs(RAIZ / "dados" / "sgs.parquet", ate=MES_FIM)
consumo = q("""SELECT mes, 100 * SUM(carteira_inadimplencia) / SUM(carteira_ativa) taxa
               FROM pf WHERE grupo_produto NOT IN ('Rural', 'Cartão: saldo não migrado (legado)')
               GROUP BY 1 ORDER BY 1""").set_index("mes")
consumo.index = pd.to_datetime(consumo.index)
val = consumo.join(sgs["inadimplencia_credito_livre_pf"])
print(f"Correlação entre a taxa calculada (consumo) e a série oficial 21112: "
      f"{val.corr().iloc[0, 1]:.3f}")
val.iloc[[0, 6, 12, -1]]'''),
    md("""
A taxa calculada no SCR.data acompanha a série oficial de inadimplência do crédito livre
(correlação acima de 0,94), mas em nível mais baixo. Isso é esperado: o escopo de consumo e habitação
inclui o **financiamento imobiliário**, crédito **direcionado** (com regras do governo) que é enorme e
quase não atrasa. O crédito livre, que a série 21112 mede, reúne cartão, cheque especial, crédito
pessoal (inclusive consignado) e veículos. A célula abaixo recalcula no SCR.data só o crédito livre,
usando a coluna `origem` ("sem destinação específica" = livre).
Os números de endividamento (29037) e comprometimento de renda (29034) chegaram a
50,1% e 29,0% em agosto/2026, os mesmos divulgados pelo Banco Central à imprensa.
"""),
    code('''livre = bruto.assign(livre=bruto.origem.astype(str).eq("Sem destinação específica"))
livre = (livre[livre.livre].groupby("data_base")[["carteira_inadimplencia", "carteira_ativa"]].sum())
livre = (100 * livre.carteira_inadimplencia / livre.carteira_ativa).rename("scr_so_credito_livre")
livre.index = pd.to_datetime(livre.index)
comp = pd.concat([livre, sgs["inadimplencia_credito_livre_pf"]], axis=1, sort=True).loc[livre.index]
dif = comp.iloc[:, 0] - comp.iloc[:, 1]
print(f"Diferença média (absoluta): {dif.abs().mean():.2f} p.p. · maior diferença: {dif.abs().max():.2f} p.p.")
print(f"Correlação das variações mensais: {comp.iloc[:, 0].diff().corr(comp.iloc[:, 1].diff()):.2f}")
comp.assign(diferenca_pp=dif).iloc[[0, 6, 8, 9, 12, -1]]'''),
    md("""
Recalculado só com o crédito livre, o SCR.data acompanha a série oficial: as duas praticamente
coincidem até set/2025 (diferença de no máximo 0,11 p.p.) e a distância média no período é de
0,25 p.p. A partir de out/2025, o cálculo passa a ficar até ~0,5 p.p. acima, e a causa não aparece
nos dados abertos (o saldo legado de cartão, que seria um candidato, cresce de forma contínua desde
jan/2025, sem salto em outubro).

Note que a correlação **no nível** (acima de 0,94) não serve como prova, pelo mesmo motivo discutido
na EDA para os juros: séries com tendência sempre parecem correlacionadas. O teste que importa é o
das **variações mensais**, que têm correlação de 0,83.

**Conclusão da preparação:** os dados são consistentes e confiáveis para a análise, com três
cuidados documentados: saldo legado de cartão à parte, renda só em corte transversal e crédito
rural em recorte próprio.
"""),
]

# ------------------------------------------------------------------ notebook 02
nb2 = [
    md("""
# 02 · Análise exploratória (EDA)

Perguntas da dissertação:

1. Em quais modalidades a inadimplência mais cresce?
2. Quais estados e regiões estão mais expostos?
3. Quais faixas de renda e ocupações são mais vulneráveis?
4. A inadimplência acompanha os juros com defasagem?
5. Onde o crédito cresce rápido e a inadimplência sobe junto?

Escopo principal: **consumo e habitação** (sem crédito rural e sem o saldo legado de cartão;
ver notebook 01). As consultas SQL equivalentes estão em `sql/consultas_eda.sql`.
"""),
    code(SETUP),
    code('''CONSUMO = "grupo_produto NOT IN ('Rural', 'Cartão: saldo não migrado (legado)')"
sgs = t.ler_sgs(RAIZ / "dados" / "sgs.parquet", ate=MES_FIM)
IPCA_ACUM = (1 + sgs.ipca_mensal.loc[MES_INI:MES_FIM].iloc[1:] / 100).prod() - 1
print(f"IPCA acumulado no período: {100 * IPCA_ACUM:.2f}%")

def compara(dim, filtro=CONSUMO):
    d = q(f"""SELECT {dim} AS d, mes, SUM(carteira_ativa) ca, SUM(carteira_inadimplencia) ci
              FROM pf WHERE {filtro} AND mes IN ('{MES_INI:%Y-%m-%d}', '{MES_FIM:%Y-%m-%d}')
              GROUP BY ALL""")
    a, b = (d[d.mes == m].set_index("d") for m in (d.mes.min(), d.mes.max()))
    out = pd.DataFrame({"carteira_bi": b.ca / 1e9, "taxa_ini": 100 * a.ci / a.ca,
                        "taxa_fim": 100 * b.ci / b.ca})
    out["variacao_pp"] = out.taxa_fim - out.taxa_ini
    out["cresc_real_pct"] = 100 * ((b.ca / a.ca) / (1 + IPCA_ACUM) - 1)
    return out.sort_values("taxa_fim", ascending=False)'''),
    md("## 0. Visão geral: estatística descritiva"),
    code('''ultimo = q(f"""SELECT grupo_produto, uf, renda, ocupacao, segmento, carteira_ativa, carteira_inadimplencia
               FROM pf WHERE mes = '{MES_FIM:%Y-%m-%d}' AND {CONSUMO}""")
linhas = ultimo.assign(taxa=lambda d: 100 * d.carteira_inadimplencia / d.carteira_ativa.where(d.carteira_ativa > 0))
print(f"{len(linhas):,} linhas no último mês (escopo consumo e habitação)")
linhas[["carteira_ativa", "carteira_inadimplencia", "taxa"]].describe(
    percentiles=[.25, .5, .75, .9, .99]).T'''),
    md("""
A distribuição dos saldos por linha é muito assimétrica: a mediana é pequena e poucos agregados
concentram a maior parte da carteira (o percentil 99 é cerca de 2 mil vezes a mediana). Isso confirma
que médias por linha não fazem sentido aqui; todos os indicadores a seguir são **ponderados pelo
saldo**.
"""),
    code('''serie = q("""SELECT mes,
    100 * SUM(carteira_inadimplencia) / SUM(carteira_ativa) AS total,
    100 * SUM(carteira_inadimplencia) FILTER (WHERE grupo_produto NOT IN ('Rural', 'Cartão: saldo não migrado (legado)'))
        / SUM(carteira_ativa) FILTER (WHERE grupo_produto NOT IN ('Rural', 'Cartão: saldo não migrado (legado)')) AS consumo
    FROM pf GROUP BY 1 ORDER BY 1""").set_index("mes")
serie.index = pd.to_datetime(serie.index)
serie = serie.join(sgs["inadimplencia_credito_livre_pf"].rename("oficial_credito_livre"))

fig, ax = plt.subplots()
ax.plot(serie.index, serie.consumo, color=AZUL, lw=2, marker="o", ms=4, label="Consumo e habitação (SCR.data)")
ax.plot(serie.index, serie.total, color=CINZA, lw=2, label="Todo o crédito PF (SCR.data)")
ax.plot(serie.index, serie.oficial_credito_livre, color=CINZA, lw=2, ls=":", label="Oficial, crédito livre PF (SGS 21112)")
ax.yaxis.set_major_formatter(pct); ax.set_ylim(0)
ax.set_title("Taxa de inadimplência das pessoas físicas")
ax.legend(frameon=False, loc="lower right"); plt.tight_layout(); plt.show()
serie.iloc[[0, 11, -1]]'''),
    md("""
**Achado geral.** Em 21 meses, a inadimplência do crédito às pessoas físicas subiu de 3,97% para
6,17% da carteira. No escopo de consumo e habitação, foi de 3,30% para 4,49% (+1,19 p.p.). A série
oficial do crédito livre foi de 5,74% para 8,09%. A alta é contínua, sem nenhum mês de alívio
relevante, e acelera a partir de janeiro/2026.
"""),
    md("## 0.1 De onde veio o aumento do saldo inadimplido"),
    code('''contrib = q(f"""SELECT grupo_produto,
    SUM(carteira_inadimplencia) FILTER (WHERE mes = '{MES_FIM:%Y-%m-%d}') / 1e9
  - SUM(carteira_inadimplencia) FILTER (WHERE mes = '{MES_INI:%Y-%m-%d}') / 1e9 AS aumento_bi
  FROM pf GROUP BY 1 ORDER BY 2 DESC""").set_index("grupo_produto")
contrib["participacao_pct"] = 100 * contrib.aumento_bi / contrib.aumento_bi.sum()
contrib'''),
    md("""
O saldo inadimplido cresceu cerca de R$ 133 bilhões. O **crédito rural** responde por 27% desse
aumento e o **saldo legado de cartão** por 21%. Ou seja, quase metade da alta "visível" no total
vem de dois blocos que não são crédito de consumo das famílias. Isso justifica a separação de
escopos feita no notebook 01.
"""),
    md("## 1. Produtos: onde a inadimplência é maior e mais cresce"),
    code('''prod = compara("grupo_produto")
prod'''),
    code('''p = prod.sort_values("taxa_fim")
fig, ax = plt.subplots(figsize=(10, 5))
ax.hlines(p.index, p.taxa_ini, p.taxa_fim, color=CINZA_CLARO, lw=3, zorder=1)
ax.scatter(p.taxa_ini, p.index, s=60, facecolor="white", edgecolor=AZUL, lw=2, zorder=2, label=f"{MES_INI:%m/%Y}")
ax.scatter(p.taxa_fim, p.index, s=70, color=AZUL, zorder=3, label=f"{MES_FIM:%m/%Y}")
for y, v in zip(p.index, p.taxa_fim):
    ax.annotate(f"{v:.1f}%", (v, y), xytext=(6, 0), textcoords="offset points", va="center", color=TEXTO_2, fontsize=9)
ax.xaxis.set_major_formatter(pct); ax.set_xlim(0, p.taxa_fim.max() * 1.15)
ax.set_title("Inadimplência por produto: início × fim do período")
ax.legend(frameon=False, loc="lower right"); plt.tight_layout(); plt.show()'''),
    md("""
**Resposta à pergunta 1.**

- O **rotativo do cartão** é o produto mais arriscado e o que mais piorou: de 12,6% para 21,0%
  (+8,4 p.p.). Um em cada cinco reais devidos no rotativo está inadimplente.
- **Cheque especial** (15,2%) e **cartão parcelado pelo emissor e saque** (14,1%) vêm logo atrás.
  Junto com o rotativo, formam o bloco das dívidas emergenciais e mais caras.
- O **crédito pessoal não consignado** subiu +4,3 p.p. (7,5% para 11,8%). É o segundo maior
  aumento, numa carteira grande (R$ 380 bi).
- **Habitacional** (1,5%) e **consignado** (3,9%) seguem baixos: garantia real e desconto em folha
  protegem essas carteiras. Ainda assim, o consignado subiu 1,3 p.p.
"""),
    md("## 2. Estados e regiões"),
    code('''uf = compara("uf")
reg = compara("regiao")
reg'''),
    code('''u = uf.sort_values("taxa_fim")
cores = [AZUL if i == "PB" else CINZA for i in u.index]
fig, ax = plt.subplots(figsize=(10, 8))
ax.hlines(u.index, u.taxa_ini, u.taxa_fim, color=CINZA_CLARO, lw=3, zorder=1)
ax.scatter(u.taxa_ini, u.index, s=50, facecolor="white", edgecolor=cores, lw=2, zorder=2)
ax.scatter(u.taxa_fim, u.index, s=60, color=cores, zorder=3)
ax.xaxis.set_major_formatter(pct); ax.set_xlim(0, u.taxa_fim.max() * 1.12)
ax.set_title(f"Inadimplência por UF, consumo e habitação ({MES_INI:%m/%Y} vazio · {MES_FIM:%m/%Y} cheio)")
plt.tight_layout(); plt.show()'''),
    code('''# Contraste: com o crédito rural incluído, o ranking muda
com_rural = compara("uf", filtro="grupo_produto <> 'Cartão: saldo não migrado (legado)'")
pd.DataFrame({"rank_consumo": uf.taxa_fim.rank(ascending=False),
              "rank_com_rural": com_rural.taxa_fim.rank(ascending=False),
              "taxa_com_rural": com_rural.taxa_fim}).sort_values("rank_com_rural").head(8)'''),
    md("""
**Resposta à pergunta 2.**

- O **Norte** tem a maior inadimplência de consumo (6,0%) e uma das maiores altas (+2,0 p.p.).
  Tocantins (6,6%), Roraima (6,4%), Pará e Amazonas (6,0% e 5,9%) lideram.
- Incluir o crédito rural muda o retrato: Tocantins, Maranhão, Mato Grosso do Sul, Goiás e
  Mato Grosso sobem no ranking por causa do agronegócio. Quem olha só o total confunde **crise do
  crédito rural** com **endividamento das famílias**.
- **Paraíba** é um caso positivo: 3,6% em set/2026, segunda menor taxa do país e a segunda
  menor alta (+0,5 p.p.). Só o Distrito Federal tem taxa menor e subiu menos.
- Sul e Sudeste têm as menores taxas, mas o Rio Grande do Sul teve alta forte (+2,3 p.p.).
"""),
    md("## 3. Perfil do tomador: renda e ocupação"),
    code('''renda = q(f"""SELECT renda, SUM(carteira_ativa) ca, SUM(carteira_inadimplencia) ci FROM pf
              WHERE {CONSUMO} AND mes = '{MES_FIM:%Y-%m-%d}' GROUP BY 1""")
renda["taxa"] = 100 * renda.ci / renda.ca
renda["carteira_bi"] = renda.ca / 1e9
renda = renda.set_index("renda").loc[t.ORDEM_RENDA, ["carteira_bi", "taxa"]]

# média dos 21 meses, para não depender de um mês afetado pela reclassificação
media = q(f"""SELECT renda, mes, 100*SUM(carteira_inadimplencia)/SUM(carteira_ativa) taxa FROM pf
              WHERE {CONSUMO} GROUP BY ALL""").groupby("renda").taxa.mean()
renda["taxa_media_21m"] = media
renda'''),
    code('''r = renda.rename(index=t.RENDA_CURTA)
cores = [CINZA if i in ("Sem renda", "Indisponível") else AZUL for i in r.index]
fig, ax = plt.subplots()
ax.bar(r.index, r.taxa, color=cores, width=0.6)
for x, v in enumerate(r.taxa):
    ax.annotate(f"{v:.1f}%", (x, v), xytext=(0, 4), textcoords="offset points", ha="center", color=TEXTO_2, fontsize=9)
ax.yaxis.set_major_formatter(pct); ax.set_title(f"Inadimplência por faixa de renda, {MES_FIM:%m/%Y}")
plt.xticks(rotation=25, ha="right"); plt.tight_layout(); plt.show()'''),
    code('''ocup = compara("ocupacao")
ocup'''),
    md("""
**Resposta à pergunta 3.**

- O gradiente de renda é claro: de 7,3% em quem ganha **até 1 salário mínimo** a 2,5% na faixa de
  **10 a 20 SM**. Quem tem menos renda tem três vezes mais inadimplência. A média dos 21 meses
  confirma o padrão, então ele não depende do mês escolhido.
- A faixa **acima de 20 SM** (3,8%) foge do gradiente. Uma hipótese é que ela inclui tomadores de
  alto valor com operações maiores e mais concentradas; isso fica como pergunta, não conclusão.
- Por ocupação, **autônomos** (5,7%) e **MEI** (4,7%) são os mais vulneráveis: renda variável e sem
  desconto em folha. **Servidores públicos** (3,2%) e **empregados do setor privado** (3,4%) têm
  as menores taxas. Entre as ocupações identificadas, os autônomos tiveram a maior alta (+1,9 p.p.).
"""),
    md("## 4. Juros e inadimplência"),
    code('''base = serie[["consumo"]].join(sgs[["juros_credito_livre_pf", "selic_meta", "comprometimento_renda"]])
linhas = []
for var in ["juros_credito_livre_pf", "selic_meta", "comprometimento_renda"]:
    for lag in range(0, 7):
        b = base[var].shift(lag)
        linhas.append({"variavel": var, "defasagem_meses": lag,
                       "corr_nivel": base.consumo.corr(b),
                       "corr_variacao_mensal": base.consumo.diff().corr(b.diff()),
                       "n": int((base.consumo.notna() & b.notna()).sum())})
corr = pd.DataFrame(linhas)
corr.pivot(index="defasagem_meses", columns="variavel", values=["corr_nivel", "corr_variacao_mensal"]).round(2)'''),
    code('''fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
for ax, (var, titulo) in zip(axes, [("juros_credito_livre_pf", "Juros do crédito livre PF (% a.a.)"),
                                    ("selic_meta", "Selic meta (% a.a.)")]):
    ax.plot(base.index, base[var], color=AZUL, lw=2)
    ax.set_title(titulo)
plt.suptitle("As séries de juros (cada uma no seu eixo)", x=0.02, ha="left", fontweight="bold")
plt.tight_layout(); plt.show()'''),
    md("""
**Resposta à pergunta 4.**

- **No nível**, a correlação entre inadimplência e juros do crédito livre é alta (0,85 a 0,92
  com defasagem de 0 a 4 meses). O comprometimento de renda também anda junto (≈0,95).
- **Nas variações mensais**, a relação some: os coeficientes ficam entre -0,3 e 0,5 e mudam de
  sinal conforme a defasagem. As duas séries sobem no período, e qualquer par de séries com
  tendência mostra correlação alta no nível (correlação espúria).
- A Selic subiu até 15% e começou a cair em março/2026, mas a inadimplência continuou subindo.
  Isso é consistente com a ideia de que juros afetam a inadimplência com atraso longo; com 21
  meses, porém, não há dados para medir esse atraso com segurança.
- **Conclusão honesta:** juros altos e inadimplência alta coexistem, mas este período não permite
  afirmar que os juros *antecipam* a inadimplência. Seria preciso uma série mais longa e um modelo
  que controle a tendência.
"""),
    md("## 5. Crescimento do crédito × piora da inadimplência"),
    code('''cr = compara("grupo_produto", filtro="grupo_produto <> 'Cartão: saldo não migrado (legado)'")
sg = compara("segmento", filtro="grupo_produto <> 'Cartão: saldo não migrado (legado)'")
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
for ax, d, titulo in [(axes[0], cr, "Por produto"), (axes[1], sg[sg.carteira_bi >= 1], "Por tipo de instituição")]:
    tamanho = 30 + 800 * (d.carteira_bi / d.carteira_bi.max()) ** 0.5
    ax.scatter(d.cresc_real_pct, d.variacao_pp, s=tamanho, color=AZUL, alpha=0.7, edgecolor="white", lw=1.5)
    for nome, row in d.iterrows():
        ax.annotate(nome, (row.cresc_real_pct, row.variacao_pp), xytext=(0, 9), textcoords="offset points",
                    ha="center", fontsize=8, color=TEXTO_2)
    ax.axhline(0, color=CINZA, lw=1); ax.axvline(0, color=CINZA, lw=1)
    ax.set_xlabel("Crescimento real da carteira (%)"); ax.set_ylabel("Variação da inadimplência (p.p.)")
    ax.set_title(titulo)
plt.tight_layout(); plt.show()
sg[sg.carteira_bi >= 1]'''),
    md("""
**Resposta à pergunta 5.**

- **Fintechs:** a carteira de pessoas físicas mais que dobrou em termos reais (+108%) e a
  inadimplência subiu 10 p.p. (de 11,2% para 21,2%). É o sinal mais claro de crescimento com piora
  simultânea, ainda que numa carteira pequena (R$ 5 bi).
- **Financeiras:** +18% real e +4 p.p. (de 6,8% para 10,9%). Com R$ 341 bi, são o segundo maior
  contribuinte do aumento do saldo inadimplido, atrás só dos bancos.
- Entre produtos, **cheque especial** (+13% real, +2,9 p.p.) e **veículos** (+12%, +2,3 p.p.)
  cresceram e pioraram juntos. O **rotativo** cresceu pouco (+4%), mas piorou muito (+8,4 p.p.):
  o problema ali é a capacidade de pagamento, não a expansão.
- O **rural** encolheu em termos reais (-3,6%) e mesmo assim teve a maior alta de inadimplência
  em volume. É um choque no setor, não excesso de oferta de crédito.
"""),
    md("""
## Variáveis mais importantes e próximos passos

| Variável | Por que importa |
|---|---|
| Grupo de produto | Explica a maior parte da diferença de risco (de 0,3% a 21%). |
| Tipo de instituição | Fintechs e financeiras concentram crescimento com piora. |
| Faixa de renda | Gradiente de 3× entre a renda mais baixa e a mais alta. |
| Ocupação | Renda variável (autônomo, MEI) eleva o risco. |
| UF / região | Diferenças menores que as de produto, mas o Norte destoa. |

Os achados detalhados e as recomendações estão em `docs/03_relatorio_insights.md`.
"""),
    md("## Apêndice: consultas SQL"),
    code('''import re
blocos = re.split(r"\\n(?=-- \\[\\d+\\])", (RAIZ / "sql" / "consultas_eda.sql").read_text(encoding="utf-8"))[1:]
for bloco in blocos:
    titulo = bloco.splitlines()[0]
    sql = bloco.strip().rstrip(";").replace("dados/scr_pf", (RAIZ / "dados" / "scr_pf").as_posix())
    print(titulo)
    display(duckdb.sql(sql).df().head(8))'''),
]

for nome, celulas in [("01_limpeza_e_preparacao.ipynb", nb1), ("02_eda.ipynb", nb2)]:
    nb = nbf.v4.new_notebook()
    nb.cells = celulas
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nbf.write(nb, AQUI / nome)
    print("gerado:", nome)
