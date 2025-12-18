"""
Simple C2C Ingestion Pipeline DAG (Fetch-only)
- Fetch data from Binance C2C API
- No DB insert
- No Telegram
- Used for ingestion testing
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.cncf.kubernetes.secret import Secret

# ============================================================
# Binance API Secrets (ONLY what ingestion needs)
# ============================================================

api_key_secret = Secret(
    deploy_type='env',
    deploy_target='BINANCE_API_KEY',
    secret='airflow-producer-secret',
    key='API_KEY'
)

api_secret_secret = Secret(
    deploy_type='env',
    deploy_target='BINANCE_API_SECRET',
    secret='airflow-producer-secret',
    key='API_SECRET'
)

# ============================================================
# Default arguments
# ============================================================

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

# ============================================================
# DAG definition
# ============================================================

with DAG(
    dag_id='c2c_ingestion_latest_month',
    default_args=default_args,
    description='C2C ingestion only (fetch latest month)',
    schedule='@hourly',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['c2c', 'ingestion', 'test']
) as dag:

    # ============================================================
    # SINGLE TASK: INGESTION ONLY
    # ============================================================

    c2c_ingestion_job = KubernetesPodOperator(
        task_id='c2c_ingestion_latest_month',
        name='c2c-ingestion-latest-month',
        namespace='orchestration',

        # 🔥 CHANGED: use ingestion image
        image='asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/ingestion-app:latest',

        # 🔥 CHANGED: ingestion entrypoint
        cmds=["python3", "/app/c2c_ingestion.py"],

        # 🔥 ONLY ingestion-related envs
        env_vars={
            "FETCH_MODE": "latest_month",
        },

        # 🔥 ONLY API secrets (no DB, no Telegram)
        secrets=[
            api_key_secret,
            api_secret_secret,
        ],

        startup_timeout_seconds=300,
        image_pull_policy='Always',
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
        kubernetes_conn_id=None,
    )
