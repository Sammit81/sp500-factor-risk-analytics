"""Pulls the star schema marts into pandas for the backtest engine.

BigQuery doesn't reliably preserve column casing through dbt table
materialization the way you might expect from the SQL as written (a lesson
learned the hard way on a sibling project) — every query result is
normalised to uppercase columns here, at the one boundary where BigQuery
results become pandas DataFrames, rather than trusting casing SQL-side.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))
from data_pipeline.bigquery_client import get_connection, table_ref

BENCHMARK_TICKER = "SPY"


def _query(sql: str) -> pd.DataFrame:
    client = get_connection()
    df = client.query(sql).to_dataframe()
    df.columns = df.columns.str.upper()
    return df


def load_price_returns() -> pd.DataFrame:
    """All price/return history, including the SPY benchmark rows."""
    return _query(f"""
        SELECT TICKER, PRICE_DATE, CLOSE_PRICE, VOLUME, DAILY_RETURN
        FROM {table_ref('fct_price_returns')}
        ORDER BY TICKER, PRICE_DATE
    """)


def load_signal_scores() -> pd.DataFrame:
    """All signal scores, investable universe only (excludes SPY — the
    benchmark isn't part of stock selection)."""
    return _query(f"""
        SELECT TICKER, PRICE_DATE, MOMENTUM_ZSCORE, MEAN_REVERSION_ZSCORE,
               LOW_VOL_ZSCORE, VALUE_ZSCORE, COMBINED_SCORE, IS_ELIGIBLE
        FROM {table_ref('fct_signal_scores')}
        WHERE TICKER != '{BENCHMARK_TICKER}'
        ORDER BY TICKER, PRICE_DATE
    """)


def load_benchmark_returns() -> pd.DataFrame:
    """SPY only — the primary ground-truth benchmark."""
    return _query(f"""
        SELECT PRICE_DATE, CLOSE_PRICE, DAILY_RETURN
        FROM {table_ref('fct_price_returns')}
        WHERE TICKER = '{BENCHMARK_TICKER}'
        ORDER BY PRICE_DATE
    """)
