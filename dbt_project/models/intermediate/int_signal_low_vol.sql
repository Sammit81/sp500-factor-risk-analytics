-- int_signal_low_vol: NEGATIVE of trailing 30-day annualised volatility —
-- lower risk = higher score, same "higher is better" convention as every
-- other signal (the well-documented low-vol anomaly: lower-risk stocks have
-- historically had better RISK-ADJUSTED, not necessarily raw, returns).

SELECT
    TICKER,
    PRICE_DATE,
    -1 * ROUND(
        STDDEV(DAILY_RETURN) OVER (
            PARTITION BY TICKER
            ORDER BY PRICE_DATE
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) * SQRT(252), 6
    ) AS LOW_VOL_SIGNAL
FROM {{ ref('int_daily_returns') }}
