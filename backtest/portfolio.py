"""
Portfolio construction: monthly rebalance, fixed share counts held between
rebalances (NOT re-normalized to equal weight daily — that would silently
simulate free, unrealistic rebalancing every single day), deterministic
tie-break at the selection boundary, flat-bps transaction cost model.
"""
from dataclasses import dataclass, field

import pandas as pd

DEFAULT_TOP_N = 50
DEFAULT_COST_BPS = 10.0  # round-trip, applied to turnover — see docs/decisions.md


@dataclass
class PortfolioState:
    shares: dict[str, float] = field(default_factory=dict)  # ticker -> share count

    def value(self, prices_on_date: dict[str, float]) -> float:
        return sum(qty * prices_on_date.get(ticker, 0.0) for ticker, qty in self.shares.items())

    def weights(self, prices_on_date: dict[str, float]) -> dict[str, float]:
        total = self.value(prices_on_date)
        if total <= 0:
            return {}
        return {t: (qty * prices_on_date.get(t, 0.0)) / total for t, qty in self.shares.items()}


def get_rebalance_dates(all_price_dates: pd.Series) -> list[pd.Timestamp]:
    """Last trading day of each calendar month present in the data."""
    dates = pd.to_datetime(pd.Series(all_price_dates).unique())
    df = pd.DataFrame({"date": dates}).sort_values("date")
    df["year_month"] = df["date"].dt.to_period("M")
    return df.groupby("year_month")["date"].max().sort_values().tolist()


def select_portfolio(
    signal_scores: pd.DataFrame,
    rebalance_date: pd.Timestamp,
    score_column: str,
    top_n: int = DEFAULT_TOP_N,
) -> list[str]:
    """Top-N tickers by score_column on rebalance_date, deterministic
    alphabetical tie-break at the N-th boundary.

    Filters on score_column being non-null directly, NOT on the combined
    signal's IS_ELIGIBLE flag (all-4-signals-present) — that flag is the
    right gate when ranking by COMBINED_SCORE (where it's redundant with
    non-null by construction), but would unfairly shrink a STANDALONE
    signal's universe to the combined signal's data-availability, biasing
    any comparison between them (see backtest/compare_signals.py)."""
    day = signal_scores[signal_scores["PRICE_DATE"] == rebalance_date].dropna(subset=[score_column])
    day = day.sort_values([score_column, "TICKER"], ascending=[False, True])
    return day["TICKER"].head(top_n).tolist()


def select_bottom_portfolio(
    signal_scores: pd.DataFrame,
    rebalance_date: pd.Timestamp,
    score_column: str,
    bottom_n: int = DEFAULT_TOP_N,
) -> list[str]:
    """Bottom-N tickers — internal diagnostic only (long-short spread),
    never a tradable portfolio given the long-only framing. Same
    non-null-on-score_column filtering rationale as select_portfolio."""
    day = signal_scores[signal_scores["PRICE_DATE"] == rebalance_date].dropna(subset=[score_column])
    day = day.sort_values([score_column, "TICKER"], ascending=[True, True])
    return day["TICKER"].head(bottom_n).tolist()


def compute_turnover_and_cost(
    old_weights: dict[str, float],
    new_weights: dict[str, float],
    portfolio_value: float,
    cost_bps: float = DEFAULT_COST_BPS,
) -> tuple[float, float]:
    """Turnover = fraction of the portfolio that changes composition
    (standard one-way definition: sum of absolute weight changes / 2).

    Both weight dicts are treated as including an implicit CASH position
    (1 - sum of stock weights) — this matters specifically for the very
    first rebalance, going from 100% cash to fully invested. Without an
    explicit CASH leg, comparing only the stock weights understates that
    transition's turnover by half (it looks like "half the portfolio
    changed" when actually the whole thing did — there's no offsetting
    stock being sold to fund the purchase, unlike a normal stock-to-stock
    reshuffle)."""
    old_cash = 1.0 - sum(old_weights.values())
    new_cash = 1.0 - sum(new_weights.values())
    all_tickers = set(old_weights) | set(new_weights)
    turnover = (
        sum(abs(new_weights.get(t, 0.0) - old_weights.get(t, 0.0)) for t in all_tickers)
        + abs(new_cash - old_cash)
    ) / 2
    cost = turnover * (cost_bps / 10_000) * portfolio_value
    return turnover, cost


def rebalance(
    portfolio_value: float,
    old_weights: dict[str, float],
    target_tickers: list[str],
    prices_on_date: dict[str, float],
    cost_bps: float = DEFAULT_COST_BPS,
) -> tuple[PortfolioState, float, float]:
    """Rebalance into an equal-weighted position across target_tickers,
    deducting transaction costs from portfolio_value (the mark-to-market
    value going into this rebalance — starting capital for the very first
    call, or the prior portfolio's value on this date otherwise).
    old_weights is {} for the first rebalance (100% cash, implicitly).
    Returns (new_state, turnover, cost)."""
    if not target_tickers or portfolio_value <= 0:
        return PortfolioState(shares={}), 0.0, 0.0

    new_weights = {t: 1.0 / len(target_tickers) for t in target_tickers}
    turnover, cost = compute_turnover_and_cost(old_weights, new_weights, portfolio_value, cost_bps)
    post_value = portfolio_value - cost

    per_ticker_value = post_value / len(target_tickers)
    new_shares = {
        t: per_ticker_value / prices_on_date[t]
        for t in target_tickers
        if prices_on_date.get(t, 0.0) > 0
    }
    return PortfolioState(shares=new_shares), turnover, cost
