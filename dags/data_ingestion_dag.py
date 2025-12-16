from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.cncf.kubernetes.secret import Secret

# Define where to fetch secrets from in Kubernetes
# This maps the Kubernetes Secret 'airflow-producer-secret' key 'API_KEY' 
# to the environment variable 'BINANCE_API_KEY' inside the pod
api_key_secret = Secret('env', 'BINANCE_API_KEY', 'airflow-producer-secret', 'API_KEY')
api_secret_secret = Secret('env', 'BINANCE_API_SECRET', 'airflow-producer-secret', 'API_SECRET')

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='data_ingestion_dag',
    default_args=default_args,
    description='DAG for Binance C2C data ingestion and Bronze/Silver processing',
    start_date=datetime(2023, 1, 1),
    schedule='@daily',
    catchup=False,
    tags=['ingestion', 'binance', 'lakehouse']
) as dag:

    # Task 1: Ingest data from API and write to Bronze
    bronze_task = KubernetesPodOperator(
        task_id='bronze_ingestion',
        name='bronze-ingestion',
        namespace='orchestration',
        image='asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/batch-app:latest',
        cmds=["python3", "etl_jobs/ingestion.py"],
        secrets=[api_key_secret, api_secret_secret],
        image_pull_policy='Always',
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
        kubernetes_conn_id=None,
    )

    # Task 2: Transform Bronze to Silver
    silver_task = KubernetesPodOperator(
        task_id='silver_transformation',
        name='silver-transformation',
        namespace='orchestration',
        image='asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/batch-app:latest',
        cmds=["python3", "etl_jobs/silver_job.py"],
        image_pull_policy='Always',
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
        kubernetes_conn_id=None,
    )

    # Define task dependencies
    bronze_task >> silver_task
