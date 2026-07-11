from datetime import datetime
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator


PROJECT_PATH = Path(__file__).resolve().parent.parent


with DAG(
    dag_id="data_lake_ticketmaster_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["data-lake", "ticketmaster", "ml"],
) as dag:

    ingestion = BashOperator(
        task_id="raw_ingestion",
        bash_command=f'cd "{PROJECT_PATH}" && uv run src/ingestion.py',
    )

    staging = BashOperator(
        task_id="staging_mysql",
        bash_command=f'cd "{PROJECT_PATH}" && uv run src/staging.py',
    )

    train_model = BashOperator(
        task_id="train_ml_model",
        bash_command=f'cd "{PROJECT_PATH}" && uv run src/train_model.py',
    )

    curated = BashOperator(
        task_id="curated_mongodb",
        bash_command=f'cd "{PROJECT_PATH}" && uv run src/curated_ml.py',
    )

    ingestion >> staging >> train_model >> curated