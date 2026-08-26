import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_pipeline.bigquery_client import get_connection, table_ref  # noqa: E402


@pytest.fixture(scope="session")
def bq_client():
    return get_connection()


@pytest.fixture(scope="session")
def bq_table_ref():
    return table_ref
