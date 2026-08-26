"""
Backtest orchestration: ties data.py (BigQuery -> pandas) and portfolio.py
(construction/cost logic) together into a daily portfolio return series.
"""
import pandas as pd

from backtest import data as data_module
from backtest import portfolio

DEFAULT_STARTING_VALUE = 1_000_000.0


def run_backtest(
    price_returns: pd.DataFrame,
    signal_scores: pd.DataFrame,
    score_column: str,
    top_n: int = portfolio.DEFAULT_TOP_N,
    cost_bps: float = portfolio.DEFAULT_COST_BPS,
    starting_value: float = DEFAULT_STARTING_VALUE,
    bottom: bool = False,
) -> tuple[pd.Series, pd.DataFrame]:
    """Run a monthly-rebalanced backtest ranked by score_column.

    bottom=True runs the bottom-N portfolio instead of top-N — used only for
    the internal long-short diagnostic, never presented as a tradable
    strategy (see docs/decisions.md).

    Returns (daily_returns, turnover_log). Rebalance-date portfolio values
    reflect the POST-rebalance, POST-cost state — a rebalance date appears
    at the end of the outgoing period AND the start of the incoming one, and
    the incoming (new-state) valuation is written second, so it wins. That's
    the financially correct convention: costs are realised on the day
    they're paid, not deferred.
    """
    price_returns = price_returns.copy()
    signal_scores = signal_scores.copy()
    price_returns["PRICE_DATE"] = pd.to_datetime(price_returns["PRICE_DATE"])
    signal_scores["PRICE_DATE"] = pd.to_datetime(signal_scores["PRICE_DATE"])

    price_matrix = (
        price_returns[price_returns["TICKER"] != "SPY"]
        .pivot(index="PRICE_DATE", columns="TICKER", values="CLOSE_PRICE")
        .sort_index()
    )
    all_dates = price_matrix.index

    rebalance_dates = [d for d in portfolio.get_rebalance_dates(price_returns["PRICE_DATE"]) if d in all_dates]
    if not rebalance_dates:
        raise ValueError("No rebalance dates found in the overlap between price and signal data.")

    select_fn = portfolio.select_bottom_portfolio if bottom else portfolio.select_portfolio

    daily_values = pd.Series(index=all_dates, dtype=float)
    state = portfolio.PortfolioState(shares={})
    turnover_log = []

    for i, rdate in enumerate(rebalance_dates):
        prices_on_date = price_matrix.loc[rdate].dropna().to_dict()

        if state.shares:
            old_value = state.value(prices_on_date)
            old_weights = state.weights(prices_on_date)
        else:
            old_value = starting_value
            old_weights = {}

        target_tickers = select_fn(signal_scores, rdate, score_column, top_n)
        state, turnover, cost = portfolio.rebalance(old_value, old_weights, target_tickers, prices_on_date, cost_bps)
        turnover_log.append({
            "date": rdate, "turnover": turnover, "cost": cost, "n_holdings": len(target_tickers),
        })

        period_end = rebalance_dates[i + 1] if i + 1 < len(rebalance_dates) else all_dates[-1]
        period_dates = all_dates[(all_dates >= rdate) & (all_dates <= period_end)]

        if state.shares:
            held_tickers = list(state.shares.keys())
            shares_vector = pd.Series(state.shares)
            period_prices = price_matrix.loc[period_dates, held_tickers].ffill()
            daily_values.loc[period_dates] = (period_prices * shares_vector).sum(axis=1)
        else:
            daily_values.loc[period_dates] = old_value - cost  # nothing eligible: hold cash flat

    daily_returns = daily_values.dropna().pct_change().dropna()
    turnover_df = pd.DataFrame(turnover_log)
    return daily_returns, turnover_df


def run_all(top_n: int = portfolio.DEFAULT_TOP_N, cost_bps: float = portfolio.DEFAULT_COST_BPS):
    """Convenience loader: fetches data once from BigQuery, returns the raw
    DataFrames so a caller (e.g. compare_signals.py) can run multiple
    backtests against the same data without re-querying each time."""
    price_returns = data_module.load_price_returns()
    signal_scores = data_module.load_signal_scores()
    return price_returns, signal_scores
