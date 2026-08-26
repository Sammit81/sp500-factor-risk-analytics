"""
Portfolio construction correctness — pure synthetic data, no BigQuery needed.
Covers the specific bugs a fast implementation would be likely to introduce:
silently re-normalizing weights daily, mis-handling the first (100%-cash)
rebalance's turnover, and non-deterministic tie-breaking.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import portfolio
from tests.fixtures.synthetic_data import make_synthetic_price_returns


def test_weights_drift_between_rebalances_not_renormalized():
    """Fixed share counts mean weights should change day to day as prices
    move, NOT stay pinned to the target allocation — if this test fails with
    constant weights, the engine is silently doing free daily rebalancing."""
    prices_day1 = {"AAA": 100.0, "BBB": 50.0}
    state = portfolio.PortfolioState(shares={"AAA": 5.0, "BBB": 10.0})  # $500 + $500 = equal weight day 1

    w1 = state.weights(prices_day1)
    assert abs(w1["AAA"] - 0.5) < 1e-9
    assert abs(w1["BBB"] - 0.5) < 1e-9

    prices_day2 = {"AAA": 120.0, "BBB": 50.0}  # AAA up 20%, BBB flat
    w2 = state.weights(prices_day2)
    assert w2["AAA"] > 0.5, "AAA's weight should have drifted up after its price rose, not stayed at 0.5"
    assert abs(w2["AAA"] - 600 / 1100) < 1e-9


def test_first_rebalance_is_full_turnover_not_half():
    """The bug this guards against: comparing only stock-vs-stock weights
    (ignoring the implicit 100% cash position before the first trade) makes
    a full cash-to-invested transition look like 50% turnover instead of
    100% — see the compute_turnover_and_cost docstring."""
    turnover, cost = portfolio.compute_turnover_and_cost(
        old_weights={},  # 100% cash, implicitly
        new_weights={"AAA": 0.5, "BBB": 0.5},
        portfolio_value=1_000_000.0,
        cost_bps=10.0,
    )
    assert abs(turnover - 1.0) < 1e-9, f"expected 100% turnover on first investment, got {turnover}"
    assert abs(cost - 1_000_000.0 * 10 / 10_000) < 1e-6


def test_full_reshuffle_turnover_is_one_not_two():
    """A complete swap from one full portfolio to a disjoint one should be
    100% turnover, not 200% — this is what the /2 in the turnover formula
    is for, and it's easy to accidentally drop."""
    turnover, _ = portfolio.compute_turnover_and_cost(
        old_weights={"AAA": 0.5, "BBB": 0.5},
        new_weights={"CCC": 0.5, "DDD": 0.5},
        portfolio_value=1_000_000.0,
        cost_bps=10.0,
    )
    assert abs(turnover - 1.0) < 1e-9


def test_no_change_means_zero_turnover():
    turnover, cost = portfolio.compute_turnover_and_cost(
        old_weights={"AAA": 0.5, "BBB": 0.5},
        new_weights={"AAA": 0.5, "BBB": 0.5},
        portfolio_value=1_000_000.0,
    )
    assert turnover == 0.0
    assert cost == 0.0


def test_selection_tie_break_is_deterministic():
    """Ties at the exact N-th boundary break alphabetically — needed for
    the anti-lookahead test to be genuinely bit-reproducible."""
    price_returns = make_synthetic_price_returns()
    date = price_returns["PRICE_DATE"].iloc[0]
    # All 4 tickers tied on score — top_n=2 must always return the same 2.
    tied_scores = pd.DataFrame({
        "TICKER": ["DDD", "BBB", "AAA", "CCC"],
        "PRICE_DATE": [date] * 4,
        "COMBINED_SCORE": [1.0, 1.0, 1.0, 1.0],
        "IS_ELIGIBLE": [True] * 4,
    })
    result1 = portfolio.select_portfolio(tied_scores, date, "COMBINED_SCORE", top_n=2)
    result2 = portfolio.select_portfolio(tied_scores, date, "COMBINED_SCORE", top_n=2)
    assert result1 == result2 == ["AAA", "BBB"], f"expected alphabetical tie-break, got {result1}"


def test_selection_excludes_nulls_without_requiring_global_eligibility():
    """A standalone signal's universe should depend only on that signal
    being non-null, not on the combined signal's all-4-present flag —
    otherwise comparing standalone vs. combined performance is unfair to
    the standalone signals (see the docstring in backtest/portfolio.py)."""
    date = pd.Timestamp("2024-01-02")
    scores = pd.DataFrame({
        "TICKER": ["AAA", "BBB", "CCC"],
        "PRICE_DATE": [date] * 3,
        "MOMENTUM_ZSCORE": [1.0, 2.0, None],
        "IS_ELIGIBLE": [True, False, False],  # BBB/CCC not eligible for the COMBINED score
    })
    result = portfolio.select_portfolio(scores, date, "MOMENTUM_ZSCORE", top_n=2)
    assert result == ["BBB", "AAA"], (
        f"expected BBB (score 2.0) and AAA (score 1.0) selected on momentum alone "
        f"despite IS_ELIGIBLE=False, got {result}"
    )
