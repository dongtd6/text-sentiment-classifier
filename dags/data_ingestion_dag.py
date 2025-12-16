from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.cncf.kubernetes.secret import Secret
from kubernetes.client import models as k8s

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
    description='DAG for Binance C2C data ingestion and Bronze/Silver/Gold processing',
    start_date=datetime(2023, 1, 1),
    schedule='@daily',
    catchup=False,
    tags=['ingestion', 'binance', 'lakehouse']
) as dag:

    # Task 1: Ingest data from API and write to Bronze
    # COMMENTED OUT: Bronze data already ingested, no need to re-run
    # bronze_task = KubernetesPodOperator(
    #     task_id='bronze_ingestion',
    #     name='bronze-ingestion',
    #     namespace='orchestration',
    #     image='asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/batch-app:latest',
    #     cmds=["python3", "etl_jobs/ingestion.py"],
    #     secrets=[api_key_secret, api_secret_secret],
    #     image_pull_policy='Always',
    #     is_delete_operator_pod=True,
    #     get_logs=True,
    #     in_cluster=True,
    #     kubernetes_conn_id=None,
    # )

    # Task 2: Transform Bronze to Silver
    # COMMENTED OUT: Silver data already processed, no need to re-run
    # NOTE: By default (no env vars), processes ALL Bronze data (for initial run)
    # To enable daily incremental mode later, uncomment the env line below:
    # silver_task = KubernetesPodOperator(
    #     task_id='silver_transformation',
    #     name='silver-transformation',
    #     namespace='orchestration',
    #     image='asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/batch-app:latest',
    #     cmds=["python3", "etl_jobs/silver_job.py"],
    #     # env_vars={"DATE_FILTER": "yesterday"},  # Uncomment for daily incremental mode
    #     image_pull_policy='Always',
    #     is_delete_operator_pod=True,
    #     get_logs=True,
    #     in_cluster=True,
    #     kubernetes_conn_id=None,
    # )

    # Task 3: Transform Silver to Gold and upload to GCS
    # NOTE: Processes ALL Silver data to build dimension tables and fact table
    # GCS credentials are mounted from Kubernetes Secret (secure, production-ready)
    gold_task = KubernetesPodOperator(
        task_id='gold_transformation',
        name='gold-transformation',
        namespace='orchestration',
        image='asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/batch-app:latest',
        cmds=["python3", "etl_jobs/gold_job.py"],
        env_vars={
            "GCS_BUCKET": "binance-gold-bucket",  # UPDATE this with your actual GCS bucket name
            "GCS_PREFIX": "gold_backup",
            "GCS_WORKERS": "16",
            "GCS_USE_THREADS": "true",  # true = ThreadPoolExecutor (recommended for I/O-bound GCS uploads)
            "GOOGLE_APPLICATION_CREDENTIALS": "/secrets/google-auth.json"  # Path where secret is mounted
        },
        # Mount GCS credentials from Kubernetes Secret
        volumes=[
            k8s.V1Volume(
                name='gcs-credentials',
                secret=k8s.V1SecretVolumeSource(secret_name='gcs-credentials')
            )
        ],
        volume_mounts=[
            k8s.V1VolumeMount(
                name='gcs-credentials',
                mount_path='/secrets',
                read_only=True
            )
        ],
        image_pull_policy='Always',
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
        kubernetes_conn_id=None,
    )

    # Define task dependencies
    # bronze_task >> silver_task >> gold_task  # Full pipeline (all commented for now)
    gold_task  # Run gold_task standalone (bronze & silver data already exist)

