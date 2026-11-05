# Household loan defaults in Brazil

*[Versão em português](README.md)*

An analysis of 21 months of consumer credit in Brazil (Jan 2025 – Sep 2026), built on 3.9 million
records from the Central Bank's **SCR.data** open credit registry and nine **SGS** time series.
Partnership project **EBAC × Semantix**.

**[Open the interactive dashboard](https://inadimplencia-familias-br.onrender.com)** (in Portuguese) · [Insights report (PT)](docs/03_relatorio_insights.md)

> The dashboard runs on Render's free tier: if it is asleep, the first load takes about 50 seconds.

## The question

Brazilian household debt reached a record 50.1% of annual income in August 2026, and 29% of
income now goes to debt service. This project asks **where, among whom, and in which credit
products** defaults are rising, so lenders and policymakers can act on targeted evidence rather
than national averages.

## Key findings

| | |
|---|---|
| **3.97% → 6.17%** | default rate on household credit over 21 months |
| **48%** | of the increase in defaulted balances comes from rural credit and a legacy credit-card stock, not consumer lending |
| **21%** | default rate on revolving credit-card debt (+8.4 pp), the riskiest product |
| **3×** | the default rate of borrowers earning up to 1 minimum wage versus those earning 10–20 |
| **11% → 21%** | default rate at fintechs, which doubled their household loan book |
| **3.6%** | Paraíba: second-lowest rate in the country and the smallest increase of any state |

## Method

- **Collection:** resumable download of the yearly SCR.data ZIPs and the SGS REST API, with
  backoff and validation; monthly CSVs read straight from the archive and stored as Parquet.
- **Data quality:** accounting identities checked on every row; a legacy card balance with ~80%
  defaults and the rural portfolio handled as separate scopes; income bands compared only
  within each month because of reclassification jumps at the source; results validated against
  the official default series (0.25 pp average gap on a like-for-like free-credit basis; month-over-month changes correlate at 0.83).
- **Analysis:** balance-weighted descriptive statistics, start-vs-end comparisons by product,
  state, income, occupation and lender type, decomposition of the default increase, and lagged
  correlations with interest rates (levels vs. first differences, to avoid spurious correlation).
- **Delivery:** a Dash app deployed on Render and a Looker Studio dashboard, both on aggregated
  tables built with DuckDB.

## Stack

Python (pandas, DuckDB, matplotlib, Plotly, Dash), SQL, Parquet, Looker Studio, Render.

## Reproduce

```bash
python -m pip install -r requirements-analise.txt
python src/coletar_dados.py
python src/gerar_bases.py
python app.py
```

---

Gustavo Hortencio da Silva · economist (UFPB) · [GitHub](https://github.com/gstvhortencio)
