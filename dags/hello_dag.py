from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='hello_world_dag',
    default_args=default_args,
    description='A simple Hello World DAG using KubernetesPodOperator',
    start_date=datetime(2023, 1, 1),
    schedule='@daily',
    catchup=False,
) as dag:

    hello_task = KubernetesPodOperator(
        task_id='hello_task',
        name='hello-task',
        namespace='airflow',
        image='asia-southeast1-docker.pkg.dev/binance-test-479915/bnb-c2c-images/hello-python:v1',
        cmds=['python', '-c', 'print("Hello World from K8s!")'],
        image_pull_policy='Always',
        is_delete_operator_pod=True,
        get_logs=True,
    )

    hello_task
