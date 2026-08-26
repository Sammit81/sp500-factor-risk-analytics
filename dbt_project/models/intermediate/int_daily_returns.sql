-- int_daily_returns: daily return per ticker. LAG() looks at the previous row.

WITH lagged AS (
    SELECT
        TICKER,
        NAME,
        PRICE_DATE,
        CLOSE_PRICE,
        VOLUME,
        LAG(CLOSE_PRICE) OVER (PARTITION BY TICKER ORDER BY PRICE_DATE) AS PREV_CLOSE
    FROM {{ ref('stg_prices') }}
)
SELECT
    TICKER,
    NAME,
    PRICE_DATE,
    CLOSE_PRICE,
    VOLUME,
    PREV_CLOSE,
    ROUND((CLOSE_PRICE - PREV_CLOSE) / NULLIF(PREV_CLOSE, 0), 6) AS DAILY_RETURN
FROM lagged
WHERE PREV_CLOSE IS NOT NULL
