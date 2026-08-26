"""
One-time scrape of the current S&P 500 constituent list from Wikipedia.

Not part of the daily pipeline — run this once locally and commit the resulting
seed CSV. Re-scraping every CI run would make the universe non-reproducible
run-to-run and adds a fragile dependency (Wikipedia's table structure changing)
to a pipeline that doesn't need it. See docs/decisions.md for the survivorship-
bias limitation this implies.

Run from project root:
    uv run data_pipeline/scrape_sp500_constituents.py
"""
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
OUTPUT_PATH = Path(__file__).parent.parent / "dbt_project" / "seeds" / "sp500_constituents.csv"


def main() -> None:
    print(f"Fetching constituent table from {WIKI_URL} ...")
    # Wikipedia rejects the default urllib user-agent with a 403 — fetch with a
    # real one via requests, then hand the HTML to pandas instead of letting
    # read_html() do the request itself.
    resp = requests.get(WIKI_URL, headers={"User-Agent": "Mozilla/5.0 (research script)"})
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text))
    constituents = tables[0]

    df = pd.DataFrame({
        "ticker": constituents["Symbol"].str.replace(".", "-", regex=False),
        "name": constituents["Security"],
        "sector": constituents["GICS Sector"],
        "gics_industry": constituents["GICS Sub-Industry"],
    })

    # yfinance uses '-' for share classes (e.g. BRK-B), Wikipedia uses '.' (BRK.B)
    df = df.drop_duplicates(subset="ticker").sort_values("ticker").reset_index(drop=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} constituents -> {OUTPUT_PATH.relative_to(Path(__file__).parent.parent)}")


if __name__ == "__main__":
    main()
