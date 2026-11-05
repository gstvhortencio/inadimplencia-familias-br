-- =====================================================================
-- Consultas SQL da EDA (DuckDB), direto sobre os Parquets mensais.
--
-- Como rodar: pelo notebook 02_eda.ipynb, que executa cada bloco, ou
-- colando um bloco no DuckDB CLI a partir da raiz do repositório.
--
-- Taxa de inadimplência = carteira inadimplida / carteira ativa.
-- Cada consulta começa com um comentário numerado [N].
-- =====================================================================

-- [1] Visão geral: linhas, carteira e taxa por mês (pessoas físicas)
SELECT
    data_base                                                    AS mes,
    COUNT(*)                                                     AS linhas,
    ROUND(SUM(carteira_ativa) / 1e9, 1)                          AS carteira_bi,
    ROUND(100 * SUM(carteira_inadimplencia) / SUM(carteira_ativa), 2) AS taxa_inad_pct
FROM read_parquet('dados/scr_pf/*.parquet')
GROUP BY 1
ORDER BY 1;

-- [2] Checagem de consistência: carteira ativa = a vencer + vencida
SELECT
    COUNT(*)                                                     AS linhas,
    SUM(CASE WHEN ABS(carteira_ativa - (carteira_a_vencer + carteira_vencida)) > 1
             THEN 1 ELSE 0 END)                                  AS linhas_inconsistentes,
    SUM(CASE WHEN carteira_inadimplencia < vencido_acima_de_90_dias - 1
             THEN 1 ELSE 0 END)                                  AS inadimplida_menor_que_vencido_90d,
    ROUND(100 * AVG(CASE WHEN numero_de_operacoes IS NULL THEN 1 ELSE 0 END), 1)
                                                                 AS pct_operacoes_suprimidas
FROM read_parquet('dados/scr_pf/*.parquet');

-- [3] Submodalidades mais arriscadas no último mês (carteira mínima de R$ 1 bi)
SELECT
    submodalidade,
    ROUND(SUM(carteira_ativa) / 1e9, 1)                          AS carteira_bi,
    ROUND(100 * SUM(carteira_inadimplencia) / SUM(carteira_ativa), 2) AS taxa_inad_pct
FROM read_parquet('dados/scr_pf/*.parquet')
WHERE data_base = (SELECT MAX(data_base) FROM read_parquet('dados/scr_pf/*.parquet'))
GROUP BY 1
HAVING SUM(carteira_ativa) >= 1e9
ORDER BY taxa_inad_pct DESC
LIMIT 15;

-- [4] Variação da taxa por UF entre o primeiro e o último mês,
--     sem crédito rural e sem o saldo legado de cartão "não migrado"
WITH base AS (
    SELECT data_base, uf, carteira_ativa, carteira_inadimplencia
    FROM read_parquet('dados/scr_pf/*.parquet')
    WHERE modalidade NOT LIKE 'Financiamentos rurais%'
      AND submodalidade NOT IN ('Cartão de crédito - não migrado', 'Financiamentos agroindustriais')
),
extremos AS (
    SELECT MIN(data_base) AS ini, MAX(data_base) AS fim FROM base
),
por_uf AS (
    SELECT
        uf,
        100 * SUM(carteira_inadimplencia) FILTER (WHERE data_base = (SELECT ini FROM extremos))
            / SUM(carteira_ativa)          FILTER (WHERE data_base = (SELECT ini FROM extremos)) AS taxa_ini,
        100 * SUM(carteira_inadimplencia) FILTER (WHERE data_base = (SELECT fim FROM extremos))
            / SUM(carteira_ativa)          FILTER (WHERE data_base = (SELECT fim FROM extremos)) AS taxa_fim
    FROM base
    GROUP BY uf
)
SELECT uf, ROUND(taxa_ini, 2) AS taxa_ini, ROUND(taxa_fim, 2) AS taxa_fim,
       ROUND(taxa_fim - taxa_ini, 2) AS variacao_pp,
       RANK() OVER (ORDER BY taxa_fim DESC) AS ranking
FROM por_uf
ORDER BY ranking;

-- [5] Quanto cada tipo de instituição contribuiu para o aumento do saldo inadimplido
WITH extremos AS (
    SELECT MIN(data_base) AS ini, MAX(data_base) AS fim FROM read_parquet('dados/scr_pf/*.parquet')
)
SELECT
    segmento,
    ROUND(SUM(carteira_inadimplencia) FILTER (WHERE data_base = (SELECT fim FROM extremos)) / 1e9
        - SUM(carteira_inadimplencia) FILTER (WHERE data_base = (SELECT ini FROM extremos)) / 1e9, 1)
        AS aumento_inadimplido_bi
FROM read_parquet('dados/scr_pf/*.parquet')
GROUP BY 1
ORDER BY 2 DESC;

-- [6] Taxa por faixa de renda e ocupação no último mês (tabela cruzada)
SELECT
    porte                                                        AS renda,
    cnae_ocupacao                                                AS ocupacao,
    ROUND(SUM(carteira_ativa) / 1e9, 1)                          AS carteira_bi,
    ROUND(100 * SUM(carteira_inadimplencia) / SUM(carteira_ativa), 2) AS taxa_inad_pct
FROM read_parquet('dados/scr_pf/*.parquet')
WHERE data_base = (SELECT MAX(data_base) FROM read_parquet('dados/scr_pf/*.parquet'))
GROUP BY 1, 2
HAVING SUM(carteira_ativa) >= 5e9
ORDER BY taxa_inad_pct DESC
LIMIT 20;

-- [7] Média móvel de 3 meses da taxa nacional (função de janela)
WITH mensal AS (
    SELECT data_base AS mes,
           100 * SUM(carteira_inadimplencia) / SUM(carteira_ativa) AS taxa
    FROM read_parquet('dados/scr_pf/*.parquet')
    GROUP BY 1
)
SELECT mes, ROUND(taxa, 2) AS taxa,
       ROUND(AVG(taxa) OVER (ORDER BY mes ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS media_movel_3m,
       ROUND(taxa - LAG(taxa, 12) OVER (ORDER BY mes), 2) AS variacao_12m_pp
FROM mensal
ORDER BY mes;
