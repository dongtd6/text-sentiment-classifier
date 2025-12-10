from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.cncf.kubernetes.secret import Secret
from airflow.kubernetes.volume import Volume
from airflow.kubernetes.volume_mount import VolumeMount
from kubernetes.client.models import V1PersistentVolumeClaimVolumeSource

# ----------------- CONFIGURATION -----------------
# Secrets for Binance API
api_key_secret = Secret('env', 'BINANCE_API_KEY', 'airflow-producer-secret', 'API_KEY')
api_secret_secret = Secret('env', 'BINANCE_API_SECRET', 'airflow-producer-secret', 'API_SECRET')

# Secrets for MinIO (S3) - Assuming you have these secrets in K8s
minio_access_key = Secret('env', 'MINIO_ROOT_USER', 'minio-secret', 'access_key')
minio_secret_key = Secret('env', 'MINIO_ROOT_PASSWORD', 'minio-secret', 'secret_key')

# Volume for sharing data between tasks
# We use a PVC named 'airflow-shared-pvc' which should exist in your K8s
volume_config = {
    'persistentVolumeClaim': {
        'claimName': 'airflow-shared-pvc'
    }
}
volume = Volume(name='shared-data', configs=volume_config)
volume_mount = VolumeMount('shared-data', mount_path='/shared_volume', sub_path=None, read_only=False)

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='c2c_bronze_etl_dag',
    default_args=default_args,
    description='Ingest Binance C2C data and process to Bronze Delta Lake',
    start_date=datetime(2023, 1, 1),
    schedule='@daily',
    catchup=False,
    tags=['ingestion', 'bronze', 'binance']
) as dag:

    # 1. Ingestion Task
    # Runs ingestion.py which fetches data and writes to /shared_volume (we need to modify ingestion.py to support this)
    # OR we pass an environment variable to tell it where to save
    ingestion_task = KubernetesPodOperator(
        task_id='ingest_c2c_data',
        name='ingest-c2c-data',
        namespace='orchestration',
        image='asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/batch-app:latest',
        cmds=["python", "ingestion.py"],
        env_vars={
            # Tell ingestion where to save data (you might need to update ingestion.py to use this)
            'OUTPUT_DIR': '/shared_volume/c2c/landing' 
        },
        secrets=[api_key_secret, api_secret_secret],
        volumes=[volume],
        volume_mounts=[volume_mount],
        image_pull_policy='Always',
        is_delete_operator_pod=True,
        get_logs=True,
    )

    # 2. Bronze Job Task
    # Runs bronze_job.py (Spark) to read from /shared_volume and write to MinIO
    bronze_task = KubernetesPodOperator(
        task_id='process_bronze',
        name='process-bronze',
        namespace='orchestration',
        image='asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/batch-app:latest',
        cmds=["python", "bronze_job.py"],
        env_vars={
            'INPUT_PATH': '/shared_volume/c2c/landing/*.parquet',
            'BRONZE_PATH': 's3a://bronze/c2c_trades/',
            'MINIO_ENDPOINT': 'http://minio.orchestration.svc.cluster.local:9000', # Internal K8s DNS for MinIO
        },
        secrets=[minio_access_key, minio_secret_key],
        volumes=[volume],
        volume_mounts=[volume_mount],
        image_pull_policy='Always',
        is_delete_operator_pod=True,
        get_logs=True,
    )

    ingestion_task >> bronze_task

