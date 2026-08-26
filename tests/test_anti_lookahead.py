"""
THE proof test for the backtest engine: mutate real price data after a
cutoff date, rerun the actual Python backtest engine (portfolio.py +
engine.py — the same code path compare_signals.py uses), and assert
portfolio returns BEFORE the cutoff are bit-identical to the unmutated run.

Scope note: this specifically tests the ENGINE (portfolio construction,
position valuation, return computation), not the SQL signal layer — that's
already covered separately and more directly by test_pointintime_pe.py (the
report_date < price_date invariant) and the dbt-native unit_tests on the
signal models. The engine also touches price data directly (for valuing
held positions day to day), so it's a distinct, legitimate thing to verify
on its own: a bug in the rebalance loop's date-slicing logic could in
principle let a future price leak backward via a pandas indexing mistake,
independent of anything upstream in dbt.
"""
import pandas as pd

from backtest.engine import run_backtest


CUTOFF = pd.Timestamp("2024-06-01")
SHOCK_MULTIPLIER = 100.0  # deliberately huge — any leak becomes blatantly obvious, not lost in noise


def _mutate_prices_after_cutoff(price_returns: pd.DataFrame) -> pd.DataFrame:
    mutated = price_returns.copy()
    mutated["PRICE_DATE"] = pd.to_datetime(mutated["PRICE_DATE"])
    after = mutated["PRICE_DATE"] > CUTOFF
    mutated.loc[after, "CLOSE_PRICE"] = mutated.loc[after, "CLOSE_PRICE"] * SHOCK_MULTIPLIER
    return mutated


def test_mutating_future_prices_does_not_change_past_returns(real_price_returns, real_signal_scores):
    baseline_returns, _ = run_backtest(real_price_returns, real_signal_scores, "COMBINED_SCORE")

    mutated_prices = _mutate_prices_after_cutoff(real_price_returns)
    mutated_returns, _ = run_backtest(mutated_prices, real_signal_scores, "COMBINED_SCORE")

    pre_cutoff_dates = baseline_returns.index[baseline_returns.index <= CUTOFF]
    assert len(pre_cutoff_dates) > 20, "not enough pre-cutoff history to make this test meaningful"

    baseline_pre = baseline_returns.loc[pre_cutoff_dates]
    mutated_pre = mutated_returns.loc[pre_cutoff_dates]

    pd.testing.assert_series_equal(
        baseline_pre, mutated_pre,
        check_exact=True,
        obj="pre-cutoff daily returns (baseline vs. future-mutated prices)",
    )


def test_the_shock_actually_changed_post_cutoff_returns(real_price_returns, real_signal_scores):
    """Companion sanity check: if this test fails, the mutation itself
    didn't do anything (e.g. wrong column, wrong date comparison), which
    would make the "no lookahead" test above pass for the wrong reason —
    trivially, because nothing was actually mutated."""
    baseline_returns, _ = run_backtest(real_price_returns, real_signal_scores, "COMBINED_SCORE")
    mutated_prices = _mutate_prices_after_cutoff(real_price_returns)
    mutated_returns, _ = run_backtest(mutated_prices, real_signal_scores, "COMBINED_SCORE")

    post_cutoff_dates = baseline_returns.index[baseline_returns.index > CUTOFF]
    assert len(post_cutoff_dates) > 20, "not enough post-cutoff history to make this test meaningful"

    baseline_post = baseline_returns.loc[post_cutoff_dates]
    mutated_post = mutated_returns.loc[post_cutoff_dates]
    assert not baseline_post.equals(mutated_post), (
        "post-cutoff returns are identical despite a 100x price shock — "
        "the mutation had no effect, so the lookahead test above isn't proving anything"
    )
