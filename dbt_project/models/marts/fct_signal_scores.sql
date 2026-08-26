-- fct_signal_scores: grain = one row per ticker per trading day. SPY also
-- gets rows here (it flows through the same signal pipeline) but the
-- backtest engine only uses this for the investable universe, not for SPY —
-- SPY's own "signal" values are unused, harmless byproduct of a shared pipeline.

SELECT
    TICKER,
    PRICE_DATE,
    MOMENTUM_ZSCORE,
    MEAN_REVERSION_ZSCORE,
    LOW_VOL_ZSCORE,
    VALUE_ZSCORE,
    COMBINED_SCORE,
    IS_ELIGIBLE
FROM {{ ref('int_signal_combined') }}
