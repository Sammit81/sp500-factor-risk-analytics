"""Small, deterministic, BigQuery-free synthetic data for fast unit tests.

4 tickers, 2 months of business days, simple linear price trends so every
downstream calculation (returns, weights, drift) is hand-checkable.
"""
import pandas as pd

TICKERS = ["AAA", "BBB", "CCC", "DDD"]
BASE_PRICES = {"AAA": 100.0, "BBB": 50.0, "CCC": 200.0, "DDD": 10.0}
DAILY_DRIFT = {"AAA": 0.50, "BBB": -0.25, "CCC": 0.00, "DDD": 1.00}  # $/day, deterministic


def make_synthetic_price_returns(n_days: int = 40) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=n_days)
    rows = []
    for ticker in TICKERS:
        for i, date in enumerate(dates):
            price = BASE_PRICES[ticker] + DAILY_DRIFT[ticker] * i
            rows.append({
                "TICKER": ticker, "PRICE_DATE": date,
                "CLOSE_PRICE": price, "VOLUME": 1_000_000,
            })
    df = pd.DataFrame(rows).sort_values(["TICKER", "PRICE_DATE"]).reset_index(drop=True)
    df["DAILY_RETURN"] = df.groupby("TICKER")["CLOSE_PRICE"].pct_change()
    return df


def make_synthetic_signal_scores(price_returns: pd.DataFrame, scores: dict[str, float] = None) -> pd.DataFrame:
    """One fixed COMBINED_SCORE per ticker, replicated across every date —
    deterministic ranking for testing selection/tie-break behaviour."""
    scores = scores or {"AAA": 1.0, "BBB": -1.0, "CCC": 0.0, "DDD": 2.0}
    rows = []
    for _, row in price_returns[["TICKER", "PRICE_DATE"]].drop_duplicates().iterrows():
        rows.append({
            "TICKER": row["TICKER"],
            "PRICE_DATE": row["PRICE_DATE"],
            "COMBINED_SCORE": scores[row["TICKER"]],
            "IS_ELIGIBLE": True,
        })
    return pd.DataFrame(rows)
