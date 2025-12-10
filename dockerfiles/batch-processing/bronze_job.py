import logging
import os
import sys

# Add /app to python path to allow importing from common and configs
sys.path.append("/app")

from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    col,
    year,
    month,
    dayofmonth,
    from_unixtime,
    from_utc_timestamp,
    to_date,
)
from pyspark.sql.types import LongType

# Import helpers from common package
from common.utils import get_spark
from common.io import write_delta

# --------------------- LOGGING & CONFIG ---------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bronze_job")

# Paths and Configs
BRONZE_TABLE_NAME = "c2c_trades_bronze"
BRONZE_PATH = os.getenv("BRONZE_PATH", "s3a://tsc-bucket/bronze/c2c_trades/")
APP_NAME = "BronzeJob"


def add_trade_date(df: DataFrame) -> DataFrame:
    """
    Add `trade_date` + year/month/day partitions.
    Handles timestamp columns correctly and ensures proper timezone.
    """
    # If already exists (e.g., re-ingest)
    if "trade_date" in df.columns:
        logger.info("trade_date already exists → only generating partitions.")
        return (
            df.withColumn("year", year("trade_date"))
            .withColumn("month", month("trade_date"))
            .withColumn("day", dayofmonth("trade_date"))
        )

    # Detect timestamp column
    timestamp_col = None
    for c in ["createTime", "create_time_ms", "create_time"]:
        if c in df.columns:
            timestamp_col = c
            break

    if not timestamp_col:
        raise Exception(
            "❌ No timestamp column found (createTime/create_time_ms/create_time).\n"
            "Bronze ingest cannot determine trade_date."
        )

    logger.info(f"Using timestamp column: {timestamp_col}")

    # Force timestamp column to long(epoch ms)
    df = df.withColumn(timestamp_col, col(timestamp_col).cast(LongType()))

    # Convert epoch(ms) → timestamp(UTC) → timestamp(Asia/Ho_Chi_Minh)
    df = df.withColumn(
        "create_ts_utc",
        from_unixtime(col(timestamp_col) / 1000)  # epoch → string timestamp UTC
    ).withColumn(
        "create_ts",
        from_utc_timestamp("create_ts_utc", "Asia/Ho_Chi_Minh")
    )

    # Create trade_date + partitions
    df = (
        df.withColumn("trade_date", to_date("create_ts"))
        .withColumn("year", year("trade_date"))
        .withColumn("month", month("trade_date"))
        .withColumn("day", dayofmonth("trade_date"))
        .drop("create_ts_utc")  # cleanup
        .drop("create_ts")
    )

    return df


def deduplicate(df: DataFrame) -> DataFrame:
    """
    Drop duplicates by orderNumber (if exists).
    This protects Bronze from re-ingestion duplication.
    """
    if "orderNumber" in df.columns:
        before = df.count()
        df = df.dropDuplicates(["orderNumber"])
        after = df.count()
        logger.info(
            f"Deduplication: {before} → {after} rows after removing duplicates."
        )
    elif "order_number" in df.columns:  # Handle case-insensitive or alternate naming
        before = df.count()
        df = df.dropDuplicates(["order_number"])
        after = df.count()
        logger.info(
            f"Deduplication: {before} → {after} rows after removing duplicates."
        )
    else:
        logger.warning(
            "No orderNumber/order_number column found → skipping deduplication."
        )
    return df


def main():
    try:
        logger.info("Starting Bronze Job (Production Optimized)...")
        
        # Initialize Spark using common utility
        spark = get_spark(APP_NAME)
        spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")

        # Input Path from Env (set by DAG)
        input_path = os.getenv("INPUT_PATH", "/app/data/c2c_trades_*.parquet")
        logger.info(f"Reading input data from: {input_path}")

        df = spark.read.option("mergeSchema", "false").parquet(input_path)

        logger.info("Schema loaded:")
        df.printSchema()

        # Extract trade_date safely
        df = add_trade_date(df)

        # Protect Bronze from duplicates
        df = deduplicate(df)

        # Reduce small files
        df = df.coalesce(4)

        # Final sanity check
        null_partitions = df.filter(
            col("year").isNull() | col("month").isNull() | col("day").isNull()
        ).count()

        if null_partitions > 0:
            raise Exception(
                f"❌ Found {null_partitions} rows with NULL partitions (year/month/day)."
            )

        # Write to Delta Lake (Bronze) using common IO utility
        # Note: write_delta takes (dataframe, table_name, path, mode)
        # We modify write_delta slightly or just call standard write here if partitions needed specific handling
        # Since write_delta in io.py is generic, let's look at it.
        # It uses saveAsTable which registers in Hive Metastore.
        
        logger.info(f"Writing to Bronze Delta → {BRONZE_PATH}")
        
        # Writing with partitioning
        (
            df.write.format("delta")
            .mode("append")
            .option("path", BRONZE_PATH)
            .partitionBy("year", "month", "day")
            .saveAsTable(BRONZE_TABLE_NAME)
        )
        
        logger.info("✅ Bronze write completed successfully!")

    except Exception as e:
        logger.exception(f"❌ Bronze Job Failed: {e}")
        sys.exit(1)
    finally:
        if "spark" in locals():
            spark.stop()
        logger.info("Spark session stopped.")


if __name__ == "__main__":
    main()
