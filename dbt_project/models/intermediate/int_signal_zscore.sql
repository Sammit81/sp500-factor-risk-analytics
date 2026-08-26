-- int_signal_zscore: cross-sectional z-score of each raw signal, computed
-- WITHIN each date (across all ~500 tickers that day) — this is what makes
-- the signals comparable/combinable despite very different raw units and
-- scales. SAFE_DIVIDE guards against a zero cross-sectional stddev.

WITH signals AS (
    SELECT
        m.TICKER,
        m.PRICE_DATE,
        m.MOMENTUM_SIGNAL,
        r.MEAN_REVERSION_SIGNAL,
        v.LOW_VOL_SIGNAL,
        val.VALUE_SIGNAL
    FROM {{ ref('int_signal_momentum') }} m
    JOIN {{ ref('int_signal_mean_reversion') }} r
        ON m.TICKER = r.TICKER AND m.PRICE_DATE = r.PRICE_DATE
    JOIN {{ ref('int_signal_low_vol') }} v
        ON m.TICKER = v.TICKER AND m.PRICE_DATE = v.PRICE_DATE
    LEFT JOIN {{ ref('int_signal_value') }} val
        ON m.TICKER = val.TICKER AND m.PRICE_DATE = val.PRICE_DATE
)
SELECT
    TICKER,
    PRICE_DATE,
    MOMENTUM_SIGNAL,
    MEAN_REVERSION_SIGNAL,
    LOW_VOL_SIGNAL,
    VALUE_SIGNAL,
    SAFE_DIVIDE(
        MOMENTUM_SIGNAL - AVG(MOMENTUM_SIGNAL) OVER (PARTITION BY PRICE_DATE),
        STDDEV(MOMENTUM_SIGNAL) OVER (PARTITION BY PRICE_DATE)
    ) AS MOMENTUM_ZSCORE,
    SAFE_DIVIDE(
        MEAN_REVERSION_SIGNAL - AVG(MEAN_REVERSION_SIGNAL) OVER (PARTITION BY PRICE_DATE),
        STDDEV(MEAN_REVERSION_SIGNAL) OVER (PARTITION BY PRICE_DATE)
    ) AS MEAN_REVERSION_ZSCORE,
    SAFE_DIVIDE(
        LOW_VOL_SIGNAL - AVG(LOW_VOL_SIGNAL) OVER (PARTITION BY PRICE_DATE),
        STDDEV(LOW_VOL_SIGNAL) OVER (PARTITION BY PRICE_DATE)
    ) AS LOW_VOL_ZSCORE,
    SAFE_DIVIDE(
        VALUE_SIGNAL - AVG(VALUE_SIGNAL) OVER (PARTITION BY PRICE_DATE),
        STDDEV(VALUE_SIGNAL) OVER (PARTITION BY PRICE_DATE)
    ) AS VALUE_ZSCORE
FROM signals
