"""
Runs every strategy (4 standalone signals, the combined score, the long-short
diagnostic, and the SPY benchmark) and writes daily returns + turnover to
BigQuery — this is what Power BI actually connects to. Previously these only
existed in-memory (compare_signals.py) or as static plots
(generate_report.py); neither is queryable by a BI tool.

Full overwrite (WRITE_TRUNCATE) each run, not incremental — a backtest
recomputes its whole history from the current data every time by nature,
unlike a price feed where only new days need appending.

Run from project root:
    uv run python -m backtest.persist_results
"""
import sys
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

sys.path.append(str(Path(__file__).parent.parent))
from data_pipeline.bigquery_client import get_connection, table_ref

from backtest import benchmark, engine, metrics
from backtest.compare_signals import SIGNAL_COLUMNS

RETURNS_TABLE = "RAW_BACKTEST_RETURNS"
TURNOVER_TABLE = "RAW_BACKTEST_TURNOVER"


def main() -> None:
    print("Loading data and running every strategy...")
    price_returns, signal_scores = engine.run_all()
    spy = benchmark.spy_returns(price_returns)

    returns_frames = []
    turnover_frames = []

    for label, column in SIGNAL_COLUMNS.items():
        print(f"  {label}...")
        returns, turnover = engine.run_backtest(price_returns, signal_scores, column)
        returns_frames.append(pd.DataFrame({
            "STRATEGY": label, "DATE": returns.index, "DAILY_RETURN": returns.values,
        }))
        turnover["STRATEGY"] = label
        turnover_frames.append(turnover.rename(columns={
            "date": "REBALANCE_DATE", "turnover": "TURNOVER",
            "cost": "COST", "n_holdings": "N_HOLDINGS",
        }))

    print("  Long-Short (diagnostic)...")
    top_returns, _ = engine.run_backtest(price_returns, signal_scores, "COMBINED_SCORE", bottom=False)
    bottom_returns, _ = engine.run_backtest(price_returns, signal_scores, "COMBINED_SCORE", bottom=True)
    aligned_top, aligned_bottom = metrics.align(top_returns, bottom_returns)
    long_short = aligned_top - aligned_bottom
    returns_frames.append(pd.DataFrame({
        "STRATEGY": "Long-Short (diagnostic)", "DATE": long_short.index, "DAILY_RETURN": long_short.values,
    }))

    print("  SPY (benchmark)...")
    returns_frames.append(pd.DataFrame({
        "STRATEGY": "SPY (benchmark)", "DATE": spy.index, "DAILY_RETURN": spy.values,
    }))

    all_returns = pd.concat(returns_frames, ignore_index=True)
    all_returns["DATE"] = pd.to_datetime(all_returns["DATE"]).dt.date

    all_turnover = pd.concat(turnover_frames, ignore_index=True)
    all_turnover["REBALANCE_DATE"] = pd.to_datetime(all_turnover["REBALANCE_DATE"]).dt.date
    all_turnover = all_turnover[["STRATEGY", "REBALANCE_DATE", "TURNOVER", "COST", "N_HOLDINGS"]]

    print(f"\nWriting {len(all_returns):,} return rows and {len(all_turnover):,} turnover rows to BigQuery...")
    client = get_connection()

    returns_job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        schema=[
            bigquery.SchemaField("STRATEGY", "STRING"),
            bigquery.SchemaField("DATE", "DATE"),
            bigquery.SchemaField("DAILY_RETURN", "FLOAT64"),
        ],
    )
    client.load_table_from_dataframe(
        all_returns, table_ref(RETURNS_TABLE).strip("`"), job_config=returns_job_config
    ).result()

    turnover_job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        schema=[
            bigquery.SchemaField("STRATEGY", "STRING"),
            bigquery.SchemaField("REBALANCE_DATE", "DATE"),
            bigquery.SchemaField("TURNOVER", "FLOAT64"),
            bigquery.SchemaField("COST", "FLOAT64"),
            bigquery.SchemaField("N_HOLDINGS", "INTEGER"),
        ],
    )
    client.load_table_from_dataframe(
        all_turnover, table_ref(TURNOVER_TABLE).strip("`"), job_config=turnover_job_config
    ).result()

    print(f"Done — {RETURNS_TABLE} and {TURNOVER_TABLE} written.")


if __name__ == "__main__":
    main()
