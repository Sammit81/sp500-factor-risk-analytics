"""BigQuery client — reads project/credentials from .env (local) or the
environment (CI). Auth uses Application Default Credentials: point
GOOGLE_APPLICATION_CREDENTIALS at a service account JSON key file.
"""
import os
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()


def get_connection() -> bigquery.Client:
    return bigquery.Client(project=os.environ["GCP_PROJECT_ID"].strip())


def dataset_id() -> str:
    return os.environ["BQ_DATASET"].strip()


def table_ref(table: str) -> str:
    """Fully-qualified, backtick-quoted `project.dataset.table` for use in SQL."""
    project = os.environ["GCP_PROJECT_ID"].strip()
    return f"`{project}.{dataset_id()}.{table}`"
