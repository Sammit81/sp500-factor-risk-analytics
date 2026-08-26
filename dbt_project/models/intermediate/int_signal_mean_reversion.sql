-- int_signal_mean_reversion: short-term reversal. Signal is the NEGATIVE of
-- the trailing 5-trading-day return — stocks that fell hardest recently get
-- the highest reversal score (expected to bounce). The sign flip keeps every
-- signal on the same convention: higher score = more attractive.

SELECT
    TICKER,
    PRICE_DATE,
    -1 * ROUND(
        SAFE_DIVIDE(
            CLOSE_PRICE - LAG(CLOSE_PRICE, 5) OVER (PARTITION BY TICKER ORDER BY PRICE_DATE),
            LAG(CLOSE_PRICE, 5) OVER (PARTITION BY TICKER ORDER BY PRICE_DATE)
        ), 6
    ) AS MEAN_REVERSION_SIGNAL
FROM {{ ref('stg_prices') }}
