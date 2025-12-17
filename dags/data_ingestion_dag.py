from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.cncf.kubernetes.secret import Secret
from kubernetes.client import models as k8s

# Define where to fetch secrets from in Kubernetes
# This maps the Kubernetes Secret 'airflow-producer-secret' key 'API_KEY' 
# to the environment variable 'BINANCE_API_KEY' inside the pod
api_key_secret = Secret('env', 
'BINANCE_API_KEY', 
'airflow-producer-secret', 
'API_KEY')
api_secret_secret = Secret('env', 
'BINANCE_API_SECRET', 
'airflow-producer-secret', 
'API_SECRET')

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
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

    # Task 3a: Transform Silver to Gold (Aggregated) - OLD VERSION
    # COMMENTED OUT: Using V1 (transaction-level) instead
    # gold_task = KubernetesPodOperator(
    #     task_id='gold_transformation',
    #     name='gold-transformation',
    #     namespace='orchestration',
    #     image='asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/batch-app:latest',
    #     cmds=["python3", "etl_jobs/gold_job.py"],
    #     env_vars={
    #         "GCS_BUCKET": "binance-gold-bucket",
    #         "GCS_PREFIX": "gold_backup",
    #         "GCS_WORKERS": "16",
    #         "GCS_USE_THREADS": "true",
    #         "GOOGLE_APPLICATION_CREDENTIALS": "/secrets/google-auth.json"
    #     },
    #     volumes=[
    #         k8s.V1Volume(
    #             name='gcs-credentials',
    #             secret=k8s.V1SecretVolumeSource(secret_name='gcs-credentials')
    #         )
    #     ],
    #     volume_mounts=[
    #         k8s.V1VolumeMount(
    #             name='gcs-credentials',
    #             mount_path='/secrets',
    #             read_only=True
    #         )
    #     ],
    #     image_pull_policy='Always',
    #     is_delete_operator_pod=True,
    #     get_logs=True,
    #     in_cluster=True,
    #     kubernetes_conn_id=None,
    # )

    # Task 3b: Transform Silver to Gold V1 (Transaction-Level Fact)
    # NOTE: Transaction-level fact table (NO aggregation)
    # - PK: order_number
    # - Includes dim_order_status
    # - User calculates metrics in dashboard
    gold_task_v1 = KubernetesPodOperator(
        task_id='gold_transformation_v1',
        name='gold-transformation-v1',
        namespace='orchestration',
        image='asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/batch-app:latest',
        cmds=["python3", "etl_jobs/gold_job_v1.py"],
        env_vars={
            "GCS_BUCKET": "binance-gold-bucket",
            "GCS_PREFIX": "gold_v1_backup",  # Different prefix to separate V0 and V1
            "GCS_WORKERS": "16",
            "GCS_USE_THREADS": "true",
            "GOOGLE_APPLICATION_CREDENTIALS": "/secrets/google-auth.json"
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
    # bronze_task >> silver_task >> gold_task_v1  # Full pipeline (all commented for now)
    gold_task_v1  # Run gold_task_v1 standalone (bronze & silver data already exist)

