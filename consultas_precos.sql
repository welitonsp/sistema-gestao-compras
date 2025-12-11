-- ============================================================================
-- CONSULTAS PADRÃO - GESTÃO DE COMPRAS / HISTÓRICO DE PREÇOS
-- Banco: Neon (PostgreSQL)
--
-- Tabelas usadas:
--   produtos (
--       id_produto   TEXT PRIMARY KEY,
--       descricao    TEXT NOT NULL,
--       created_at   TIMESTAMPTZ DEFAULT NOW()
--   )
--
--   historico_precos (
--       id             SERIAL PRIMARY KEY,
--       id_produto     TEXT NOT NULL REFERENCES produtos(id_produto),
--       data_nota      DATE NOT NULL,
--       mercado        TEXT NOT NULL,
--       quantidade     NUMERIC(12,3) NOT NULL,
--       preco_unitario NUMERIC(12,2) NOT NULL,
--       preco_total    NUMERIC(12,2) NOT NULL,
--       created_at     TIMESTAMPTZ DEFAULT NOW()
--   )
--
-- Você pode abrir esse arquivo no Neon Console ou em qualquer cliente SQL
-- (DBeaver, Beekeeper, etc.) e executar as consultas conforme a necessidade.
-- ============================================================================


-- 1) Último preço registrado por produto
--    Mostra, para cada produto, o registro mais recente de preço.

SELECT
    p.id_produto,
    p.descricao,
    hp.mercado,
    hp.data_nota,
    hp.preco_unitario,
    hp.preco_total
FROM produtos p
JOIN LATERAL (
    SELECT h.*
    FROM historico_precos h
    WHERE h.id_produto = p.id_produto
    ORDER BY h.data_nota DESC, h.created_at DESC, h.id DESC
    LIMIT 1
) hp ON TRUE
ORDER BY p.descricao;


-- 2) Histórico de preços de um produto específico
--    Troque o valor do id_produto pelo código desejado (ex.: '789110').

SELECT
    h.data_nota,
    h.mercado,
    h.quantidade,
    h.preco_unitario,
    h.preco_total
FROM historico_precos h
WHERE h.id_produto = '789110'   -- <<< ALTERE AQUI PARA O CÓDIGO DO PRODUTO
ORDER BY h.data_nota;


-- 3) Produtos com maior variação de preço (mínimo x máximo)
--    Mostra quais produtos mais oscilaram de preço no histórico.

WITH stats AS (
    SELECT
        h.id_produto,
        MIN(h.preco_unitario) AS preco_min,
        MAX(h.preco_unitario) AS preco_max,
        MAX(h.preco_unitario) - MIN(h.preco_unitario) AS variacao_absoluta,
        CASE
            WHEN MIN(h.preco_unitario) = 0 THEN NULL
            ELSE (MAX(h.preco_unitario) - MIN(h.preco_unitario))
                 / MIN(h.preco_unitario) * 100
        END AS variacao_percentual
    FROM historico_precos h
    GROUP BY h.id_produto
)
SELECT
    s.id_produto,
    p.descricao,
    s.preco_min,
    s.preco_max,
    s.variacao_absoluta,
    ROUND(s.variacao_percentual, 2) AS variacao_percentual
FROM stats s
JOIN produtos p ON p.id_produto = s.id_produto
WHERE s.preco_min IS NOT NULL
  AND s.preco_max IS NOT NULL
ORDER BY s.variacao_absoluta DESC
LIMIT 50;


-- 4) Preço médio mensal por produto
--    Ajuda a ver como o preço se comporta ao longo dos meses.

SELECT
    h.id_produto,
    p.descricao,
    DATE_TRUNC('month', h.data_nota)::date AS mes,
    AVG(h.preco_unitario) AS preco_medio
FROM historico_precos h
JOIN produtos p ON p.id_produto = h.id_produto
GROUP BY
    h.id_produto,
    p.descricao,
    DATE_TRUNC('month', h.data_nota)
ORDER BY
    p.descricao,
    mes;


-- 5) Comparar preço médio por mercado para produtos filtrados
--    Use o ILIKE para filtrar (ex: produtos que contenham "CAFE", "LEITE").
--    Altere '%CAFE%' para o termo desejado.

SELECT
    p.id_produto,
    p.descricao,
    h.mercado,
    AVG(h.preco_unitario) AS preco_medio,
    COUNT(*) AS qtd_registros
FROM historico_precos h
JOIN produtos p ON p.id_produto = h.id_produto
WHERE p.descricao ILIKE '%CAFE%'   -- <<< ALTERE O TEXTO PARA OUTRO FILTRO
GROUP BY
    p.id_produto,
    p.descricao,
    h.mercado
ORDER BY
    p.descricao,
    h.mercado;


-- 6) Itens comprados em uma data específica
--    Informe a data da nota (formato ISO: AAAA-MM-DD).

SELECT
    h.data_nota,
    h.mercado,
    p.id_produto,
    p.descricao,
    h.quantidade,
    h.preco_unitario,
    h.preco_total
FROM historico_precos h
JOIN produtos p ON p.id_produto = h.id_produto
WHERE h.data_nota = DATE '2025-04-07'   -- <<< ALTERE A DATA AQUI
ORDER BY
    p.descricao;


-- 7) Últimas 100 compras registradas (independente de produto)
--    Mostra o histórico mais recente.

SELECT
    h.data_nota,
    h.mercado,
    p.id_produto,
    p.descricao,
    h.quantidade,
    h.preco_unitario,
    h.preco_total,
    h.created_at
FROM historico_precos h
JOIN produtos p ON p.id_produto = h.id_produto
ORDER BY
    h.data_nota DESC,
    h.created_at DESC,
    h.id DESC
LIMIT 100;


-- 8) Resumo geral por produto (quantidade total e valor total comprado)
--    Ajuda a ver em quais produtos você mais investe ao longo do tempo.

SELECT
    h.id_produto,
    p.descricao,
    SUM(h.quantidade) AS quantidade_total,
    AVG(h.preco_unitario) AS preco_medio,
    SUM(h.preco_total) AS valor_total
FROM historico_precos h
JOIN produtos p ON p.id_produto = h.id_produto
GROUP BY
    h.id_produto,
    p.descricao
ORDER BY
    valor_total DESC;
