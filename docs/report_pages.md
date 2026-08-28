# Report Page Spec

Four pages, same structure as the sibling Irish Market Intelligence model
(executive summary, trend analysis, drill-down detail, KPI scorecard), adapted to this project's
actual unit of analysis: **strategies being compared**, not individual tickers. Ticker-level detail
still exists (via `fct_signal_scores`/`fct_price_returns`) and shows up on the drill-down page only.

---

## Page 1 — Executive Summary

**Purpose**: one-glance "did the combined signal actually work" — the single most important claim
this project makes.

- **KPI cards (top row)**, filtered to `Strategy = "Combined (all 4)"` by default: `[YTD Return]`, `[Sharpe Ratio (Annualised)]`, `[Max Drawdown]`, `[Variance to Benchmark]`.
- **Bar chart — Strategy comparison**: `dim_strategy[Strategy]` on axis, `[Sharpe Ratio (Annualised)]` as value, sorted descending, excluding `Long-Short (diagnostic)` (internal-only signal, not a real strategy — filter it out of this page explicitly). This is the chart that answers "does combining 4 signals beat any single one" at a glance.
- **Strategy slicer**: `dim_strategy[Strategy]`, drives every visual on the page.
- **Line chart — Cumulative return, all strategies**: `dim_date[Date]` on axis, `[Cumulative Return]` as value, legend by `dim_strategy[Strategy]` — the growth-of-$1 chart, the single visual most people expect first from a backtest report.

## Page 2 — Trend Analysis

**Purpose**: time-series depth for one selected strategy against the benchmark.

- **Strategy slicer**: `dim_strategy[Strategy]`, single-select (default `Combined (all 4)`).
- **Line chart — Strategy vs. SPY**: `[Cumulative Return]` for the selected strategy plotted alongside `[Benchmark Return (SPY)]`'s cumulative equivalent, `dim_date[Date]` on the shared axis.
- **Area chart — Rolling drawdown**: a `Rolling Max Drawdown` measure (same `ADDCOLUMNS` pattern as `[Max Drawdown]` in `docs/dax_measures.md`, evaluated per-date instead of over the whole filter context) over `dim_date[Date]` — shows *when* the strategy was underwater, not just the single worst number.
- **Line chart — Rolling volatility**: `[Rolling 30-Day Volatility (Annualised)]` over `dim_date[Date]`.
- **Card row**: `[YTD Return]`, `[QTD Return]`, `[Variance to Benchmark]` for the selected strategy.

## Page 3 — Drill-Down Detail

**Purpose**: the "prove the numbers are real" page — rebalance-level turnover/cost detail, plus
ticker-level signal scores for whoever asks "which stocks were actually held."

- **Matrix visual**: rows = `dim_strategy[StrategyType]` → `dim_strategy[Strategy]` hierarchy, columns = `dim_date[YearQuarter]`, values = `[QTD Return]`.
- **Table visual — Rebalance log**: raw `fct_backtest_turnover` columns (`RebalanceDate`, `Turnover`, `Cost`, `NHoldings`) filtered to the strategy selected via cross-filter from the matrix — sorted by `RebalanceDate` descending so the most recent rebalance is on top.
- **Table visual — Ticker-level signal scores**: `fct_signal_scores` columns (`TICKER`, momentum/value/low-vol/mean-reversion/combined score columns) at the `PRICE_DATE` closest to a selected `RebalanceDate` from the table above — the page a skeptical interviewer would point at and ask "so what did the top-50 actually hold on this date."
- **Drillthrough page** (optional, same PL-300-relevant feature as the sibling project): right-click a strategy in the matrix → drillthrough to a Page-2-style single-strategy detail page.

## Page 4 — KPI Scorecard

**Purpose**: the risk/return scorecard across every strategy at once — the actual deliverable this
project set out to produce, exactly matching `reports/generate_report.py`'s markdown table but live
and filterable.

- **Table visual**: one row per `dim_strategy[Strategy]` (excluding the diagnostic), columns = `[YTD Return]`, `[Rolling 12-Month Return]`, `[Rolling 30-Day Volatility (Annualised)]`, `[Sharpe Ratio (Annualised)]`, `[Max Drawdown]`, `[Historical VaR 95%]`, `[Variance to Benchmark]`, `[Avg Cost per Rebalance (bps)]`.
- **Conditional formatting**: data bars on `[Sharpe Ratio (Annualised)]`, red/green background on `[Variance to Benchmark]`.
- **Scatter chart**: `[Rolling 30-Day Volatility (Annualised)]` on X, `[YTD Return]` on Y, one point per strategy, sized by `[Avg Turnover per Rebalance]` — the risk/return plot, same concept as the sibling project's scatter but per-strategy instead of per-ticker.
- **StrategyType slicer**, shared filter state with the table and scatter — lets a Portfolio Manager role (see RLS below) view just their permitted rows without needing a separate page.

---

## RLS verification checklist (do this before calling the report "done")

- [ ] `View As → Standalone Analyst`: confirm every page only shows the 4 individual factor strategies — combined score and SPY benchmark absent, including from the Page 1 bar chart and the Page 4 scatter.
- [ ] `View As → Portfolio Manager`: confirm only `Combined (all 4)` and `SPY (benchmark)` are visible; individual-factor rows absent everywhere.
- [ ] `View As → Risk Team (Full Access)`: confirm nothing is filtered, including `Long-Short (diagnostic)`.
- [ ] Publish to Power BI Service, then assign a test account to a role under the workspace's security settings and confirm the *published* report enforces it too — RLS defined in Desktop doesn't apply on its own until roles are assigned to users/groups in the Service.
