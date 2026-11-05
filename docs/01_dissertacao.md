# Inadimplência e endividamento das famílias brasileiras

Gustavo Hortencio da Silva · novembro de 2026

## 1. Descrição do problema

As famílias brasileiras nunca estiveram tão endividadas. Segundo o Banco Central, o endividamento chegou a 50,1% da renda acumulada em 12 meses em agosto de 2026, recorde da série histórica. No mesmo mês, 29% da renda foi consumida só com o pagamento de juros e amortizações, também um recorde ([Gazeta do Povo, com dados do BCB](https://www.gazetadopovo.com.br/economia/endividamento-familias-brasileiras-bate-novo-recorde-aleta-banco-central/)).

O problema não é apenas ter dívida. Crédito bem usado financia uma casa, um curso ou um negócio. O problema é a combinação de três fatores:

- **Dívida cara:** a taxa média do crédito livre às famílias chegou a 64% ao ano em junho de 2026 ([O Povo, com dados do BCB](https://www.opovo.com.br/noticias/economia/2026/07/30/amp/juros-das-familias-seguem-elevados-e-chegam-a-64-ao-ano-diz-bc.html)).
- **Dívida concentrada nas modalidades mais caras:** o cartão de crédito aparece em 85,3% das famílias endividadas ([Peic/CNC, julho de 2026](https://mercadoeconsumo.com.br/06/08/2026/noticias/cnc-endividamento-das-familias-sobe-para-82-mas-inadimplencia-cai/)).
- **Incapacidade de pagar:** 84,2 milhões de brasileiros estavam inadimplentes em setembro de 2026, com R$ 597,4 bilhões em dívidas e média de R$ 7.093,83 por pessoa ([Serasa, via Mercado&Consumo](https://mercadoeconsumo.com.br/02/11/2026/economia/inadimplencia-atinge-recorde-de-842-milhoes-de-brasileiros/)).

O quadro também é desigual. Entre famílias com renda de até 3 salários mínimos, 38,5% têm contas em atraso. Acima de 10 salários mínimos, são 15,1% (Peic/CNC). A inadimplência não é um fenômeno uniforme: ela se concentra em certas faixas de renda, modalidades de crédito e regiões. É essa concentração que a análise de dados pode revelar.

## 2. Importância e relevância

O superendividamento afeta ao mesmo tempo as famílias, o sistema financeiro e a economia como um todo.

**Para as famílias.** Quando quase um terço da renda vai para o serviço da dívida, sobra pouco para necessidades básicas. Não por acaso, contas de água, luz e gás respondem por 20,32% das dívidas em atraso (Serasa). O nome negativado também fecha portas: dificulta alugar um imóvel, financiar um bem e, em alguns setores, até conseguir emprego.

**Para o sistema financeiro.** A inadimplência das famílias no crédito livre chegou a 8,1% da carteira em setembro de 2026, alta de 1,2 ponto percentual em 12 meses (BCB, série SGS 21112). Calotes maiores levam os bancos a cobrar juros mais altos de todos, inclusive de quem paga em dia. Juros mais altos, por sua vez, aumentam a chance de novos atrasos. O resultado é um ciclo que se retroalimenta.

**Para a economia.** O consumo das famílias é o maior componente do PIB brasileiro. Renda comprometida com dívidas significa menos consumo, menos vendas e crescimento mais lento, mesmo quando a renda cresce.

**Para as políticas públicas.** O próprio Banco Central acompanha o tema de perto e prepara medidas contra a concessão de crédito considerada predatória (Gazeta do Povo). Programas de renegociação e de educação financeira só funcionam bem se souberem onde está o problema. Por isso o tema é relevante agora e tem gente que decide com base nele.

## 3. Como a análise de dados pode ajudar

A análise de dados transforma uma média nacional assustadora em um mapa de onde, com quem e em qual tipo de crédito o risco se concentra. Sem esse mapa, as decisões de bancos e do governo são tomadas no escuro ou de forma genérica.

**Fonte principal.** O [SCR.data](https://dadosabertos.bcb.gov.br/dataset/scr_data), base aberta do Banco Central derivada do Sistema de Informações de Crédito, é atualizado mensalmente desde junho de 2012. O projeto usa os arquivos mensais de janeiro de 2025 a setembro de 2026, recortando apenas pessoas físicas. Cada linha traz saldos em reais (carteira ativa, carteira vencida por faixa de atraso, carteira inadimplida e ativo problemático), separados por:

- unidade da federação (27 UFs);
- modalidade e submodalidade de crédito (cartão rotativo, cheque especial, crédito pessoal consignado e não consignado, veículos, habitacional etc.);
- faixa de rendimento do cliente, em salários mínimos;
- natureza da ocupação (empregado privado, servidor, autônomo, MEI, aposentado etc.);
- segmento da instituição (banco, financeira, fintech, cooperativa etc.).

**Fontes complementares.** O SCR.data não traz juros nem dados macroeconômicos. Esses vêm de séries do Sistema Gerenciador de Séries Temporais (SGS) do Banco Central, detalhadas em [`02_fontes_e_coleta.md`](02_fontes_e_coleta.md).

**Atenção ao escopo.** O SCR.data cobre todo o crédito às famílias, livre (cartão, cheque especial, crédito pessoal, consignado, veículos) e direcionado (financiamento imobiliário, rural, BNDES). Como o financiamento imobiliário é grande e quase não atrasa, a taxa de inadimplência calculada no total é menor: 4,0% em janeiro de 2025, contra 5,7% do crédito livre no mesmo mês. Para comparar com os números oficiais, o projeto usa a série 21112 como referência.

**Perguntas que a análise responde:**

| Pergunta analítica | Como responder | Base | Quem usa a resposta |
| --- | --- | --- | --- |
| Em quais modalidades a inadimplência mais cresce? | Taxa de inadimplência (carteira inadimplida ÷ carteira ativa) por submodalidade, mês a mês | SCR.data | Bancos e fintechs: revisar limites e política de concessão |
| Quais estados e regiões estão mais expostos? | Mesma taxa por UF: ranking e evolução, com destaque para o Nordeste e a Paraíba | SCR.data | Governo e Procons: direcionar renegociação e educação financeira |
| Quais faixas de renda e ocupações são mais vulneráveis? | Taxa por faixa de rendimento × ocupação | SCR.data | Formuladores de política e áreas de risco de crédito |
| A inadimplência acompanha os juros com defasagem? | Taxa mensal contra juros (20740) e Selic (432), com correlação defasada de 0 a 6 meses; leitura exploratória, não causal | SCR.data + SGS | Analistas econômicos |
| Onde o crédito cresce rápido e a inadimplência sobe junto? | Crescimento real da carteira (deflacionada pelo IPCA) contra a variação da taxa, por produto e tipo de instituição | SCR.data + SGS | Reguladores: sinais de crédito predatório |

A análise não resolve o endividamento sozinha. O que ela faz é trocar ações genéricas por ações direcionadas: o banco aperta o crédito onde o risco realmente cresce, e o governo leva a renegociação para quem mais precisa.

## 4. Conclusão

O endividamento das famílias está em nível recorde, concentrado em crédito caro e distribuído de forma desigual entre rendas, modalidades e regiões. Os dados públicos para estudá-lo existem, são mensais e têm granularidade suficiente. Isso faz do tema uma problemática real, atual e tratável com análise de dados, com resultados úteis para bancos, governo e para as próprias famílias.

## Fontes

- [Banco Central — SCR.data (Dados Abertos)](https://dadosabertos.bcb.gov.br/dataset/scr_data) e [metodologia](https://www.bcb.gov.br/content/estabilidadefinanceira/scr/scr.data/scr_data_metodologia.pdf)
- [SGS 21112 — Inadimplência do crédito livre, PF](https://dadosabertos.bcb.gov.br/dataset/21112-inadimplencia-da-carteira-de-credito-com-recursos-livres---pessoas-fisicas---total)
- [SGS 29037 — Endividamento das famílias](https://dadosabertos.bcb.gov.br/en_AU/dataset/29037-endividamento-das-familias-com-o-sistema-financeiro-nacional-em-relacao-a-renda-acumulada-dos)
- [Gazeta do Povo — Endividamento das famílias bate novo recorde (29/10/2026)](https://www.gazetadopovo.com.br/economia/endividamento-familias-brasileiras-bate-novo-recorde-aleta-banco-central/)
- [O Povo — Juros das famílias chegam a 64% ao ano (30/07/2026)](https://www.opovo.com.br/noticias/economia/2026/07/30/amp/juros-das-familias-seguem-elevados-e-chegam-a-64-ao-ano-diz-bc.html)
- [Mercado&Consumo — Peic/CNC: endividamento sobe para 82% (06/08/2026)](https://mercadoeconsumo.com.br/06/08/2026/noticias/cnc-endividamento-das-familias-sobe-para-82-mas-inadimplencia-cai/)
- [Mercado&Consumo — Serasa: inadimplência atinge 84,2 milhões (02/11/2026)](https://mercadoeconsumo.com.br/02/11/2026/economia/inadimplencia-atinge-recorde-de-842-milhoes-de-brasileiros/)
