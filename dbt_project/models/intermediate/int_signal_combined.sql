-- int_signal_combined: PHASE B — all 4 signals. Coverage rule (see
-- docs/decisions.md): a ticker is only eligible for the combined score if
-- EVERY signal is present that date — no partial averaging over whichever
-- signals happen to exist. Value will have real gaps (limited EPS history
-- depth per ticker), so IS_ELIGIBLE will be false for a meaningful chunk of
-- (ticker, date) rows — expected, not a bug.

SELECT
    TICKER,
    PRICE_DATE,
    MOMENTUM_ZSCORE,
    MEAN_REVERSION_ZSCORE,
    LOW_VOL_ZSCORE,
    VALUE_ZSCORE,
    CASE
        WHEN MOMENTUM_ZSCORE IS NOT NULL
         AND MEAN_REVERSION_ZSCORE IS NOT NULL
         AND LOW_VOL_ZSCORE IS NOT NULL
         AND VALUE_ZSCORE IS NOT NULL
        THEN (MOMENTUM_ZSCORE + MEAN_REVERSION_ZSCORE + LOW_VOL_ZSCORE + VALUE_ZSCORE) / 4
        ELSE NULL
    END AS COMBINED_SCORE,
    (
        MOMENTUM_ZSCORE IS NOT NULL
        AND MEAN_REVERSION_ZSCORE IS NOT NULL
        AND LOW_VOL_ZSCORE IS NOT NULL
        AND VALUE_ZSCORE IS NOT NULL
    ) AS IS_ELIGIBLE
FROM {{ ref('int_signal_zscore') }}
