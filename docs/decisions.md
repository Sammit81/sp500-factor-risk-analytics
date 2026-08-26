# Architecture & Design Decisions

Documented up front, before building, so every assumption is named and arguable rather than buried
in code. Several of these are honest limitations, not bugs — flagged as such.

## Universe: S&P 500 constituents, scraped once

Pulled from Wikipedia's "List of S&P 500 companies" page via `pandas.read_html`, run once locally,
saved as `dbt_project/seeds/sp500_constituents.csv`. **Not** re-scraped on every CI run — that would
make the universe non-reproducible run to run and adds a fragile dependency (Wikipedia's table
structure changing) to a daily pipeline that doesn't need it.

**Known limitation — survivorship bias**: this is *today's* constituent list applied across the
entire historical backtest window. Companies that were removed from the index (delisted, acquired,
went bankrupt) during the backtest period are absent, which tends to inflate backtested returns
versus what a real point-in-time index fund would have captured. Fixing this properly requires paid
point-in-time index membership data, which is out of scope here. Worth saying plainly rather than
overselling the backtest's realism.

## Value signal: point-in-time EPS, not daily snapshots

The daily fundamentals fetch (`fetch_fundamentals_snapshot.py`, same pattern as the sibling
`financial-markets-analytics` project) only ever captures *today's* P/E and accumulates forward from
whenever the pipeline first runs. That makes it structurally unusable for a walk-forward Value
signal — there's no historical P/E series in it, and backfilling with today's P/E across historical
dates would be a straightforward lookahead bug (using information from the future to score the
past).

**Fix**: `fetch_fundamentals_history.py` is a one-time, locally-run script (not part of the daily CI
pipeline) that backfills quarterly trailing EPS + report dates per ticker via yfinance, saved as
`dbt_project/seeds/pointintime_eps_history.csv`. `int_pointintime_pe.sql` computes P/E via an as-of
join: for each `(ticker, price_date)`, use the latest `report_date < price_date` — never a report
dated on or after the price date being scored.

**`EARNINGS_AVAILABILITY_LAG_DAYS`**: a named constant (not implicit) for how many days after a
report date the market is assumed to actually know the number. Currently `0` (report_date itself is
treated as the earliest usable date) — conservative would be a few days for filing/dissemination lag;
documented here so the assumption can be changed and argued with, not discovered by reading SQL.

**Known limitation — backtest window length**: momentum's 252-trading-day lookback is actually the
binding constraint on usable history, not the EPS depth — with 5 years of price history fetched
(`HISTORY_DAYS = 1825`, extended from an initial 730-day/2-year attempt specifically because that
first attempt left only ~13 rebalances with all 4 signals eligible), the backtest has **49 monthly
rebalances with a fully eligible universe, spanning ~August 2022 to August 2026** (the first year is
"burn-in" while momentum's lookback fills in). 49 rebalances is a real, usable sample — better than
the initial 13 — but it's still a modest sample for time-series inference by normal statistical
standards. Sharpe ratios and other risk-adjusted metrics from this backtest should be read as
directional evidence, not statistically definitive conclusions. Said plainly here rather than
over-claiming.

## Coverage rule: require all 4 signals, no partial averaging

A ticker is only eligible for the combined score if it has a non-null value for all four signals
(momentum, mean reversion, low volatility, value) on that date. The alternative — averaging whichever
signals happen to be available — is harder to defend cleanly under questioning ("why does this
ticker's combined score only reflect 2 of 4 signals this month?"). Requiring completeness is the
simpler, more defensible rule, at the cost of a smaller eligible universe on any given date (Value
in particular will have gaps).

## Benchmark: real SPY, not a self-constructed index

The primary benchmark for excess return / tracking error / information ratio is actual SPY price
data, fetched as one extra ticker in `fetch_prices.py` — not a cap-weighted reconstruction of the
500-ticker universe, which would need point-in-time shares-outstanding data (the same class of
problem as the Value signal, not worth solving twice for a secondary benchmark). An equal-weight
return of the full universe is also computed, but only as an internal diagnostic that isolates stock
*selection* skill from cap-weighting effects — not presented as "the benchmark."

## Rebalance: monthly, top decile (50 of 500)

Standard academic/practitioner convention (Fama-French and AQR-style factor research use
quintile/decile sorts), not an arbitrary round number. Bottom-decile return and the long-short spread
(top decile minus bottom decile) are also computed as an internal diagnostic — not a tradable
portfolio given the long-only framing, but the cleanest, most standard way to show a signal carries
information content independent of implementation choices like position count or weighting scheme.

Positions are held as **fixed share counts** between rebalances, not re-normalized to equal weight
daily — daily re-normalization would silently simulate free, unrealistic rebalancing every single
day. Weights drift with price between rebalance dates, same as a real portfolio would.

**Deterministic tie-break**: at the exact N=50 boundary, ties are broken alphabetically by ticker.
Needed for the anti-lookahead test to be genuinely bit-reproducible, not just "usually the same."

## Transaction costs: flat 10bps round-trip

Applied to the fraction of the portfolio that turns over at each rebalance. Both gross and
net-of-cost metrics are reported side by side. 10bps is a documented assumption, not a researched
number for this specific universe/strategy — changeable in one place (`portfolio.py`).

## VaR: historical primary, parametric secondary, Kupiec-tested

Historical (nonparametric) VaR is the primary risk measure — it doesn't assume a normal return
distribution, which is the wrong assumption for equities (fat tails). Parametric
(variance-covariance) VaR is computed alongside it; the *discrepancy* between the two is itself
informative rather than a nuisance. A Kupiec proportion-of-failures test counts actual daily loss
exceedances against the VaR threshold and compares to the statistically expected exceedance rate —
applying the same "prove it against ground truth" standard to the risk metrics themselves, not just
the trading signal.

## Anti-lookahead testing: two layers

1. **dbt-native `unit_tests:`** on the SQL signal models (cheap, fast, run every CI build) —
   including a fixture row dated in the future that must not change a past row's computed value.
2. **A pytest integration test** (`test_anti_lookahead.py`) that runs the actual Python backtest
   engine on a real data slice, mutates prices after a cutoff date in a copy, reruns, and asserts
   pre-cutoff portfolio returns are bit-identical. This is the test that proves the full pipeline —
   signals and backtest engine together — not just one SQL model in isolation.

## Test framework: first pytest suite in this portfolio

No sibling project has an automated Python test suite yet. This project introduces `pytest` — worth
being upfront that it's new here, not an established convention being followed.

## Explicitly out of scope for v1

No Streamlit or other interactive dashboard. The deliverable is the tested star schema, the backtest
engine, the pytest suite, and a generated results report (static plots + a markdown summary). Given
the universe size (500 vs. 27 tickers elsewhere) and the 4-signal combination, this is already a
bigger lift than the sibling projects — a dashboard is a clearly-labeled stretch goal, not committed
scope.
