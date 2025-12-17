import os
import sys
import logging
from pathlib import Path
from typing import List
from datetime import datetime, timedelta

sys.path.append("/app")

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.types import IntegerType, StringType, StructType, StructField
from pyspark.sql.functions import (
    col, when, lit, year, month, dayofmonth, dayofweek, lower, 
    current_timestamp, row_number, md5, concat_ws
)
from pyspark.sql.window import Window
from delta.tables import DeltaTable

from common.utils import get_spark
from common.gcs_manager import GCSManager

# ========================= CONFIG & LOGGING ============================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("gold_job_v1")
logger.info("Starting Gold Job V1 (Transaction-Level Fact)")

SILVER_PATH = os.getenv("SILVER_PATH", "s3a://silver/c2c_trades/")
GOLD_LOCAL_PATH = os.getenv("GOLD_LOCAL_PATH", "/tmp/gold_delta_v1")
GCS_BUCKET = os.getenv("GCS_BUCKET", "")
GCS_PREFIX = os.getenv("GCS_PREFIX", "gold_v1_backup")
APP_NAME = "C2CGoldJobV1"

logger.info(f"SILVER_PATH={SILVER_PATH}")
logger.info(f"GOLD_LOCAL_PATH={GOLD_LOCAL_PATH}")
logger.info(f"GCS_BUCKET={GCS_BUCKET}")
logger.info(f"GCS_PREFIX={GCS_PREFIX}")

# ========================= DIM ORDER STATUS (NEW!) =====================
def build_dim_order_status(spark: SparkSession, dim_status_path: str) -> DataFrame:
    """
    Build order status dimension (static reference data).
    This is a junk dimension for order statuses.
    """
    logger.info("Building dim_order_status...")
    
    # Define all possible order statuses
    status_data = [
        (1, "COMPLETED", "Completed", "Successful", True, 8),
        (2, "CANCELLED", "Cancelled", "Failed", True, 2),
        (3, "CANCELLED_BY_SYSTEM", "Cancelled by System", "Failed", True, 1),
        (4, "IN_APPEAL", "In Appeal", "Pending", False, 7),
        (5, "DISTRIBUTING", "Distributing", "Processing", False, 6),
        (6, "BUYER_PAYED", "Buyer Payed", "Processing", False, 5),
        (7, "TRADING", "Trading", "Processing", False, 4),
        (8, "PENDING", "Pending", "Pending", False, 3),
        (9, "UNKNOWN", "Unknown", "Unknown", False, 0),
    ]
    
    schema = StructType([
        StructField("status_key", IntegerType(), False),
        StructField("status_code", StringType(), False),
        StructField("status_name", StringType(), False),
        StructField("status_category", StringType(), False),
        StructField("is_final_state", StringType(), False),  # Boolean as String for compatibility
        StructField("priority", IntegerType(), False),
    ])
    
    df_dim_status = spark.createDataFrame(status_data, schema)
    
    # Convert boolean to proper type
    df_dim_status = df_dim_status.withColumn(
        "is_final_state",
        when(col("is_final_state") == "true", lit(True)).otherwise(lit(False))
    )
    
    (
        df_dim_status.write
        .format("delta")
        .mode("overwrite")
        .save(dim_status_path)
    )
    
    logger.info(f"✅ dim_order_status written to {dim_status_path} (rows={len(status_data)})")
    return df_dim_status


# ========================= DIM DATE =====================================
def build_dim_date(spark: SparkSession, df_silver: DataFrame, dim_date_path: str) -> DataFrame:
    """
    Build date dimension from Silver trade_date range.
    Enhanced with more attributes.
    """
    logger.info("Building dim_date...")
    
    from pyspark.sql.functions import max as spark_max, sum as spark_sum, date_format, weekofyear
    
    agg = df_silver.agg(
        spark_max("trade_date").alias("max_date"),
        spark_sum(when(col("trade_date").isNotNull(), lit(1)).otherwise(lit(0))).alias("non_null_count")
    ).collect()[0]
    
    max_date = agg["max_date"]
    if not max_date or agg["non_null_count"] == 0:
        logger.warning("No valid trade_date found in Silver. Creating empty dim_date.")
        return spark.createDataFrame([], 
            "date_key INT, full_date DATE, day_of_week INT, day_name STRING, week_of_year INT, " +
            "month INT, month_name STRING, quarter INT, year INT, is_weekend BOOLEAN, fiscal_year INT")
    
    df_dates = (
        df_silver
        .select("trade_date")
        .where(col("trade_date").isNotNull())
        .distinct()
        .withColumnRenamed("trade_date", "full_date")
    )
    
    df_dim_date = (
        df_dates
        .withColumn(
            "date_key",
            (year("full_date") * 10000 + month("full_date") * 100 + dayofmonth("full_date")).cast(IntegerType())
        )
        .withColumn("day_of_week", dayofweek("full_date"))
        .withColumn("day_name", date_format("full_date", "EEEE"))
        .withColumn("week_of_year", weekofyear("full_date"))
        .withColumn("month", month("full_date"))
        .withColumn("month_name", date_format("full_date", "MMMM"))
        .withColumn("quarter", ((month("full_date") - 1) / 3 + 1).cast("int"))
        .withColumn("year", year("full_date"))
        .withColumn("is_weekend", when(col("day_of_week").isin(1, 7), lit(True)).otherwise(lit(False)))
        .withColumn("fiscal_year", year("full_date"))
    )
    
    (
        df_dim_date.write
        .format("delta")
        .mode("overwrite")
        .save(dim_date_path)
    )
    
    logger.info(f"✅ dim_date written to {dim_date_path} (rows={df_dim_date.count()})")
    return df_dim_date


# ========================= DIM ASSET ====================================
def build_dim_asset(df_silver: DataFrame, dim_asset_path: str) -> DataFrame:
    """
    Build asset dimension from Silver.
    Simple version without SCD (can be enhanced later).
    """
    logger.info("Building dim_asset...")
    
    w = Window.orderBy("asset_code")
    
    df_dim_asset = (
        df_silver
        .select(lower(col("asset")).alias("asset_code"))
        .where(col("asset").isNotNull())
        .distinct()
        .withColumn("asset_key", row_number().over(w).cast(IntegerType()))
        .withColumn("asset_name", col("asset_code"))
        .withColumn("is_stablecoin", when(col("asset_code") == "usdt", lit(True)).otherwise(lit(False)))
        .withColumn("created_at", current_timestamp())
    )
    
    (
        df_dim_asset.write
        .format("delta")
        .mode("overwrite")
        .save(dim_asset_path)
    )
    
    logger.info(f"✅ dim_asset written to {dim_asset_path} (rows={df_dim_asset.count()})")
    return df_dim_asset


# ========================= DIM FIAT =====================================
def build_dim_fiat(df_silver: DataFrame, dim_fiat_path: str) -> DataFrame:
    """
    Build fiat dimension from Silver.
    Simple version without SCD (can be enhanced later).
    """
    logger.info("Building dim_fiat...")
    
    w = Window.orderBy("fiat_code")
    
    df_dim_fiat = (
        df_silver
        .select(lower(col("fiat")).alias("fiat_code"))
        .where(col("fiat").isNotNull())
        .distinct()
        .withColumn("fiat_key", row_number().over(w).cast(IntegerType()))
        .withColumn("fiat_name", col("fiat_code"))
        .withColumn("currency_symbol", when(col("fiat_code") == "vnd", lit("₫")).otherwise(lit("$")))
        .withColumn("is_local", when(col("fiat_code") == "vnd", lit(True)).otherwise(lit(False)))
    )
    
    (
        df_dim_fiat.write
        .format("delta")
        .mode("overwrite")
        .save(dim_fiat_path)
    )
    
    logger.info(f"✅ dim_fiat written to {dim_fiat_path} (rows={df_dim_fiat.count()})")
    return df_dim_fiat


# ========================= FACT TABLE (Transaction Level) ==============
def build_fact_transaction(
    df_silver: DataFrame,
    df_dim_date: DataFrame,
    df_dim_asset: DataFrame,
    df_dim_fiat: DataFrame,
    df_dim_status: DataFrame,
    fact_path: str,
    spark: SparkSession
) -> None:
    """
    Build transaction-level fact table (NO AGGREGATION).
    Each row = 1 order from Silver.
    PK = order_number
    
    User will do their own aggregations in the dashboard.
    """
    logger.info("Building fact_c2c_trades (transaction level)...")
    
    # Select relevant columns from Silver (transaction grain)
    df_fact = df_silver.select(
        col("order_number"),
        col("trade_date"),
        lower(col("asset")).alias("asset"),
        lower(col("fiat")).alias("fiat"),
        col("order_status"),
        col("trade_type"),
        col("amount"),
        col("unit_price"),
        col("total_price"),
        col("commission"),
        col("net_volume"),
        col("adv_no"),
        col("advertisement_role"),
        col("counter_part_nick_name"),
        col("year"),
        col("month"),
        col("day")
    )
    
    # Add date_key
    df_fact = df_fact.withColumn(
        "date_key",
        (year(col("trade_date")) * 10000 + month(col("trade_date")) * 100 + dayofmonth(col("trade_date"))).cast(IntegerType())
    )
    
    # Join with dim_asset to get asset_key
    df_fact = (
        df_fact
        .join(
            df_dim_asset.select("asset_key", "asset_code"),
            df_fact["asset"] == df_dim_asset["asset_code"],
            "left"
        )
        .drop("asset_code")
    )
    
    # Join with dim_fiat to get fiat_key
    df_fact = (
        df_fact
        .join(
            df_dim_fiat.select("fiat_key", "fiat_code"),
            df_fact["fiat"] == df_dim_fiat["fiat_code"],
            "left"
        )
        .drop("fiat_code")
    )
    
    # Join with dim_order_status to get status_key
    df_fact = (
        df_fact
        .join(
            df_dim_status.select("status_key", "status_code"),
            df_fact["order_status"] == df_dim_status["status_code"],
            "left"
        )
        .drop("status_code")
    )
    
    # Add audit columns
    df_fact = df_fact.withColumn("last_updated", current_timestamp())
    
    # Add row hash for CDC detection
    df_fact = df_fact.withColumn(
        "row_hash",
        md5(concat_ws("||",
                      col("order_number"),
                      col("order_status"),
                      col("amount"),
                      col("commission")))
    )
    
    # Select final columns (ONLY surrogate keys in dimensional columns)
    fact_cols = [
        # === PRIMARY KEY ===
        "order_number",  # Business PK
        
        # === FOREIGN KEYS (Surrogate Keys) ===
        "date_key",
        "asset_key",
        "fiat_key",
        "status_key",
        
        # === DEGENERATE DIMENSIONS (String attributes kept in fact) ===
        "trade_type",
        "adv_no",
        "advertisement_role",
        "counter_part_nick_name",
        
        # === MEASURES (Raw, No Aggregation) ===
        "amount",
        "unit_price",
        "total_price",
        "commission",
        "net_volume",
        
        # === AUDIT ===
        "last_updated",
        "row_hash",
        
        # === PARTITIONS ===
        "year",
        "month",
        "day",
    ]
    
    df_fact = df_fact.select(*fact_cols)
    
    # Validate PK uniqueness
    logger.info("Validating PK uniqueness (order_number)...")
    duplicate_count = (
        df_fact
        .groupBy("order_number")
        .count()
        .filter(col("count") > 1)
        .count()
    )
    
    if duplicate_count > 0:
        logger.error(f"❌ Found {duplicate_count} duplicate order_numbers!")
        raise ValueError("Duplicate PKs detected in fact table!")
    
    logger.info("✅ PK uniqueness validated. No duplicates found.")
    
    # Write fact table
    fact_path_path = Path(fact_path)
    fact_path_str = str(fact_path_path)
    
    if fact_path_path.exists() and DeltaTable.isDeltaTable(spark, fact_path_str):
        logger.info(f"Fact table exists at {fact_path_str} → MERGE by order_number")
        
        delta_table = DeltaTable.forPath(spark, fact_path_str)
        
        (
            delta_table.alias("target")
            .merge(
                df_fact.alias("source"),
                "target.order_number = source.order_number"
            )
            .whenMatchedUpdate(
                condition="target.row_hash != source.row_hash",  # Only update if changed
                set={
                    "status_key": col("source.status_key"),
                    "amount": col("source.amount"),
                    "commission": col("source.commission"),
                    "net_volume": col("source.net_volume"),
                    "last_updated": col("source.last_updated"),
                    "row_hash": col("source.row_hash"),
                }
            )
            .whenNotMatchedInsertAll()
            .execute()
        )
        logger.info("✅ MERGE completed (upsert by order_number)")
    else:
        logger.info(f"Fact table does NOT exist → Creating new Delta fact at {fact_path_str}")
        fact_path_path.mkdir(parents=True, exist_ok=True)
        
        (
            df_fact.write
            .format("delta")
            .mode("overwrite")
            .partitionBy("year", "month", "day")
            .save(fact_path_str)
        )
        logger.info(f"✅ Initial fact written (rows={df_fact.count()})")


# ========================= GCS UPLOAD ===================================
def upload_to_gcs(local_path: str, bucket: str, prefix: str) -> None:
    """
    Upload Gold Delta tables to GCS using GCSManager.
    """
    if not bucket:
        logger.warning("GCS_BUCKET not set, skipping GCS upload")
        return
    
    logger.info(f"Uploading Gold layer to GCS: gs://{bucket}/{prefix}/")
    
    try:
        gcs_manager = GCSManager()
        gcs_manager.create_bucket(bucket_name=bucket, location="asia-southeast1")
        
        local_root = Path(local_path)
        if not local_root.exists():
            logger.warning(f"Local path {local_path} does not exist, nothing to upload.")
            return
        
        workers = int(os.getenv("GCS_WORKERS", "16"))
        use_threads = os.getenv("GCS_USE_THREADS", "true").lower() == "true"
        
        uploaded_count = gcs_manager.upload_tree_parallel(
            root_folder=local_path,
            bucket_name=bucket,
            destination_prefix=prefix,
            workers=workers,
            use_threads=use_threads,
        )
        
        logger.info(f"✅ Gold layer uploaded to gs://{bucket}/{prefix}/ ({uploaded_count} files)")
        
    except Exception as e:
        logger.error(f"❌ Failed to upload to GCS: {e}")
        raise


# ========================= MAIN =========================================
def main():
    try:
        spark = get_spark(APP_NAME)
        spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
        spark.conf.set("spark.sql.shuffle.partitions", "8")
        
        logger.info(f"Reading Silver data from {SILVER_PATH}")
        df_silver = spark.read.format("delta").load(SILVER_PATH)
        
        record_count = df_silver.count()
        logger.info(f"Silver DataFrame count: {record_count}")
        
        if record_count == 0:
            logger.warning("No data found in Silver. Exiting.")
            return
        
        # Setup Gold local paths
        gold_root = Path(GOLD_LOCAL_PATH)
        gold_root.mkdir(parents=True, exist_ok=True)
        
        dim_status_path = str(gold_root / "dim_order_status")
        dim_date_path = str(gold_root / "dim_date")
        dim_asset_path = str(gold_root / "dim_asset")
        dim_fiat_path = str(gold_root / "dim_fiat")
        fact_path = str(gold_root / "fact_c2c_trades")
        
        # Build dimensions
        logger.info("Generating dimensions...")
        df_dim_status = build_dim_order_status(spark, dim_status_path)
        df_dim_date = build_dim_date(spark, df_silver, dim_date_path)
        df_dim_asset = build_dim_asset(df_silver, dim_asset_path)
        df_dim_fiat = build_dim_fiat(df_silver, dim_fiat_path)
        
        # Build fact (transaction level - NO aggregation)
        logger.info("Generating fact table (transaction level)...")
        build_fact_transaction(
            df_silver,
            df_dim_date,
            df_dim_asset,
            df_dim_fiat,
            df_dim_status,
            fact_path,
            spark
        )
        
        # Upload to GCS
        logger.info("Gold layer built locally. Starting upload to GCS...")
        upload_to_gcs(GOLD_LOCAL_PATH, GCS_BUCKET, GCS_PREFIX)
        
        logger.info("✅ Gold Job V1 completed successfully.")
        
    except Exception as e:
        logger.exception(f"❌ Gold Job V1 failed: {e}")
        sys.exit(1)
    finally:
        if "spark" in locals():
            spark.stop()
        logger.info("Spark session stopped.")


if __name__ == "__main__":
    main()

