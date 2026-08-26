-- stg_prices: clean and type-cast the raw price data. No business logic here.

SELECT
    TICKER,
    NAME,
    CAST(PRICE_DATE AS DATE)          AS PRICE_DATE,
    ROUND(CAST(OPEN AS FLOAT64), 4)   AS OPEN_PRICE,
    ROUND(CAST(HIGH AS FLOAT64), 4)   AS HIGH_PRICE,
    ROUND(CAST(LOW AS FLOAT64), 4)    AS LOW_PRICE,
    ROUND(CAST(CLOSE AS FLOAT64), 4)  AS CLOSE_PRICE,
    CAST(VOLUME AS INT64)             AS VOLUME
FROM {{ source('raw', 'RAW_PRICES') }}
WHERE CLOSE IS NOT NULL
  AND CLOSE > 0
