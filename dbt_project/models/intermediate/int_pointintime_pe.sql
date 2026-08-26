-- int_pointintime_pe: the lookahead-safe Value signal input. As-of join —
-- for each (ticker, price_date), use the MOST RECENT EPS report strictly
-- BEFORE that price date, never a report dated on or after it. This is the
-- one model in the whole project where getting the join direction wrong
-- would silently create a lookahead bug, so the join condition is the most
-- important line in this file: `e.REPORT_DATE < p.PRICE_DATE`.
--
-- EARNINGS_AVAILABILITY_LAG_DAYS (see docs/decisions.md) is currently 0 —
-- report_date itself is treated as the earliest date the market could have
-- known the number. A more conservative choice would push this out a few
-- days for filing/dissemination lag; changeable in one place if needed.

WITH eps_seed AS (
    SELECT
        ticker       AS TICKER,
        report_date  AS REPORT_DATE,
        trailing_eps AS TRAILING_EPS
    FROM {{ ref('pointintime_eps_history') }}
),
priced AS (
    SELECT
        p.TICKER,
        p.PRICE_DATE,
        p.CLOSE_PRICE,
        e.REPORT_DATE,
        e.TRAILING_EPS
    FROM {{ ref('stg_prices') }} p
    JOIN eps_seed e
        ON p.TICKER = e.TICKER
       AND e.REPORT_DATE < p.PRICE_DATE
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY p.TICKER, p.PRICE_DATE
        ORDER BY e.REPORT_DATE DESC
    ) = 1
)
SELECT
    TICKER,
    PRICE_DATE,
    CLOSE_PRICE,
    REPORT_DATE AS EPS_REPORT_DATE,
    TRAILING_EPS,
    ROUND(SAFE_DIVIDE(CLOSE_PRICE, TRAILING_EPS), 4) AS PE_RATIO
FROM priced
WHERE TRAILING_EPS > 0   -- negative/zero trailing EPS makes P/E meaningless — excluded, not clipped to a garbage value
