# Roteiro do dashboard no Looker Studio

Passo a passo para montar o dashboard do Looker Studio, que é a entrega exigida pela EBAC, com as
bases de `dados/agregados/`. O dashboard em Dash (`app.py`) segue a mesma estrutura e pode servir de
referência visual.

## 1. Fontes de dados

Os CSVs já saem prontos de `src/gerar_bases.py`, em UTF-8 e separados por vírgula. O jeito mais
direto é enviá-los ao Looker Studio pelo conector **Upload de arquivo**, sem passar pelo Google
Sheets:

1. No relatório, **Adicionar dados > Upload de arquivo**.
2. Arraste o CSV (um por fonte de dados) e clique em **Conectar** quando o upload terminar.
3. Repita para os quatro arquivos:

| Arquivo | Linhas | Uso |
|---|---|---|
| `fato_credito_pf.csv` | ~61 mil | Base principal: mês × UF × produto × escopo × renda |
| `segmento_mes.csv` | ~1,3 mil | Tipo de instituição |
| `ocupacao_mes.csv` | ~2 mil | Ocupação |
| `serie_nacional.csv` | 21 | Taxas nacionais e séries do SGS (juros, Selic, IPCA, endividamento) |

Alternativa: importar cada CSV no Google Sheets (*Arquivo > Importar > Upload*) e conectar com
*Adicionar dados > Planilhas Google*. Vale a pena se você quiser atualizar os dados depois sem
refazer o relatório.

Em cada fonte, confira os tipos: `mes` como **Data**, `uf` como **Geo > Subdivisão de país
(1º nível)** e as colunas terminadas em `_mi` como **Número**.

**Rótulos do escopo.** Nos CSVs, a coluna `escopo` vem com os valores técnicos `Consumo e habitação`,
`Rural` e `Legado`. Para o filtro mostrar os mesmos nomes do dashboard em Dash, crie o campo:

```
Escopo do crédito = CASE
  WHEN escopo = "Consumo e habitação" THEN "Famílias: consumo e habitação"
  WHEN escopo = "Rural" THEN "Produtores rurais (pessoa física)"
  WHEN escopo = "Legado" THEN "Saldo legado de cartão"
END
```

Use esse campo num controle de **lista suspensa com seleção múltipla**, com só "Famílias: consumo e
habitação" marcado por padrão. Marcar mais itens soma os blocos, como no Dash.

## 2. Campos calculados (crie em cada fonte)

```
Taxa de inadimplência (%)  = SUM(carteira_inadimplida_mi) / SUM(carteira_ativa_mi) * 100
Carteira (R$ bi)           = SUM(carteira_ativa_mi) / 1000
Inadimplido (R$ bi)        = SUM(carteira_inadimplida_mi) / 1000
UF (geo)                   = CONCAT("BR-", uf)
```

A taxa **tem** de ser razão de somas. Nunca use média de uma coluna de taxa: cada linha tem peso
(saldo) diferente.

## 3. Controles (topo de todas as páginas)

- **Escopo do crédito** (lista suspensa no campo calculado acima), com padrão "Famílias: consumo e
  habitação".
- **Região** (lista suspensa em `regiao`).
- **Período** (controle de intervalo de datas em `mes`).

## 4. Páginas e gráficos

### Página 1 · Visão geral
- **Visões gerais (scorecards):** Taxa de inadimplência (com comparação ao período anterior), Carteira
  (R$ bi), Inadimplido (R$ bi). Da `serie_nacional`: último `endividamento_familias` e
  `comprometimento_renda`.
- **Série temporal:** `mes` × Taxa de inadimplência. Título: *"A inadimplência subiu mês a mês"*.
- **Texto de interpretação:** "Em 21 meses, a inadimplência das famílias no crédito de consumo e
  habitação subiu de 3,3% para 4,5%. Quase metade da alta do total vem do crédito rural e de um
  estoque legado de cartão."

### Página 2 · Produtos
- **Barras horizontais:** `grupo_produto` × Taxa de inadimplência, ordenado do maior para o menor.
- **Tabela** com Carteira, Taxa e variação (use a comparação de período do Looker).
- **Interpretação:** "Rotativo (21%), cheque especial (15%) e cartão parcelado (14%) concentram o
  risco. Habitacional e consignado seguem protegidos por garantia e desconto em folha."

### Página 3 · Estados
- **Mapa geográfico preenchido** (campo `UF (geo)`, métrica Taxa), em escala de uma cor só.
- **Barras** por `uf`, com a Paraíba destacada (cor de série diferente por regra condicional).
- **Interpretação:** "O Norte lidera (6,0%). A Paraíba tem a segunda menor taxa (3,6%) e a menor
  alta do país."

### Página 4 · Perfil do tomador
- **Colunas:** `renda` × Taxa (ordem manual das faixas, do menor para o maior salário).
- **Barras:** `ocupacao` × Taxa (fonte `ocupacao_mes`).
- **Nota fixa:** a classificação de renda oscila entre meses; compare faixas dentro do mesmo mês.

### Página 5 · Crescimento × risco
- **Tabela** da fonte `segmento_mes`: segmento, Carteira, Taxa no início e no fim do período.
- **Interpretação:** "Fintechs dobraram a carteira e quase dobraram a inadimplência (11% para 21%)."

### Página 6 · Recomendações
Caixas de texto com as recomendações do `docs/03_relatorio_insights.md`, uma por público
(instituições, governo, famílias).

## 5. Estilo

- Uma cor de destaque (azul) e cinza para o resto; vermelho/verde só para variação.
- Títulos dos gráficos em forma de **frase com a conclusão**, não só o nome da métrica.
- Rodapé em todas as páginas: "Fonte: SCR.data e SGS, Banco Central. Elaboração própria."
