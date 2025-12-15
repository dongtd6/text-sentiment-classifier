# jobs/common/utils.py
import os

import yaml
from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # /job/jobs
CONFIG_PATH = os.path.join(BASE_DIR, "configs", "config.yml")
with open(CONFIG_PATH) as f:
    cfg = yaml.safe_load(f)

JARS_DIR = os.path.join(os.path.dirname(BASE_DIR), "jars")  # /job/jars

jars = [
    os.path.join(JARS_DIR, "postgresql-42.6.0.jar"),
    os.path.join(JARS_DIR, "deequ-2.0.3-spark-3.3.jar"),
    os.path.join(JARS_DIR, "hadoop-aws-3.3.2.jar"),
    os.path.join(JARS_DIR, "aws-java-sdk-bundle-1.11.1026.jar"),
]

jars_str = ",".join(jars)


def get_spark(app_name: str):
    endpoint = cfg["s3"]["endpoint"]
    access_key = cfg["s3"]["access_key"]
    secret_key = cfg["s3"]["secret_key"]
    # bucket = cfg["s3"]["bucket"] # Removed
    
    metastore_host = cfg["metastore"]["host"]
    builder = (
        SparkSession.builder.master("local[*]")
        .appName(app_name)
        .config("spark.ui.port", "4042")
        # Delta config
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        # Hive Metastore config
        .config("spark.sql.catalogImplementation", "hive")
        .config("spark.hadoop.hive.metastore.uris", metastore_host)
        # Default warehouse to bronze bucket for now, or could be a separate system bucket
        .config("spark.sql.warehouse.dir", "s3a://bronze/warehouse")
        .config(
            "spark.hadoop.hive.metastore.warehouse.dir", "s3a://bronze/warehouse"
        )
        # S3 config
        .config("spark.jars", jars_str)
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.endpoint", endpoint)
        .config("spark.hadoop.fs.s3a.access.key", access_key)
        .config("spark.hadoop.fs.s3a.secret.key", secret_key)
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")  # Disable SSL
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        # S3A timeout configurations (must be in milliseconds, not with time units)
        .config("spark.hadoop.fs.s3a.connection.timeout", "200000")  # 200 seconds
        .config("spark.hadoop.fs.s3a.connection.establish.timeout", "60000")  # 60 seconds
        .config("spark.hadoop.fs.s3a.attempts.maximum", "10")
        .config("spark.hadoop.fs.s3a.connection.maximum", "15")
        .config("spark.hadoop.fs.s3a.threads.max", "10")
    )
    spark = configure_spark_with_delta_pip(builder).enableHiveSupport().getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark
