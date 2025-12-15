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
        # Warehouse dir - will be set after Hadoop config is properly initialized
        # Temporarily use a placeholder to avoid early S3A initialization
        .config("spark.hadoop.hive.metastore.warehouse.dir", "s3a://bronze/warehouse")
        # S3 config
        .config("spark.jars", jars_str)
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.endpoint", endpoint)
        .config("spark.hadoop.fs.s3a.access.key", access_key)
        .config("spark.hadoop.fs.s3a.secret.key", secret_key)
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")  # Disable SSL
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        # S3A timeout configurations (must be in milliseconds as integers, NOT with time units like "60s")
        # These override Hadoop's default time-unit-based values that cause NumberFormatException
        .config("spark.hadoop.fs.s3a.connection.timeout", "200000")  # 200 seconds in ms
        .config("spark.hadoop.fs.s3a.connection.establish.timeout", "60000")  # 60 seconds in ms
        .config("spark.hadoop.fs.s3a.attempts.maximum", "10")
        .config("spark.hadoop.fs.s3a.connection.maximum", "15")
        .config("spark.hadoop.fs.s3a.threads.max", "10")
        .config("spark.hadoop.fs.s3a.threads.core", "5")
        .config("spark.hadoop.fs.s3a.max.total.tasks", "10")
        .config("spark.hadoop.fs.s3a.socket.send.buffer", "8192")
        .config("spark.hadoop.fs.s3a.socket.recv.buffer", "8192")
        .config("spark.hadoop.fs.s3a.paging.maximum", "5000")
        .config("spark.hadoop.fs.s3a.block.size", "33554432")  # 32MB
        .config("spark.hadoop.fs.s3a.buffer.dir", "/tmp")
        .config("spark.hadoop.fs.s3a.fast.upload", "true")
        .config("spark.hadoop.fs.s3a.multipart.size", "104857600")  # 100MB
        .config("spark.hadoop.fs.s3a.multipart.threshold", "2147483647")  # 2GB
    )
    spark = configure_spark_with_delta_pip(builder).enableHiveSupport().getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    
    # Set Hadoop S3A configurations directly on the Hadoop Configuration object
    # This ensures they override any defaults that might use time units
    hadoop_conf = spark.sparkContext._jsc.hadoopConfiguration()
    hadoop_conf.set("fs.s3a.connection.timeout", "200000")
    hadoop_conf.set("fs.s3a.connection.establish.timeout", "60000")
    hadoop_conf.set("fs.s3a.attempts.maximum", "10")
    hadoop_conf.set("fs.s3a.connection.maximum", "15")
    hadoop_conf.set("fs.s3a.threads.max", "10")
    hadoop_conf.set("fs.s3a.endpoint", endpoint)
    hadoop_conf.set("fs.s3a.access.key", access_key)
    hadoop_conf.set("fs.s3a.secret.key", secret_key)
    hadoop_conf.set("fs.s3a.connection.ssl.enabled", "false")
    hadoop_conf.set("fs.s3a.path.style.access", "true")
    hadoop_conf.set("fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    
    return spark
