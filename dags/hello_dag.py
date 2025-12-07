from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='hello_world_dag',
    default_args=default_args,
    description='A simple Hello World DAG',
    start_date=datetime(2023, 1, 1),
    schedule='@daily',
    catchup=False,
) as dag:

    hello_task = BashOperator(
        task_id='hello_task',
        bash_command='echo "Hello World!"',
    )

    hello_task

