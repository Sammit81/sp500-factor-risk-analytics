import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_pipeline.bigquery_client import get_connection, table_ref  # noqa: E402
from backtest import data as data_module  # noqa: E402


@pytest.fixture(scope="session")
def bq_client():
    return get_connection()


@pytest.fixture(scope="session")
def bq_table_ref():
    return table_ref


@pytest.fixture(scope="session")
def real_price_returns():
    """Session-scoped: fetched once from BigQuery, reused across every test
    that needs it — these queries are not free, and several tests in this
    suite want the same real data."""
    return data_module.load_price_returns()


@pytest.fixture(scope="session")
def real_signal_scores():
    return data_module.load_signal_scores()
