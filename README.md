# S&P 500 Multi-Signal Factor Backtest & Risk Analytics

A multi-signal equity factor backtest and portfolio risk analytics project on the S&P 500 universe —
framed as **portfolio risk & performance analytics** (benchmark-relative attribution, risk-adjusted
metrics) rather than pure alpha-signal trading, matching how quant-analyst hiring at Dublin's asset
managers and fund administrators actually looks, more than prop-trading-desk hiring does.

Four signals — Momentum (12-1 month), Mean Reversion (short-term), Low Volatility, and Value
(point-in-time P/E) — are combined into one cross-sectionally ranked score, backtested against real
SPY as the benchmark, with two layers of anti-lookahead testing and a comparison step that proves the
combined signal actually beats each standalone signal rather than just asserting it.

Every non-obvious design decision (survivorship bias, the point-in-time Value signal fix, the
coverage rule, transaction costs, VaR methodology) is documented in
[`docs/decisions.md`](docs/decisions.md) — read that before asking "why did you do X."

---

## Status

Built in phases, each verified against real BigQuery data before moving to the next:

- ✅ Phase A — ingestion + price-only star schema (momentum, mean reversion, low-vol signals). 5 years of price history, 623k rows, momentum hand-verified against a manual calculation.
- ✅ Phase B — point-in-time Value signal. 500/503 tickers backfilled (10,316 quarterly EPS records), 20/20 dbt tests, P/E hand-verified.
- ✅ Phase C — backtest engine + anti-lookahead tests. Two independent lookahead-bias tests (a dbt unit test on the highest-risk join, a pytest integration test on the full engine), both deliberately verified to have teeth by injecting a real bug, confirming the failure, and reverting.
- ✅ Phase D — risk analytics, signal comparison, results report. See [`reports/output/summary.md`](reports/output/summary.md) — 21/21 pytest, 23/23 dbt tests (22 data + 1 unit test).

**Real result** (49 monthly rebalances, Aug 2022–Aug 2026): the combined 4-signal score didn't beat Momentum alone on raw Sharpe (0.97 vs 1.11), but it did cut annualised volatility from 23.5% to 15.9% and improved max drawdown from -29.0% to -22.4% versus Momentum standalone, while still beating SPY, every other standalone signal, and doing so with less risk than any single factor except Low Volatility. A real, explainable diversification result — reported as-is, not cherry-picked.

---

## Architecture

```
S&P 500 constituents (Wikipedia, scraped once → seed, not re-scraped in CI)
    ▼
data_pipeline/ — batch yfinance fetch (~500 tickers + SPY), incremental watermark,
                  single consolidated parameterized DELETE (BigQuery DML rate limits
                  mean one-DELETE-per-ticker fails at this scale — see docs/decisions.md)
    ▼
BigQuery (SP500_FACTOR_ANALYTICS dataset)
    ▼
dbt_project/ — staging → intermediate (one SQL model per signal + point-in-time Value join)
             → marts (fct_signal_scores, dim_ticker)
    ▼
backtest/ — Python: monthly rebalance, fixed-share positions, transaction costs,
            benchmarked against real SPY, compare_signals.py proves the combination
            beats every standalone signal
    ▼
reports/generate_report.py — static plots + markdown summary
```

---

## Setup

**Prerequisites**: Python 3.10+, `uv`, access to the `irish-market-intelligence` GCP project
(same project as the sibling `financial-markets-analytics` and `irish-markets-powerbi-model`
projects — this reuses that project's BigQuery access, just a new dataset).

```bash
uv sync

cp .env.example .env
# GCP_PROJECT_ID, BQ_DATASET=SP500_FACTOR_ANALYTICS, GOOGLE_APPLICATION_CREDENTIALS already set
# if you have gcp-key.json from the sibling project — copy it here, or point at its path directly.

# One-time setup (not part of the daily pipeline):
uv run data_pipeline/scrape_sp500_constituents.py     # writes dbt_project/seeds/sp500_constituents.csv
uv run data_pipeline/fetch_fundamentals_history.py     # writes dbt_project/seeds/pointintime_eps_history.csv

# Daily pipeline:
uv run data_pipeline/fetch_prices.py

cd dbt_project
export GCP_PROJECT_ID=irish-market-intelligence BQ_DATASET=SP500_FACTOR_ANALYTICS \
       GOOGLE_APPLICATION_CREDENTIALS=../gcp-key.json DBT_PROFILES_DIR=.
uv run --with dbt-bigquery dbt seed
uv run --with dbt-bigquery dbt run
uv run --with dbt-bigquery dbt test
cd ..

# Backtest + risk analytics:
uv run python -m backtest.compare_signals
uv run python reports/generate_report.py

# Tests:
uv run --group dev pytest
```
