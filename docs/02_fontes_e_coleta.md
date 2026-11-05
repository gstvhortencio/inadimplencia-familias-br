# Fontes de dados e método de coleta

Todas as fontes são **públicas, gratuitas e não confidenciais**, publicadas pelo Banco Central do
Brasil sob licença aberta. Nenhum dado identifica pessoas ou contratos.

## Resumo

| Fonte | O que traz | Tipo de dado | Formato | Acesso | Periodicidade |
|---|---|---|---|---|---|
| [SCR.data](https://dadosabertos.bcb.gov.br/dataset/scr_data) | Saldos de crédito por UF, produto, renda, ocupação e tipo de instituição | Estruturado, tabular | CSV dentro de ZIP anual | Download direto (HTTP) | Mensal, desde jun/2012 |
| [SGS](https://www3.bcb.gov.br/sgspub/) | Séries macroeconômicas e de crédito (juros, Selic, IPCA, endividamento) | Estruturado, série temporal | JSON | API REST | Mensal (Selic diária) |

## 1. SCR.data: Sistema de Informações de Crédito

**Descrição.** O SCR é o cadastro em que todas as instituições financeiras registram as operações
de crédito acima de R$ 200. O SCR.data é a versão aberta e agregada: cada linha soma as operações
que compartilham a mesma combinação de atributos, sem identificar clientes.

**Dimensões usadas:** mês, UF, segmento da instituição (banco, financeira, fintech, cooperativa
etc.), tipo de cliente (PF/PJ), ocupação (PF), faixa de rendimento em salários mínimos (PF),
modalidade e submodalidade de crédito, origem do recurso e indexador.

**Métricas usadas (R$):** carteira ativa, carteira a vencer, carteira vencida (15 a 90 dias e acima
de 90 dias), carteira inadimplida e ativo problemático. A **taxa de inadimplência** do projeto é
carteira inadimplida ÷ carteira ativa. A carteira inadimplida soma o saldo inteiro das operações
com atraso superior a 90 dias.

**Volume.** Cerca de 310 mil linhas por mês (PF + PJ) e uns 100 MB de CSV por mês. Depois de filtrar
pessoas físicas e converter para Parquet, ficam cerca de 185 mil linhas e 8 MB por mês. São
**3,9 milhões de linhas** no período analisado (jan/2025 a set/2026).

**Acesso e coleta.** É um download direto, sem autenticação, de um ZIP por ano:

```
https://www.bcb.gov.br/pda/desig/scrdata_{ANO}.zip
```

O script `src/coletar_dados.py`:

1. baixa o ZIP de cada ano em blocos, **retomando de onde parou** se a conexão cair (cabeçalho
   HTTP `Range`), com espera progressiva entre tentativas (5 s, 10 s, 20 s... até 2 min) e
   validação do arquivo antes de considerá-lo pronto;
2. lê cada CSV mensal **direto de dentro do ZIP**, em blocos de 200 mil linhas, sem descompactar;
3. trata o formato brasileiro (separador `;`, vírgula decimal, BOM UTF-8);
4. filtra pessoas físicas e converte o número de operações `-1` (suprimido por sigilo) em ausente;
5. salva um Parquet por mês em `dados/scr_pf/`.

**Documentação oficial:** [metodologia do SCR.data](https://www.bcb.gov.br/content/estabilidadefinanceira/scr/scr.data/scr_data_metodologia.pdf).

## 2. SGS: Sistema Gerenciador de Séries Temporais

**Descrição.** Repositório oficial de séries econômicas do Banco Central. Complementa o SCR.data com
o que ele não tem: juros, inflação e indicadores macro do endividamento.

**Acesso e coleta.** API REST pública, uma chamada por série:

```
https://api.bcb.gov.br/dados/serie/bcdata.sgs.{código}/dados?formato=json&dataInicial=01/01/2024&dataFinal=31/12/2026
```

O mesmo script consulta as nove séries abaixo, com pausa de 2 s entre chamadas e novas tentativas
automáticas em caso de erro, reduz a Selic (diária) ao último valor de cada mês e salva tudo em
`dados/sgs.parquet`.

| Código | Série | Uso no projeto |
|---|---|---|
| [20740](https://dadosabertos.bcb.gov.br/dataset/20740-taxa-media-de-juros-das-operacoes-de-credito-com-recursos-livres---pessoas-fisicas---total) | Taxa média de juros, crédito livre PF | Pergunta 4 (juros × inadimplência) |
| 432 | Selic meta | Pergunta 4 |
| 433 | IPCA mensal | Deflacionar saldos (pergunta 5) |
| [21112](https://dadosabertos.bcb.gov.br/dataset/21112-inadimplencia-da-carteira-de-credito-com-recursos-livres---pessoas-fisicas---total) | Inadimplência, crédito livre PF | Validação |
| [21129](https://dadosabertos.bcb.gov.br/dataset/21129-inadimplencia-da-carteira-de-credito-com-recursos-livres---pessoas-fisicas---cartao-de-credit) | Inadimplência, crédito livre PF, cartão | Validação |
| [29037](https://dadosabertos.bcb.gov.br/en_AU/dataset/29037-endividamento-das-familias-com-o-sistema-financeiro-nacional-em-relacao-a-renda-acumulada-dos) | Endividamento das famílias (% da renda em 12 meses) | Contexto |
| [29038](https://dadosabertos.bcb.gov.br/dataset/29038-endividamento-das-familias-com-o-sistema-financeiro-nacional-exceto-credito-habitacional-em-r) | Endividamento exceto habitacional | Contexto |
| [29034](https://dadosabertos.bcb.gov.br/dataset/29034-comprometimento-de-renda-das-familias-com-o-servico-da-divida-com-o-sistema-financeiro-nacion) | Comprometimento de renda com o serviço da dívida | Contexto |
| [29035](https://dadosabertos.bcb.gov.br/dataset/29035-comprometimento-de-renda-das-familias-com-o-servico-da-divida-com-o-sistema-financeiro-nacion) | Comprometimento de renda, exceto habitacional | Contexto |

## Por que não houve scraping

As duas fontes oferecem acesso estruturado e oficial (download e API), então não foi preciso raspar
páginas. Isso dá dados mais confiáveis, reprodutíveis e de acordo com os termos de uso das fontes.

## Como reproduzir

```bash
python -m pip install -r requirements-analise.txt
python src/coletar_dados.py      # ~300 MB de download; gera dados/scr_pf/*.parquet e dados/sgs.parquet
python src/gerar_bases.py        # gera dados/agregados/*.csv (Looker Studio e dashboard)
```
