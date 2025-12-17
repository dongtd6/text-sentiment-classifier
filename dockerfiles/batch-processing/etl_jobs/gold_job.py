import os
import sys
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

sys.path.append("/app")

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.types import IntegerType
from pyspark.sql.functions import (
    col, when, lit, sum as spark_sum, avg, count, coalesce,
    year, month, dayofmonth, dayofweek, lower, current_timestamp,
    max as spark_max, date_sub, row_number
)
from pyspark.sql.window import Window
from delta.tables import DeltaTable

from common.utils import get_spark
from common.gcs_manager import GCSManager

# ========================= CONFIG & LOGGING ============================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("gold_job")

SILVER_PATH = os.getenv("SILVER_PATH", "s3a://silver/c2c_trades/")
GOLD_LOCAL_PATH = os.getenv("GOLD_LOCAL_PATH", "/tmp/gold_delta")
GCS_BUCKET = os.getenv("GCS_BUCKET", "")
GCS_PREFIX = os.getenv("GCS_PREFIX", "gold_backup")
APP_NAME = "C2CGoldJob"

# Date filter: None = process all, "yesterday" = process yesterday, or specific date
DATE_FILTER = os.getenv("DATE_FILTER", None)

logger.info(f"SILVER_PATH={SILVER_PATH}")
logger.info(f"GOLD_LOCAL_PATH={GOLD_LOCAL_PATH}")
logger.info(f"GCS_BUCKET={GCS_BUCKET}")
logger.info(f"GCS_PREFIX={GCS_PREFIX}")
logger.info(f"DATE_FILTER={DATE_FILTER}")

# ========================= DIMENSION BUILDERS ==========================
def build_dim_date(spark: SparkSession, df_silver: DataFrame, dim_date_path: str) -> DataFrame:
    """
    Build date dimension from Silver trade_date range.
    """
    logger.info("Building dim_date...")
    
    agg = df_silver.agg(
        spark_max("trade_date").alias("max_date"),
        spark_sum(when(col("trade_date").isNotNull(), lit(1)).otherwise(lit(0))).alias("non_null_count")
    ).collect()[0]
    
    max_date = agg["max_date"]
    if not max_date or agg["non_null_count"] == 0:
        logger.warning("No valid trade_date found in Silver for dim_date. Skipping.")
        return spark.createDataFrame(
            [], 
            "date_key INT, full_date DATE, day_of_week INT, month INT, quarter INT, year INT, is_weekend BOOLEAN, fiscal_year INT"
        )
    
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
        .withColumn("month", month("full_date"))
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


def build_dim_asset(df_silver: DataFrame, dim_asset_path: str) -> DataFrame:
    """
    Build asset dimension from Silver.
    """
    logger.info("Building dim_asset...")
    
    w = Window.orderBy("asset_code")
    
    df_dim_asset = (
        df_silver
        .select(lower(col("asset")).alias("asset_code"))
        .where(col("asset").isNotNull())
        .distinct()
        .withColumn("asset_key", (row_number().over(w)).cast(IntegerType()))
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


def build_dim_fiat(df_silver: DataFrame, dim_fiat_path: str) -> DataFrame:
    """
    Build fiat dimension from Silver.
    """
    logger.info("Building dim_fiat...")
    
    w = Window.orderBy("fiat_code")
    
    df_dim_fiat = (
        df_silver
        .select(lower(col("fiat")).alias("fiat_code"))
        .where(col("fiat").isNotNull())
        .distinct()
        .withColumn("fiat_key", (row_number().over(w)).cast(IntegerType()))
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


# ========================= FACT BUILDER ================================
def build_fact(df_silver: DataFrame,
               df_dim_asset: DataFrame,
               df_dim_fiat: DataFrame,
               fact_path: str,
               spark: SparkSession) -> None:
    """
    Build fact table from Silver data with aggregations.
    """
    logger.info("Building fact_c2c_trades_daily...")
    
    # Filter completed orders for main metrics
    df_completed = df_silver.filter(col("order_status") == "COMPLETED")
    
    # Aggregations by date, asset, fiat
    df_fact_agg = (
        df_completed.groupBy("trade_date", "asset", "fiat")
        .agg(
            spark_sum(when(col("trade_type") == "BUY", col("amount")).otherwise(0)).alias("buy_volume"),
            spark_sum(when(col("trade_type") == "SELL", col("amount")).otherwise(0)).alias("sell_volume"),
            spark_sum(when(col("trade_type") == "BUY", col("total_vnd")).otherwise(0)).alias("buy_total_vnd"),
            spark_sum(when(col("trade_type") == "SELL", col("total_vnd")).otherwise(0)).alias("sell_total_vnd"),
            spark_sum(col("net_volume")).alias("daily_net_volume"),
            spark_sum(col("commission")).alias("total_commission"),
            avg(col("commission")).alias("avg_commission"),
            # Weighted avg prices
            (
                spark_sum(when(col("trade_type") == "BUY", col("unit_price") * col("amount")).otherwise(0)) /
                coalesce(spark_sum(when(col("trade_type") == "BUY", col("amount")).otherwise(0)), lit(1))
            ).alias("avg_unit_buy_price"),
            (
                spark_sum(when(col("trade_type") == "SELL", col("unit_price") * col("amount")).otherwise(0)) /
                coalesce(spark_sum(when(col("trade_type") == "SELL", col("amount")).otherwise(0)), lit(1))
            ).alias("avg_unit_sell_price"),
            count("*").alias("completed_orders"),
        )
        .withColumn("price_spread", col("avg_unit_sell_price") - col("avg_unit_buy_price"))
    )
    
    # All orders metrics
    df_full = (
        df_silver.groupBy("trade_date", "asset", "fiat")
        .agg(
            count("*").alias("total_orders"),
            count(when(col("order_status") == "CANCELLED", lit(1)).otherwise(None)).alias("canceled_orders"),
        )
    )
    
    # Combine metrics
    df_fact = (
        df_fact_agg
        .join(df_full, ["trade_date", "asset", "fiat"], "left")
        .withColumn("completed_rate",
                    (col("completed_orders") / coalesce(col("total_orders"), lit(1))) * 100)
        .withColumn("cancel_rate",
                    (col("canceled_orders") / coalesce(col("total_orders"), lit(1))) * 100)
        .withColumn("daily_net_vnd",
                    col("sell_total_vnd") - col("buy_total_vnd"))
    )
    
    # Add date key and partitions
    df_fact = (
        df_fact
        .withColumn(
            "date_key",
            (year("trade_date") * 10000 + month("trade_date") * 100 + dayofmonth("trade_date")).cast(IntegerType())
        )
        .withColumn("year", year(col("trade_date")))
        .withColumn("month", month(col("trade_date")))
        .withColumn("day", dayofmonth(col("trade_date")))
    )
    
    # Join with dimensions for keys
    df_fact = (
        df_fact
        .join(
            df_dim_asset.select("asset_key", "asset_code"),
            lower(df_fact["asset"]) == df_dim_asset["asset_code"],
            "left"
        )
        .join(
            df_dim_fiat.select("fiat_key", "fiat_code"),
            lower(df_fact["fiat"]) == df_dim_fiat["fiat_code"],
            "left"
        )
        .drop("asset_code", "fiat_code")
        .withColumn("last_updated", current_timestamp())
    )
    
    # Select final columns
    fact_cols = [
        "date_key", "asset_key", "fiat_key",
        "trade_date", "asset", "fiat",
        "buy_volume", "sell_volume",
        "buy_total_vnd", "sell_total_vnd",
        "daily_net_volume", "daily_net_vnd",
        "total_commission", "avg_commission",
        "avg_unit_buy_price", "avg_unit_sell_price",
        "price_spread",
        "completed_orders", "total_orders", "canceled_orders",
        "completed_rate", "cancel_rate",
        "year", "month", "day",
        "last_updated",
    ]
    df_fact = df_fact.select(*fact_cols)
    
    # Write fact table (overwrite for initial load, can be changed to incremental later)
    fact_path_path = Path(fact_path)
    fact_path_str = str(fact_path_path)
    
    if fact_path_path.exists() and DeltaTable.isDeltaTable(spark, fact_path_str):
        logger.info(f"Fact table exists at {fact_path_str} → Overwriting")
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
    
    logger.info(f"✅ Fact written to {fact_path_str} (rows={df_fact.count()})")


# ========================= GCS UPLOAD ==================================
def upload_to_gcs(local_path: str, bucket: str, prefix: str) -> None:
    """
    Upload Gold Delta tables to GCS using GCSManager.
    """
    if not bucket:
        logger.warning("GCS_BUCKET not set, skipping GCS upload")
        return
    
    logger.info(f"Uploading Gold layer to GCS: gs://{bucket}/{prefix}/")
    
    try:
        # Initialize GCS Manager (will use GOOGLE_APPLICATION_CREDENTIALS env var)
        gcs_manager = GCSManager()
        
        # Ensure bucket exists
        gcs_manager.create_bucket(bucket_name=bucket, location="asia-southeast1")
        
        # Check if local path exists
        local_root = Path(local_path)
        if not local_root.exists():
            logger.warning(f"Local path {local_path} does not exist, nothing to upload.")
            return
        
        # Upload entire folder (you can use upload_tree_parallel for faster upload)
        workers = int(os.getenv("GCS_WORKERS", "16"))
        use_threads = os.getenv("GCS_USE_THREADS", "false").lower() == "true"
        
        uploaded_count = gcs_manager.upload_tree_parallel(
            root_folder=local_path,
            bucket_name=bucket,
            destination_prefix=prefix,
            workers=workers,
            use_threads=use_threads
        )
        
        logger.info(f"✅ Gold layer uploaded to gs://{bucket}/{prefix}/ ({uploaded_count} files)")
        
    except Exception as e:
        logger.error(f"❌ Failed to upload to GCS: {e}")
        raise


# ========================= MAIN =======================================
def main():
    try:
        spark = get_spark(APP_NAME)
        spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
        spark.conf.set("spark.sql.shuffle.partitions", "8")
        
        logger.info(f"Reading Silver data from {SILVER_PATH}")
        
        # Determine processing mode
        if DATE_FILTER:
            if DATE_FILTER.lower() == "yesterday":
                target_date = datetime.now() - timedelta(days=1)
                logger.info(f"📅 INCREMENTAL MODE: Processing yesterday's data ({target_date.date()})")
            else:
                target_date = datetime.strptime(DATE_FILTER, "%Y-%m-%d")
                logger.info(f"📅 SPECIFIC DATE MODE: Processing data for {target_date.date()}")
            
            # Filter Silver by date (not implemented yet for simplicity)
            # df_silver = spark.read.format("delta").load(SILVER_PATH).filter(...)
            logger.warning("Date filtering not fully implemented yet, processing ALL Silver data")
            df_silver = spark.read.format("delta").load(SILVER_PATH)
        else:
            # Full mode: process ALL Silver data
            logger.info(f"🔄 FULL MODE: Processing ALL Silver data")
            df_silver = spark.read.format("delta").load(SILVER_PATH)
        
        record_count = df_silver.count()
        logger.info(f"Silver DataFrame count: {record_count}")
        
        if record_count == 0:
            logger.warning("No data found in Silver. Exiting.")
            return
        
        # Setup Gold local paths
        gold_root = Path(GOLD_LOCAL_PATH)
        gold_root.mkdir(parents=True, exist_ok=True)
        
        dim_date_path = str(gold_root / "dim_date")
        dim_asset_path = str(gold_root / "dim_asset")
        dim_fiat_path = str(gold_root / "dim_fiat")
        fact_path = str(gold_root / "fact_c2c_trades_daily")
        
        # Build dimensions
        logger.info("Generating dimensions...")
        df_dim_date = build_dim_date(spark, df_silver, dim_date_path)
        df_dim_asset = build_dim_asset(df_silver, dim_asset_path)
        df_dim_fiat = build_dim_fiat(df_silver, dim_fiat_path)
        
        # Build fact
        logger.info("Generating fact table...")
        build_fact(df_silver, df_dim_asset, df_dim_fiat, fact_path, spark)
        
        # Upload to GCS
        logger.info("Gold layer built locally. Starting upload to GCS...")
        upload_to_gcs(GOLD_LOCAL_PATH, GCS_BUCKET, GCS_PREFIX)
        
        logger.info("✅ Gold job completed successfully.")
        
    except Exception as e:
        logger.exception(f"❌ Gold job failed: {e}")
        sys.exit(1)
    finally:
        if "spark" in locals():
            spark.stop()
        logger.info("Spark session stopped.")


if __name__ == "__main__":
    main()

