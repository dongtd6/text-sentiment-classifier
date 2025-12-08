# # dags/airflow_dag.py
# from datetime import datetime

# from airflow import DAG
# from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

# image_name = "dongtd6/airflow-job-scripts:v1.39"
# default_args = {
#     "owner": "airflow",
#     "start_date": datetime(2025, 1, 1),
# }

# with DAG(
#     dag_id="masterdata_full_etl",
#     start_date=datetime(2025, 1, 1),
#     schedule="0 0 * * *",
#     default_args=default_args,
#     catchup=False,
# ) as dag:

#     extract_postgres_reviews = KubernetesPodOperator(
#         task_id="extract_postgres_reviews",
#         name="extract-postgres-reviews",
#         namespace="orchestration",
#         image=image_name,
#         cmds=["python", "jobs/extract_postgres_reviews.py"],
#         image_pull_policy="Always",
#         is_delete_operator_pod=True,
#         get_logs=True,
#     )

#     transform_reviews_sentiment = KubernetesPodOperator(
#         task_id="transform_reviews_sentiment",
#         name="transform-reviews-sentiment",
#         namespace="orchestration",
#         image=image_name,
#         cmds=["python", "jobs/transform_reviews_sentiment.py"],
#         is_delete_operator_pod=True,
#         get_logs=True,
#     )

#     aggregate_reviews_daily = KubernetesPodOperator(
#         task_id="aggregate_reviews_daily",
#         name="aggregate-reviews-daily",
#         namespace="orchestration",
#         image=image_name,
#         cmds=["python", "jobs/aggregate_reviews_daily.py"],
#         is_delete_operator_pod=True,
#         get_logs=True,
#     )

#     extract_postgres_reviews >> transform_reviews_sentiment >> aggregate_reviews_daily
