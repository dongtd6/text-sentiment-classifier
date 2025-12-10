import logging
import sys
import traceback

from pyspark import SparkContext
from pyspark.sql import SparkSession

_PACKAGES = ",".join(
    [
        # Delta for Spark 3.5.x (Scala 2.12)
        "io.delta:delta-spark_2.12:3.2.0",
        # Use Spark’s curated Hadoop/S3A bundle to avoid version drift
        "org.apache.spark:spark-hadoop-cloud_2.12:3.5.1",
    ]
)


def create_spark_session(
    memory: str,
    app_name: str = "Batch Processing Application",
    extra_packages: str = "",
) -> SparkSession:
    try:
        logging.info("Initializing Spark session...")

        packages = _PACKAGES if not extra_packages else f"{_PACKAGES},{extra_packages}"

        spark = (
            SparkSession.builder.appName(app_name)
            .config("spark.executor.memory", memory)
            .config("spark.driver.memory", memory)
            .config("spark.jars.packages", packages)
            # Do NOT force userClassPathFirst; let Spark resolve its own Hadoop set
            .config("spark.sql.execution.arrow.pyspark.enabled", "true")
            # Delta
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
            .config(
                "spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog",
            )
            .getOrCreate()
        )

        logging.info("✅ Spark session created successfully.")
        return spark

    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        logging.error(f"❌ Failed to create Spark session: {e}")
        raise


def _normalize_endpoint(endpoint: str, secure: bool) -> str:
    """
    Ensure endpoint has scheme. For MinIO typically http://host:9000 (non-SSL) or https://...
    """
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    return f"{'https' if secure else 'http'}://{endpoint}"


def load_minio_config(spark_context: SparkContext, minio_cfg: dict):
    """
    Configure Hadoop S3A settings to connect to a MinIO storage endpoint.

    Expected keys in minio_cfg:
      - endpoint (str): 'host:port' or full URL
      - access_key (str)
      - secret_key (str)
      - secure (bool, optional): default False
    """
    try:
        logging.info("Applying MinIO configuration to Spark Hadoop settings...")
        hadoop_conf = spark_context._jsc.hadoopConfiguration()

        secure = bool(minio_cfg.get("secure", False))
        endpoint = _normalize_endpoint(minio_cfg["endpoint"], secure)

        hadoop_conf.set("fs.s3a.access.key", minio_cfg["access_key"])
        hadoop_conf.set("fs.s3a.secret.key", minio_cfg["secret_key"])
        hadoop_conf.set("fs.s3a.endpoint", endpoint)
        hadoop_conf.set(
            "fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        hadoop_conf.set("fs.s3a.path.style.access", "true")
        hadoop_conf.set("fs.s3a.connection.ssl.enabled", "true" if secure else "false")
        hadoop_conf.set("fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")

        logging.info("✅ MinIO configuration loaded successfully.")

    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        logging.error(f"❌ Failed to configure MinIO: {e}")
        raise