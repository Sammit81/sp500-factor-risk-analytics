"""
Fetch historical and latest price data from Yahoo Finance → BigQuery, for the
full S&P 500 universe (+SPY as the backtest benchmark).

Batches requests in chunks (not 500 individual yf.download() calls, and not one
giant 500-ticker call either — chunking bounds memory/timeout risk while still
being far more efficient than one-ticker-at-a-time). Incremental after the first
run: on run one every ticker has no watermark, so the whole universe gets a full
history pull in one pass; every run after that, all tickers get updated together
each time, so the per-ticker watermark stays in sync and subsequent runs only
fetch new days.

Known simplification: if a ticker is added to sp500_constituents.csv later with
no prior watermark while every other ticker already has one, the batch start
date becomes that new ticker's full-history start, causing a redundant re-fetch
for the rest of the universe too. Rare in practice (the constituent seed isn't
auto-updated in CI) and not worth a more complex per-ticker-grouped fetch for
this project — documented here rather than silently accepted.

Run from project root:
    uv run data_pipeline/fetch_prices.py
"""
import csv
import sys
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from google.cloud import bigquery

sys.path.append(str(Path(__file__).parent.parent))
from data_pipeline.bigquery_client import get_connection, table_ref

load_dotenv()

HISTORY_DAYS = 1825  # 5 years on first run — matches the EPS backfill's depth. A shorter
                      # window (originally 730 days) left momentum's 252-trading-day lookback
                      # eating most of the price history, leaving only ~13 rebalances with all
                      # 4 signals eligible — too small a sample for the signal comparison to mean much.
TABLE_NAME   = "RAW_PRICES"
CHUNK_SIZE   = 50
SEED_PATH    = Path(__file__).parent.parent / "dbt_project" / "seeds" / "sp500_constituents.csv"
BENCHMARK_TICKER = "SPY"


def load_universe() -> dict[str, str]:
    """Ticker -> name, from the S&P 500 seed, plus the SPY benchmark ticker."""
    with open(SEED_PATH, newline="") as f:
        tickers = {row["ticker"]: row["name"] for row in csv.DictReader(f)}
    tickers[BENCHMARK_TICKER] = "SPDR S&P 500 ETF Trust (benchmark)"
    return tickers


def get_last_loaded_date(client: bigquery.Client) -> dict[str, str]:
    """Return the most recent date loaded per ticker — for incremental loads."""
    try:
        rows = client.query(f"""
            SELECT TICKER, MAX(PRICE_DATE) AS MAX_DATE
            FROM {table_ref(TABLE_NAME)}
            GROUP BY TICKER
        """).result()
        return {row.TICKER: row.MAX_DATE for row in rows}
    except Exception:
        return {}


def chunked(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def fetch_chunk(tickers: list[str], names: dict[str, str], start: str, end: str) -> pd.DataFrame:
    """Batch-download OHLCV for a chunk of tickers and return a long-format DataFrame."""
    try:
        raw = yf.download(
            tickers, start=start, end=end, progress=False, auto_adjust=True,
            group_by="ticker", threads=True,
        )
    except Exception as e:
        print(f"  ERROR fetching chunk {tickers[:3]}...: {e}")
        return pd.DataFrame()

    if raw.empty:
        return pd.DataFrame()

    frames = []
    for ticker in tickers:
        try:
            df = raw[ticker].dropna(how="all") if len(tickers) > 1 else raw.dropna(how="all")
        except KeyError:
            continue
        if df.empty:
            continue

        df = df.reset_index()
        df.columns = [c.upper().replace(" ", "_") for c in df.columns]
        df["TICKER"] = ticker
        df["NAME"]   = names.get(ticker, ticker)
        df = df.rename(columns={"DATE": "PRICE_DATE"})
        df["PRICE_DATE"] = pd.to_datetime(df["PRICE_DATE"]).dt.date.astype(str)
        frames.append(df[["TICKER", "NAME", "PRICE_DATE", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]])

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main():
    print("Connecting to BigQuery...")
    client = get_connection()

    client.query(f"""
        CREATE TABLE IF NOT EXISTS {table_ref(TABLE_NAME)} (
            TICKER     STRING,
            NAME       STRING,
            PRICE_DATE DATE,
            OPEN       FLOAT64,
            HIGH       FLOAT64,
            LOW        FLOAT64,
            CLOSE      FLOAT64,
            VOLUME     FLOAT64,
            LOADED_AT  TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
        )
    """).result()

    universe   = load_universe()
    last_dates = get_last_loaded_date(client)
    end_date   = datetime.today().strftime("%Y-%m-%d")

    # One batch start date: the earliest date any ticker needs data from.
    # See module docstring for the tradeoff this implies.
    if last_dates:
        oldest_watermark = min(pd.to_datetime(d) for d in last_dates.values())
        start_date = (oldest_watermark + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        start_date = (datetime.today() - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%d")

    tickers_needing_full_history = [t for t in universe if t not in last_dates]
    mode = "full" if len(tickers_needing_full_history) == len(universe) else "incremental/mixed"
    print(f"Fetching {len(universe)} tickers [{mode}] {start_date} → {end_date}")

    all_frames = []
    ticker_list = list(universe.keys())
    for i, chunk in enumerate(chunked(ticker_list, CHUNK_SIZE), 1):
        print(f"  chunk {i}/{-(-len(ticker_list) // CHUNK_SIZE)} ({len(chunk)} tickers)...", end=" ", flush=True)
        df = fetch_chunk(chunk, universe, start_date, end_date)
        if df.empty:
            print("no data")
            continue
        all_frames.append(df)
        print(f"{len(df)} rows")

    if not all_frames:
        print("No new data to load.")
        return

    combined = pd.concat(all_frames, ignore_index=True)

    # Upsert: delete existing rows in the date range about to be reloaded, then insert.
    # BigQuery strictly rate-limits DML mutations per table, so this must be ONE DELETE
    # statement covering every ticker rather than one DELETE per ticker.
    min_dates = pd.to_datetime(combined["PRICE_DATE"]).groupby(combined["TICKER"]).min()
    conditions, params = [], []
    for i, (ticker, min_date) in enumerate(min_dates.items()):
        conditions.append(f"(TICKER = @ticker_{i} AND PRICE_DATE >= @date_{i})")
        params.append(bigquery.ScalarQueryParameter(f"ticker_{i}", "STRING", ticker))
        params.append(bigquery.ScalarQueryParameter(f"date_{i}", "DATE", min_date.date()))

    client.query(
        f"DELETE FROM {table_ref(TABLE_NAME)} WHERE {' OR '.join(conditions)}",
        job_config=bigquery.QueryJobConfig(query_parameters=params),
    ).result()

    load_df = combined.copy()
    load_df["PRICE_DATE"] = pd.to_datetime(load_df["PRICE_DATE"]).dt.date

    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND",
        schema=[
            bigquery.SchemaField("TICKER", "STRING"),
            bigquery.SchemaField("NAME", "STRING"),
            bigquery.SchemaField("PRICE_DATE", "DATE"),
            bigquery.SchemaField("OPEN", "FLOAT64"),
            bigquery.SchemaField("HIGH", "FLOAT64"),
            bigquery.SchemaField("LOW", "FLOAT64"),
            bigquery.SchemaField("CLOSE", "FLOAT64"),
            bigquery.SchemaField("VOLUME", "FLOAT64"),
        ],
    )
    job = client.load_table_from_dataframe(load_df, table_ref(TABLE_NAME).strip("`"), job_config=job_config)
    job.result()
    print(f"\nLoaded {len(combined):,} rows -> {TABLE_NAME}")


if __name__ == "__main__":
    main()
