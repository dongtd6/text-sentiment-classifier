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
    bucket = cfg["s3"]["bucket"]
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
        .config("spark.sql.warehouse.dir", f"s3a://{bucket}/warehouse")
        .config(
            "spark.hadoop.hive.metastore.warehouse.dir", f"s3a://{bucket}/warehouse"
        )
        # S3 config
        .config("spark.jars", jars_str)
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.endpoint", endpoint)
        .config("spark.hadoop.fs.s3a.access.key", access_key)
        .config("spark.hadoop.fs.s3a.secret.key", secret_key)
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")  # Disable SSL
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
    )
    spark = configure_spark_with_delta_pip(builder).enableHiveSupport().getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark
    # .config("spark.hadoop.fs.s3a.fast.upload", "true")
    # .config("spark.hadoop.fs.s3a.fast.upload.buffer", "disk")
    # .config("spark.hadoop.fs.s3a.multipart.size", "104857600")
    # .config("spark.hadoop.fs.s3a.threads.max", "256")
    # .config("spark.hadoop.fs.s3a.connection.maximum", "100")
    # .config("spark.hadoop.fs.s3a.attempts.maximum", "3")
    # .config("spark.hadoop.fs.s3a.retry.limit", "3")
    # .config("spark.hadoop.fs.s3a.retry.interval", "500ms")
    # .config("spark.hadoop.fs.s3a.paging.maximum", "1000")
    # .config("spark.hadoop.fs.s3a.signing-algorithm", "S3SignerType")
    # .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
    # .config("spark.hadoop.fs.s3a.connection.timeout", "5000")
    # .config("spark.hadoop.fs.s3a.connection.establish.timeout", "5000")
    # .config("spark.hadoop.fs.s3a.socket.timeout", "5000")
    # .config("spark.hadoop.fs.s3a.threads.keepalivetime", "60s")
    # .config("spark.hadoop.fs.s3a.threads.core", "10")
    # .config("spark.hadoop.fs.s3a.threads.max", "50")
    # .config("spark.hadoop.fs.s3a.buffer.directory", "/tmp/spark-s3a")
    # .config("spark.hadoop.fs.s3a.acl.default", "BucketOwnerFullControl")
    # .config("spark.hadoop.fs.s3a.acl.bucket.default", "BucketOwnerFullControl")

    # .config("spark.sql.shuffle.partitions", "4")
    # .config("spark.default.parallelism", "4")
    # .config("spark.driver.memory", "2g")
    # .config("spark.executor.memory", "2g")
    # .config("spark.executor.cores", "1")
    # .config("spark.sql.autoBroadcastJoinThreshold", "-1")  # Disable broadcast joins
    # .config("spark.sql.adaptive.enabled", "true")  # Enable adaptive query execution
    # .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
    # .config("spark.sql.adaptive.coalescePartitions.minPartitionNum", "2")
    # .config("spark.sql.adaptive.coalescePartitions.initialPartitionNum", "4")
    # .config("spark.sql.adaptive.skewJoin.enabled", "true")
    # .config("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "256000000")
    # .config("spark.sql.adaptive.skewJoin.maxNumSkewedPartitions", "10")
    # .config("spark.sql.adaptive.skewJoin.minNumPartitionsForSkewedJoin", "8")
    # .config("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "4")
    # .config("spark.sql.adaptive.skewJoin.optimizeSkewedJoinWithSalt", "true")
    # .config("spark.sql.adaptive.skewJoin.saltFactor", "10")
    # .config("spark.sql.adaptive.skewJoin.saltMax", "100")
    # .config("spark.sql.adaptive.skewJoin.saltMin", "1")
    # .config("spark.sql.adaptive.skewJoin.saltNumBits", "10")
    # .config("spark.sql.adaptive.skewJoin.saltSeed", "42")
    # .config("spark.sql.adaptive.skewJoin.saltShufflePartitions", "true")
    # .config("spark.sql.adaptive.skewJoin.saltShuffleSeed", "42")
    # .config("spark.sql.adaptive.skewJoin.saltShuffleNumPartitions", "4")
    # .config("spark.sql.adaptive.skewJoin.saltShuffleMinPartitionSize", "64MB")
    # .config("spark.sql.adaptive.skewJoin.saltShuffleMaxPartitionSize", "256MB")
    # .config("spark.sql.adaptive.skewJoin.saltShuffleTargetPartitionSize", "128MB")
    # .config("spark.sql.adaptive.skewJoin.saltShuffleMaxNumPartitions", "200")
    # .config("spark.sql.adaptive.skewJoin.saltShuffleMinNumPartitions", "10")
    # .config("spark.sql.adaptive.skewJoin.saltShuffleInitialNumPartitions", "50")
    # .config("spark.sql.adaptive.skewJoin.saltShuffleFinalNumPartitions", "100")
    # .config("spark.sql.adaptive.skewJoin.saltShufflePartitionSizeFactor", "1.5")
    # .config("spark.sql.adaptive.skewJoin.saltShufflePartitionSizeExponent", "1.2")
    # .config("spark.sql.adaptive.skewJoin.saltShufflePartitionSizeBase", "64MB")
