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

- ⬜ Phase A — ingestion + price-only star schema (momentum, mean reversion, low-vol signals)
- ⬜ Phase B — point-in-time Value signal
- ⬜ Phase C — backtest engine + anti-lookahead tests
- ⬜ Phase D — risk analytics, signal comparison, results report

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
uv run data_pipeline/fetch_fundamentals_snapshot.py

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
uv run pytest
```
