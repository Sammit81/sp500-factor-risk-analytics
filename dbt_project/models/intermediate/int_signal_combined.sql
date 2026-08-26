-- int_signal_combined: PHASE A VERSION — combines the 3 price-only signals.
-- Phase B adds VALUE_ZSCORE here and changes the eligibility rule to require
-- all 4. Coverage rule (see docs/decisions.md): a ticker is only eligible for
-- the combined score if EVERY signal is present that date — no partial
-- averaging over whichever signals happen to exist.

SELECT
    TICKER,
    PRICE_DATE,
    MOMENTUM_ZSCORE,
    MEAN_REVERSION_ZSCORE,
    LOW_VOL_ZSCORE,
    CASE
        WHEN MOMENTUM_ZSCORE IS NOT NULL
         AND MEAN_REVERSION_ZSCORE IS NOT NULL
         AND LOW_VOL_ZSCORE IS NOT NULL
        THEN (MOMENTUM_ZSCORE + MEAN_REVERSION_ZSCORE + LOW_VOL_ZSCORE) / 3
        ELSE NULL
    END AS COMBINED_SCORE,
    (
        MOMENTUM_ZSCORE IS NOT NULL
        AND MEAN_REVERSION_ZSCORE IS NOT NULL
        AND LOW_VOL_ZSCORE IS NOT NULL
    ) AS IS_ELIGIBLE
FROM {{ ref('int_signal_zscore') }}
