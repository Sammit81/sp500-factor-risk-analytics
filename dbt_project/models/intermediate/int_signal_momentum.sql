-- int_signal_momentum: 12-1 month momentum (Jegadeesh-Titman convention) —
-- return from ~12 months ago to ~1 month ago, deliberately SKIPPING the most
-- recent month to avoid contaminating this signal with short-term reversal
-- (which is its own separate signal — combining them without the skip would
-- make the two signals partially redundant/correlated by construction).
--
-- Trading-day approximation, not exact calendar-month alignment: ~21 trading
-- days/month, ~252 trading days/year. Documented here, not hidden in the LAG
-- offsets — a real production system might align to actual month-end dates
-- instead.

SELECT
    TICKER,
    PRICE_DATE,
    ROUND(
        SAFE_DIVIDE(
            LAG(CLOSE_PRICE, 21)  OVER (PARTITION BY TICKER ORDER BY PRICE_DATE)
          - LAG(CLOSE_PRICE, 252) OVER (PARTITION BY TICKER ORDER BY PRICE_DATE),
            LAG(CLOSE_PRICE, 252) OVER (PARTITION BY TICKER ORDER BY PRICE_DATE)
        ), 6
    ) AS MOMENTUM_SIGNAL
FROM {{ ref('stg_prices') }}
