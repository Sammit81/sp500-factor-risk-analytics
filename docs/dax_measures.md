# DAX Measures Reference

All measures below are written against the Power BI layer added to `SP500_FACTOR_ANALYTICS`:
`dim_date`, `dim_strategy`, `fct_backtest_returns`, `fct_backtest_turnover` — plus the existing
`dim_ticker`, `fct_signal_scores`, `fct_price_returns` for stock-level drill-down.

**Setup required in Power BI Desktop before these work:**
1. Connect to BigQuery, import all 7 tables from `SP500_FACTOR_ANALYTICS`.
2. Relationships: `fct_backtest_returns[Strategy]` → `dim_strategy[Strategy]`, `fct_backtest_returns[Date]` → `dim_date[Date]`; same two from `fct_backtest_turnover` (its date column is `RebalanceDate`, still relates to `dim_date[Date]`). Separately: `fct_signal_scores[TICKER]`/`fct_price_returns[TICKER]` → `dim_ticker[TICKER]`, and their `PRICE_DATE` → `dim_date[Date]`.
3. **Mark `dim_date` as a Date Table** (Modeling → Mark as Date Table → key column `Date`) — every time-intelligence measure below depends on this.

---

## 1. Base measures

```DAX
Total Trading Days = COUNTROWS(fct_backtest_returns)

Cumulative Return =
PRODUCTX(fct_backtest_returns, 1 + fct_backtest_returns[DailyReturn]) - 1
```

`PRODUCTX` compounds daily returns correctly (multiplicative), unlike summing daily returns, which
would understate/overstate compounding — worth being able to explain the distinction if asked.

---

## 2. Time intelligence

```DAX
YTD Return =
VAR DatesInPeriod = DATESYTD('dim_date'[Date])
RETURN
    PRODUCTX(DatesInPeriod, 1 + CALCULATE(SUM(fct_backtest_returns[DailyReturn]))) - 1

QTD Return =
VAR DatesInPeriod = DATESQTD('dim_date'[Date])
RETURN
    PRODUCTX(DatesInPeriod, 1 + CALCULATE(SUM(fct_backtest_returns[DailyReturn]))) - 1

Rolling 12-Month Return =
VAR DatesInPeriod = DATESINPERIOD('dim_date'[Date], MAX('dim_date'[Date]), -12, MONTH)
RETURN
    PRODUCTX(DatesInPeriod, 1 + CALCULATE(SUM(fct_backtest_returns[DailyReturn]))) - 1

Prior Year Return (Same Period) =
CALCULATE([YTD Return], SAMEPERIODLASTYEAR('dim_date'[Date]))

YoY Return Growth = [YTD Return] - [Prior Year Return (Same Period)]
```

`PRODUCTX` iterating a date table with `CALCULATE(SUM(...))` inside is the standard context-transition
idiom (same shape as `SUMX`/`AVERAGEX` with `CALCULATE` inside) — each row's `CALCULATE` re-filters
`fct_backtest_returns` to that specific date via the `dim_date` relationship before summing.

---

## 3. Variance-to-target (vs. real SPY)

```DAX
Benchmark Return (SPY) =
CALCULATE(
    [YTD Return],
    REMOVEFILTERS(dim_strategy),
    dim_strategy[Strategy] = "SPY (benchmark)"
)

Variance to Benchmark = [YTD Return] - [Benchmark Return (SPY)]

Variance to Benchmark % =
DIVIDE([Variance to Benchmark], ABS([Benchmark Return (SPY)]))
```

Same `REMOVEFILTERS` + re-filter-to-a-fixed-member pattern as the Irish Market Intelligence project —
reusable for any actual budget/target table, not just a benchmark.

---

## 4. Rolling volatility

```DAX
Rolling 30-Day Volatility (Annualised) =
VAR DatesInPeriod = DATESINPERIOD('dim_date'[Date], MAX('dim_date'[Date]), -30, DAY)
RETURN
    CALCULATE(
        STDEVX.P(fct_backtest_returns, fct_backtest_returns[DailyReturn]),
        DatesInPeriod
    ) * SQRT(252)
```

---

## 5. Risk/performance scorecard (Sharpe, Max Drawdown, VaR — computed in DAX)

`backtest/metrics.py` already computes these in Python for the report; these DAX equivalents exist
specifically to demonstrate the technique live inside Power BI, filterable by any slicer on the page
(date range, strategy) without re-running Python.

```DAX
Sharpe Ratio (Annualised) =
VAR AvgDailyReturn = AVERAGE(fct_backtest_returns[DailyReturn])
VAR StdDevDailyReturn = STDEVX.P(fct_backtest_returns, fct_backtest_returns[DailyReturn])
VAR RiskFreeDaily = 0.04 / 252
RETURN
    DIVIDE(AvgDailyReturn - RiskFreeDaily, StdDevDailyReturn) * SQRT(252)

Historical VaR 95% =
PERCENTILEX.INC(fct_backtest_returns, fct_backtest_returns[DailyReturn], 0.05)

Max Drawdown =
VAR ReturnHistory =
    ADDCOLUMNS(
        SUMMARIZE(fct_backtest_returns, fct_backtest_returns[Date]),
        "@CumReturn",
            VAR CurrentDate = fct_backtest_returns[Date]
            RETURN
                CALCULATE(
                    PRODUCTX(fct_backtest_returns, 1 + fct_backtest_returns[DailyReturn]),
                    fct_backtest_returns[Date] <= CurrentDate
                )
    )
VAR WithRunningMax =
    ADDCOLUMNS(
        ReturnHistory,
        "@RunningMax",
            VAR CurrentDate = [Date]
            RETURN CALCULATE(MAX([@CumReturn]), FILTER(ReturnHistory, [Date] <= CurrentDate))
    )
RETURN
    MINX(WithRunningMax, DIVIDE([@CumReturn] - [@RunningMax], [@RunningMax]))
```

`Max Drawdown` is the most advanced measure in this project: a running cumulative-product column,
then a running-max column over *that*, then the drawdown at every point — three layers of row context
built with `ADDCOLUMNS`, no `EARLIER()`. Worth being able to walk through each `ADDCOLUMNS` layer
individually if asked "explain this measure."

---

## 6. Turnover & cost (from `fct_backtest_turnover`)

```DAX
Total Transaction Cost = SUM(fct_backtest_turnover[Cost])

Avg Turnover per Rebalance = AVERAGE(fct_backtest_turnover[Turnover])

Number of Rebalances = DISTINCTCOUNT(fct_backtest_turnover[RebalanceDate])

Avg Cost per Rebalance (bps) =
DIVIDE([Total Transaction Cost], [Number of Rebalances]) * 10000
```

`Cost Drag (Annualised)` is deliberately not included here: `Cost` in `fct_backtest_turnover` is a
per-rebalance return-drag already netted into `DailyReturn` upstream in `backtest/engine.py`, so
`fct_backtest_returns[DailyReturn]` is already net-of-cost. Grossing it back up to a clean annualised
drag figure needs the gross (no-cost) return series alongside it, which isn't persisted today — worth
flagging as a possible v2 addition (persist both gross and net return columns) rather than faking the
number with a proxy calculation.

---

## 7. Row-Level Security (RLS)

**Static roles** (Modeling → Manage Roles, filter expression on `dim_strategy`):

| Role name | DAX filter on `dim_strategy` | Who sees what |
|---|---|---|
| `Standalone Analyst` | `[StrategyType] = "Standalone Signal"` | Only the 4 individual factors — not the combined score or benchmark |
| `Portfolio Manager` | `[StrategyType] IN {"Combined", "Benchmark"}` | The combined strategy and SPY, not individual-factor detail |
| `Risk Team (Full Access)` | *(no filter expression — leave blank)* | Every strategy, including the long-short diagnostic |

Test with **Modeling → View As** before publishing. As with the Irish Market Intelligence project,
RLS defined in Desktop does nothing until roles are assigned to real users/groups in Power BI
Service after publishing.
