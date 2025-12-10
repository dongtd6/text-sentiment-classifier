from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.cncf.kubernetes.secret import Secret

# ----------------- CONFIGURATION -----------------
# Secrets for Binance API
api_key_secret = Secret('env', 'BINANCE_API_KEY', 'airflow-producer-secret', 'API_KEY')
api_secret_secret = Secret('env', 'BINANCE_API_SECRET', 'airflow-producer-secret', 'API_SECRET')

# Secrets for MinIO (S3) - Assuming you have these secrets in K8s
minio_access_key = Secret('env', 'MINIO_ROOT_USER', 'minio-secret', 'access_key')
minio_secret_key = Secret('env', 'MINIO_ROOT_PASSWORD', 'minio-secret', 'secret_key')

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='c2c_bronze_etl_dag',
    default_args=default_args,
    description='Ingest Binance C2C data and process to Bronze Delta Lake (Combined Task)',
    start_date=datetime(2023, 1, 1),
    schedule='@daily',
    catchup=False,
    tags=['ingestion', 'bronze', 'binance']
) as dag:

    # Combined Task: Fetch API -> Spark -> MinIO
    # Runs ingest_to_bronze.py which does everything in memory
    ingest_bronze_task = KubernetesPodOperator(
        task_id='ingest_and_process_bronze',
        name='ingest-bronze',
        namespace='orchestration',
        image='asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/batch-app:latest',
        cmds=["python", "ingest_to_bronze.py"],
        env_vars={
            'BRONZE_PATH': 's3a://bronze/c2c_trades/',
            'MINIO_ENDPOINT': 'http://minio.orchestration.svc.cluster.local:9000', # Internal K8s DNS for MinIO
        },
        secrets=[api_key_secret, api_secret_secret, minio_access_key, minio_secret_key],
        image_pull_policy='Always',
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
        kubernetes_conn_id=None,
    )
    
    ingest_bronze_task
