-- fct_backtest_returns: grain = one row per strategy per trading day.
-- Relates to dim_strategy on Strategy and dim_date on Date.

SELECT
    STRATEGY      AS Strategy,
    RETURN_DATE   AS Date,
    DAILY_RETURN  AS DailyReturn
FROM {{ ref('stg_backtest_returns') }}
