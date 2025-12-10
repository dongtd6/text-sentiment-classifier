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
    description='DAG for Binance C2C data ingestion',
    start_date=datetime(2023, 1, 1),
    schedule='@daily',
    catchup=False,
    tags=['ingestion', 'binance']
) as dag:

    # Task to ingest yesterday's data
    ingest_yesterday_task = KubernetesPodOperator(
        task_id='ingest_yesterday_data',
        name='ingest-yesterday-data',
        namespace='orchestration',
        # Use the image built from dockerfiles/batch-processing/Dockerfile
        image='asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/batch-app:latest',
        # Now we can just run the script directly since it's the CMD/Entrypoint or available in path
        cmds=["python", "ingestion.py"],
        secrets=[api_key_secret, api_secret_secret],
        image_pull_policy='Always',
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
        kubernetes_conn_id=None,
    )

    ingest_yesterday_task
