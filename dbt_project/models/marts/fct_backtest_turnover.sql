-- fct_backtest_turnover: grain = one row per strategy per rebalance date.
-- Relates to dim_strategy on Strategy and dim_date on RebalanceDate.

SELECT
    STRATEGY        AS Strategy,
    REBALANCE_DATE   AS RebalanceDate,
    TURNOVER          AS Turnover,
    COST               AS Cost,
    N_HOLDINGS          AS NHoldings
FROM {{ ref('stg_backtest_turnover') }}
