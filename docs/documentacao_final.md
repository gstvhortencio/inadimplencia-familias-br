# Documentação do projeto

**Inadimplência e endividamento das famílias brasileiras** · Projeto de parceria EBAC × Semantix
Gustavo Hortencio da Silva · novembro de 2026

Este documento reúne os três tópicos pedidos na entrega: **coleta de dados, modelagem e
conclusões**. Os detalhes estão nos arquivos indicados em cada seção.

---

## 1. Coleta de dados

**Fontes:** duas bases públicas do Banco Central do Brasil.

- **SCR.data:** saldos de crédito agregados por UF, produto, faixa de renda, ocupação e tipo de
  instituição. Download direto dos ZIPs anuais (`scrdata_{ANO}.zip`).
- **SGS:** nove séries temporais (juros, Selic, IPCA, inadimplência oficial, endividamento e
  comprometimento de renda), coletadas pela API REST pública.

**Recorte:** pessoas físicas, janeiro/2025 a setembro/2026, num total de 21 meses, 3,9 milhões de
linhas e R$ 4,8 trilhões de carteira no último mês.

**Automação (`src/coletar_dados.py`):** download com retomada quando a conexão cai, espera
progressiva entre tentativas e validação do ZIP; leitura dos CSVs direto do ZIP, em blocos; filtro
de pessoas físicas; gravação em Parquet (de ~100 MB para ~8 MB por mês). Não houve scraping: as
duas fontes oferecem acesso oficial e estruturado.

Detalhes: [`02_fontes_e_coleta.md`](02_fontes_e_coleta.md).

---

## 2. Modelagem

### 2.1 Preparação e qualidade dos dados

Feita em [`notebooks/01_limpeza_e_preparacao.ipynb`](../notebooks/01_limpeza_e_preparacao.ipynb):

| Verificação | Resultado | Decisão |
|---|---|---|
| Identidades contábeis (ativa = a vencer + vencida) | 100% das linhas | Dados consistentes |
| Valores ausentes | Só no número de operações (19,7%, suprimido por sigilo) | Não usar contagem de operações |
| Conceito de inadimplência | Saldo inteiro das operações com atraso > 90 dias | Taxa = inadimplida ÷ ativa |
| Saldo de cartão "não migrado" | Inadimplência de ~80%, cresce no período | Tratado à parte (escopo "Legado") |
| Faixas de renda | Reclassificações abruptas entre meses | Comparar faixas só dentro do mesmo mês |
| Crédito rural | 27% do aumento do saldo inadimplido | Recorte próprio, fora do escopo de consumo |
| Validação externa | Só crédito livre: 0,25 p.p. de diferença média para a série oficial 21112 e variações mensais com correlação de 0,83 | Base confiável (até 0,5 p.p. acima desde out/2025, causa não identificada) |

### 2.2 Modelo de dados

As regras de transformação ficam em um único módulo, `src/transformacao.py`, usado pelo notebook,
pelas bases do Looker Studio e pelo dashboard:

- **Grupo de produto:** as ~50 submodalidades viram 12 grupos (cartão rotativo, cheque especial,
  crédito pessoal consignado e não consignado, veículos, habitacional, rural etc.).
- **Região:** UF → Norte, Nordeste, Centro-Oeste, Sudeste, Sul.
- **Escopo:** *Consumo e habitação* (foco do projeto), *Rural* e *Legado*.

`src/gerar_bases.py` monta, com DuckDB, um **modelo agregado** em CSV (`dados/agregados/`):

| Tabela | Granularidade | Linhas | Medidas |
|---|---|---|---|
| `fato_credito_pf` | mês × UF × grupo de produto × renda | ~61 mil | carteira ativa, inadimplida, vencido > 90 dias (R$ mi) |
| `segmento_mes` | mês × tipo de instituição × produto | ~1,3 mil | idem |
| `ocupacao_mes` | mês × ocupação × produto | ~2 mil | idem |
| `serie_nacional` | mês | 21 | taxas do SCR.data + nove séries do SGS |

As medidas são **aditivas** (saldos em R$), e a taxa é sempre calculada como razão de somas na
camada de visualização. Assim, qualquer filtro (UF, produto, renda) produz a taxa correta.

### 2.3 Análise exploratória

Feita em [`notebooks/02_eda.ipynb`](../notebooks/02_eda.ipynb), com Python (pandas, DuckDB,
matplotlib) e SQL ([`sql/consultas_eda.sql`](../sql/consultas_eda.sql), sete consultas com
CTEs, filtros agregados e funções de janela). Técnicas usadas:

- estatística descritiva ponderada pelo saldo;
- comparação início × fim do período por produto, UF, região, renda, ocupação e instituição;
- decomposição do aumento do saldo inadimplido por grupo de produto;
- correlação no nível e nas variações mensais, com defasagens de 0 a 6 meses (juros, Selic,
  comprometimento de renda);
- crescimento real da carteira (deflacionado pelo IPCA) × variação da inadimplência.

### 2.4 Visualização

- **Looker Studio:** dashboard da entrega, montado sobre as bases agregadas. Roteiro em
  [`04_roteiro_looker_studio.md`](04_roteiro_looker_studio.md).
- **Dash (Python):** dashboard interativo (`app.py`) publicado no Render, aberto no navegador,
  com filtros de escopo, região e mês e sete abas: uma de abertura que explica a análise e os
  indicadores, evolução, produtos, estados, perfil do tomador, crescimento × risco e fontes e
  método (com a validação do cálculo contra a série oficial do Banco Central). Cada gráfico tem
  um quadro "Como ler".

---

## 3. Conclusões

1. **A inadimplência das pessoas físicas subiu de 3,97% para 6,17%** em 21 meses, sem nenhum mês
   de alívio relevante. No crédito de consumo e habitação, foi de 3,30% para 4,49%.
2. **Quase metade da alta não é consumo:** o crédito rural (27%) e o saldo legado de cartão (21%)
   explicam juntos 48% do aumento do saldo inadimplido. Separar esses blocos muda o diagnóstico.
3. **O rotativo do cartão é o epicentro:** 21% de inadimplência (+8,4 p.p.). Cheque especial
   (15,2%) e cartão parcelado (14,1%) completam o bloco das dívidas emergenciais.
4. **Renda baixa e variável concentram o risco:** quem ganha até 1 SM tem cerca de três vezes a
   inadimplência de quem ganha de 10 a 20 SM. Autônomos e MEIs têm as maiores taxas entre as
   ocupações.
5. **Norte lidera, e a Paraíba é destaque positivo:** segunda menor taxa do país (3,6%) e a menor
   alta entre as UFs.
6. **Fintechs e financeiras cresceram e pioraram juntas:** fintechs com +108% de carteira real e
   inadimplência de 11,2% para 21,2%.
7. **Juros × inadimplência:** correlação alta no nível, fraca nas variações. O período é curto
   demais para afirmar que os juros antecipam a inadimplência.

**Recomendações** (detalhadas no relatório): rever limites de rotativo e oferecer migração para
parcelamento; monitorar safras nas instituições que mais cresceram; adaptar modelos de risco à
renda variável; separar a política para o crédito rural da política para o endividamento das
famílias; priorizar o Norte e as faixas de até 2 SM em programas de renegociação.

Relatório completo: [`03_relatorio_insights.md`](03_relatorio_insights.md).
