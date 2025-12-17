"""
Simple C2C Streaming Pipeline DAG
One task that does everything:
- Fetch data from Binance C2C API
- Insert into c2c.trades table
- Send Telegram notification with results

CDC and Flink will be set up separately.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.cncf.kubernetes.secret import Secret

# Define Kubernetes secrets
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

db_password_secret = Secret(
    deploy_type='env',
    deploy_target='DB_PASSWORD',
    secret='postgresql',
    key='postgres-password'
)

# Telegram secrets
telegram_bot_token_secret = Secret(
    deploy_type='env',
    deploy_target='TELEGRAM_BOT_TOKEN',
    secret='telegram-secrets',
    key='bot-token'
)

telegram_chat_id_secret = Secret(
    deploy_type='env',
    deploy_target='TELEGRAM_CHAT_ID',
    secret='telegram-secrets',
    key='chat-id'
)

# Default arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# Create DAG
with DAG(
    dag_id='c2c_simple_streaming',
    default_args=default_args,
    description='C2C streaming: Ingest + Insert + Telegram (all in one)',
    schedule='@hourly',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['c2c', 'streaming', 'simple']
) as dag:
    
    # ============================================================
    # SINGLE TASK: Ingest Data + Insert + Send Telegram
    # ============================================================
    
    c2c_streaming_job = KubernetesPodOperator(
        task_id='c2c_streaming_complete',
        name='c2c-streaming-all-in-one',
        namespace='orchestration',
        image='asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/stream-app:latest',
        cmds=["python3", "/app/c2c_data_streaming.py"],
        env_vars={
            "FETCH_MODE": "latest",  # Fetch latest data (current day)
            "DB_HOST": "postgresql.storage.svc.cluster.local",
            "DB_PORT": "5432",
            "DB_NAME": "postgres",
            "DB_USER": "pgadmin"
        },
        secrets=[
            api_key_secret, 
            api_secret_secret, 
            db_password_secret,
            telegram_bot_token_secret,
            telegram_chat_id_secret
        ],
        image_pull_policy='Always',
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
        kubernetes_conn_id=None,
    )

