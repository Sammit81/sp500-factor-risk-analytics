-- fct_price_returns: grain = one row per ticker per trading day.

SELECT
    TICKER,
    PRICE_DATE,
    CLOSE_PRICE,
    VOLUME,
    DAILY_RETURN
FROM {{ ref('int_daily_returns') }}
