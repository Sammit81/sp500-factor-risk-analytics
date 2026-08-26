"""Benchmark return series: real SPY (primary) and an equal-weight-of-universe
diagnostic. See docs/decisions.md — the equal-weight series isolates stock
SELECTION skill from cap-weighting effects, it is not "the benchmark"."""
import pandas as pd


def spy_returns(price_returns: pd.DataFrame) -> pd.Series:
    """Daily SPY returns indexed by date — the primary ground-truth benchmark."""
    spy = price_returns[price_returns["TICKER"] == "SPY"].copy()
    spy["PRICE_DATE"] = pd.to_datetime(spy["PRICE_DATE"])
    return spy.set_index("PRICE_DATE")["DAILY_RETURN"].sort_index()


def equal_weight_universe_returns(price_returns: pd.DataFrame) -> pd.Series:
    """Daily equal-weight average return across the full S&P 500 universe
    (excludes SPY itself). Internal diagnostic only, not a benchmark claim."""
    universe = price_returns[price_returns["TICKER"] != "SPY"].copy()
    universe["PRICE_DATE"] = pd.to_datetime(universe["PRICE_DATE"])
    return universe.groupby("PRICE_DATE")["DAILY_RETURN"].mean().sort_index()
