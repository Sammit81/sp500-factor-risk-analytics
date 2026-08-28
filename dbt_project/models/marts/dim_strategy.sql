-- dim_strategy: one row per strategy, classified into a StrategyType so
-- Power BI can filter/group standalone signals separately from the
-- combined score, the long-short diagnostic, and the SPY benchmark.

SELECT DISTINCT
    STRATEGY                                                            AS Strategy,
    CASE
        WHEN STRATEGY = 'Combined (all 4)'         THEN 'Combined'
        WHEN STRATEGY = 'SPY (benchmark)'          THEN 'Benchmark'
        WHEN STRATEGY = 'Long-Short (diagnostic)'  THEN 'Diagnostic'
        ELSE 'Standalone Signal'
    END                                                                  AS StrategyType
FROM {{ ref('stg_backtest_returns') }}
