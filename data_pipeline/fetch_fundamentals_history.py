"""
ONE-TIME backfill of point-in-time quarterly EPS history for the S&P 500
universe. NOT part of the daily pipeline — run this once locally and commit
the resulting seed CSV. See docs/decisions.md for why this exists as a
separate, seed-backed table rather than reusing the daily fundamentals
snapshot (the daily snapshot only has "today's" P/E, which cannot support a
walk-forward Value-signal backtest without a lookahead bug).

For each ticker: pulls reported quarterly EPS + the actual earnings report
date (not the period-end date — the report date is when the market actually
knew the number, which is what matters for avoiding lookahead). Computes
trailing-twelve-month EPS as the sum of the 4 most recent reported quarters
as of each report date — the conventional basis for a P/E ratio, not a
single quarter's EPS.

Known limitation: yfinance's earnings-date history is realistically bounded
to roughly the last ~5 years per ticker (documented in docs/decisions.md
alongside the resulting short backtest window).

Run from project root:
    uv run data_pipeline/fetch_fundamentals_history.py
"""
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.append(str(Path(__file__).parent.parent))

SEED_IN  = Path(__file__).parent.parent / "dbt_project" / "seeds" / "sp500_constituents.csv"
SEED_OUT = Path(__file__).parent.parent / "dbt_project" / "seeds" / "pointintime_eps_history.csv"
EARNINGS_LOOKBACK_QUARTERS = 20  # ~5 years, gives enough history for a 4-quarter trailing sum


def load_tickers() -> list[str]:
    with open(SEED_IN, newline="") as f:
        return [row["ticker"] for row in csv.DictReader(f)]


def trailing_eps_for_ticker(ticker: str) -> pd.DataFrame:
    """Reported quarterly EPS -> trailing-4-quarter EPS as of each report date."""
    t = yf.Ticker(ticker)
    df = t.get_earnings_dates(limit=EARNINGS_LOOKBACK_QUARTERS)
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.reset_index().rename(columns={"Earnings Date": "report_date", "Reported EPS": "eps"})
    df["report_date"] = pd.to_datetime(df["report_date"]).dt.tz_localize(None).dt.date

    # Drop rows with no reported EPS yet (future/upcoming earnings dates) and
    # sort chronologically so the rolling sum is a genuine trailing window.
    df = df.dropna(subset=["eps"]).sort_values("report_date").reset_index(drop=True)
    if len(df) < 4:
        return pd.DataFrame()

    df["trailing_eps"] = df["eps"].rolling(window=4).sum()
    df = df.dropna(subset=["trailing_eps"])

    df["ticker"] = ticker
    return df[["ticker", "report_date", "trailing_eps"]]


def main() -> None:
    tickers = load_tickers()
    print(f"Backfilling point-in-time EPS history for {len(tickers)} tickers...")

    frames = []
    failed = []
    for i, ticker in enumerate(tickers, 1):
        try:
            df = trailing_eps_for_ticker(ticker)
            if not df.empty:
                frames.append(df)
                status = f"{len(df)} quarters"
            else:
                status = "no usable history"
        except Exception as e:
            failed.append(ticker)
            status = f"ERROR: {e}"

        if i % 25 == 0 or i == len(tickers):
            print(f"  [{i}/{len(tickers)}] {ticker:<8} {status}")

    if not frames:
        print("No fundamentals history collected — aborting without overwriting the seed.")
        return

    combined = pd.concat(frames, ignore_index=True).sort_values(["ticker", "report_date"])
    SEED_OUT.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(SEED_OUT, index=False)

    print(f"\nWrote {len(combined):,} (ticker, report_date) rows across "
          f"{combined['ticker'].nunique()} tickers -> {SEED_OUT.relative_to(Path(__file__).parent.parent)}")
    if failed:
        print(f"{len(failed)} tickers failed entirely: {', '.join(failed[:20])}"
              f"{' ...' if len(failed) > 20 else ''}")


if __name__ == "__main__":
    main()
