import os
import sys
import logging
from decimal import Decimal
from typing import Optional
from datetime import datetime, timedelta

sys.path.append("/app")

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, lit, lower, upper, when, coalesce,
    from_unixtime, to_date, year, month, dayofmonth,
    array, map_from_arrays, current_date, from_utc_timestamp
)
from pyspark.sql.types import DecimalType
from delta.tables import DeltaTable

from common.utils import get_spark

# ========================= CONFIG & LOGGING ============================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("silver_job")

BRONZE_PATH = os.getenv("BRONZE_PATH", "s3a://bronze/c2c_trades/")
SILVER_PATH = os.getenv("SILVER_PATH", "s3a://silver/c2c_trades/")
APP_NAME = "C2CSilverJob"

# Date filter: process yesterday's data by default (can be overridden by env var)
DATE_FILTER = os.getenv("DATE_FILTER", None)

logger.info(f"BRONZE_PATH={BRONZE_PATH}")
logger.info(f"SILVER_PATH={SILVER_PATH}")
logger.info(f"DATE_FILTER={DATE_FILTER}")

# ========================= STATUS PRIORITY MAP =========================
PRIORITY_MAP = {
    "COMPLETED": 8,
    "IN_APPEAL": 7,
    "DISTRIBUTING": 6,
    "BUYER_PAYED": 5,
    "TRADING": 4,
    "PENDING": 3,
    "CANCELLED": 2,
    "CANCELLED_BY_SYSTEM": 1,
    "UNKNOWN": 0
}

def build_priority_expr():
    """Return Spark expression map(order_status -> priority)."""
    return map_from_arrays(
        array([lit(k) for k in PRIORITY_MAP.keys()]),
        array([lit(v).cast("int") for v in PRIORITY_MAP.values()])
    )

# ========================= TRANSFORMATION ===============================
def extract_timestamp(df: DataFrame) -> DataFrame:
    """Standardize timestamp column -> trade_date, trade_time."""
    ts_col = None
    for c in ("create_time", "createTime", "create_time_ms"):
        if c in df.columns:
            ts_col = c
            break
    
    if ts_col is None:
        logger.warning("No timestamp column found → using current_date")
        return (df
                .withColumn("trade_time", lit(None))
                .withColumn("trade_date", current_date()))
    
    # Convert ms → timestamp in Asia/Ho_Chi_Minh timezone
    df = df.withColumn(
        "trade_time_utc",
        from_unixtime(col(ts_col) / 1000)
    ).withColumn(
        "trade_time",
        from_utc_timestamp("trade_time_utc", "Asia/Ho_Chi_Minh")
    ).drop("trade_time_utc")
    
    df = df.withColumn("trade_date", to_date(col("trade_time")))
    return df.drop(ts_col)

def cast_numeric(df: DataFrame, col_name: str, precision=18, scale=8) -> DataFrame:
    """Safe cast, fallback to 0."""
    if col_name in df.columns:
        return df.withColumn(col_name, col(col_name).cast(DecimalType(precision, scale)))
    return df.withColumn(col_name, lit(Decimal("0")))

def transform_silver(df: DataFrame) -> DataFrame:
    """Main transformation logic for Silver layer."""
    df = extract_timestamp(df)
    
    # ----- Standardize price columns -----
    price_map = {
        "totalPrice": "total_price",
        "total_price": "total_price",
        "unitPrice": "unit_price",
        "unit_price": "unit_price",
    }
    
    for src, dst in price_map.items():
        if src in df.columns:
            df = df.withColumn(dst, col(src))
    
    df = cast_numeric(df, "total_price", 18, 2)
    df = cast_numeric(df, "unit_price", 18, 2)
    df = cast_numeric(df, "amount", 18, 8)
    df = cast_numeric(df, "commission", 18, 8)
    
    # Standardize asset and fiat to lowercase
    if "asset" in df.columns:
        df = df.withColumn("asset", lower(col("asset")))
    if "fiat" in df.columns:
        df = df.withColumn("fiat", lower(col("fiat")))
    
    # ----- Compute net_volume -----
    if "tradeType" in df.columns:
        df = df.withColumn("trade_type", upper(col("tradeType")))
        df = df.drop("tradeType")
    elif "trade_type" in df.columns:
        df = df.withColumn("trade_type", upper(col("trade_type")))
    
    df = df.withColumn(
        "net_volume",
        when(col("trade_type") == "BUY", col("amount") - col("commission"))
        .when(col("trade_type") == "SELL", -(col("amount") + col("commission")))
        .otherwise(lit(Decimal("0")))
    )
    
    df = df.withColumn("total_vnd", col("total_price"))
    
    # ----- Add partition columns (skip if already exist from Bronze) -----
    if "year" not in df.columns:
        df = df.withColumn("year", year(col("trade_date")))
    if "month" not in df.columns:
        df = df.withColumn("month", month(col("trade_date")))
    if "day" not in df.columns:
        df = df.withColumn("day", dayofmonth(col("trade_date")))
    
    # ----- Add status priority column -----
    priority_expr = build_priority_expr()
    df = df.withColumn(
        "status_priority",
        coalesce(priority_expr[col("order_status")], lit(0))
    )
    
    return df

# ========================= MERGE LOGIC ==================================
def merge_into_silver(spark: SparkSession, df: DataFrame) -> None:
    """Perform incremental MERGE into Silver Delta table."""
    if not DeltaTable.isDeltaTable(spark, SILVER_PATH):
        logger.info("Silver table not found → bootstrapping new table")
        (
            df.coalesce(4)
              .write.format("delta")
              .mode("overwrite")
              .partitionBy("year", "month", "day")
              .save(SILVER_PATH)
        )
        logger.info("✅ Bootstrap completed.")
        return
    
    logger.info("Silver table exists → incremental MERGE")
    delta = DeltaTable.forPath(spark, SILVER_PATH)
    
    # Merge condition
    merge_cond = "target.order_number = source.order_number"
    
    # Only update if incoming row has higher priority
    update_cond = "source.status_priority > target.status_priority"
    
    cols = [
        "order_number", "adv_no", "trade_type", "asset", "fiat", "amount",
        "total_price", "unit_price", "order_status", "trade_time", "trade_date",
        "commission", "total_vnd", "net_volume", "year", "month", "day",
        "status_priority"
    ]
    
    # Filter to only include columns that exist in the DataFrame
    existing_cols = [c for c in cols if c in df.columns]
    
    set_map = {c: col(f"source.{c}") for c in existing_cols}
    insert_map = {c: col(f"source.{c}") for c in existing_cols}
    
    (
        delta.alias("target")
             .merge(df.alias("source"), merge_cond)
             .whenMatchedUpdate(condition=update_cond, set=set_map)
             .whenNotMatchedInsert(values=insert_map)
             .execute()
    )
    
    logger.info("✅ MERGE completed.")

# ========================= MAIN ==========================================
def main():
    try:
        spark = get_spark(APP_NAME)
        spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
        
        logger.info(f"Reading Bronze data from {BRONZE_PATH}")
        
        # Determine processing mode based on DATE_FILTER env var
        if DATE_FILTER:
            if DATE_FILTER.lower() == "yesterday":
                # Incremental mode: process yesterday's data only
                target_date = datetime.now() - timedelta(days=1)
                target_year = target_date.year
                target_month = target_date.month
                target_day = target_date.day
                
                logger.info(f"📅 INCREMENTAL MODE: Processing yesterday's data ({target_date.date()})")
                df = (spark.read.format("delta")
                      .load(BRONZE_PATH)
                      .filter((col("year") == target_year) & 
                              (col("month") == target_month) & 
                              (col("day") == target_day)))
            else:
                # Process specific date (format: YYYY-MM-DD)
                target_date = datetime.strptime(DATE_FILTER, "%Y-%m-%d")
                target_year = target_date.year
                target_month = target_date.month
                target_day = target_date.day
                
                logger.info(f"📅 SPECIFIC DATE MODE: Processing data for {target_date.date()}")
                df = (spark.read.format("delta")
                      .load(BRONZE_PATH)
                      .filter((col("year") == target_year) & 
                              (col("month") == target_month) & 
                              (col("day") == target_day)))
        else:
            # Full mode: process ALL Bronze data (for initial run / backfill)
            logger.info(f"🔄 FULL MODE: Processing ALL Bronze data (initial run / backfill)")
            df = spark.read.format("delta").load(BRONZE_PATH)
        
        record_count = df.count()
        logger.info(f"Bronze DataFrame count: {record_count}")
        
        if record_count == 0:
            logger.warning(f"No data found in Bronze. Exiting.")
            return
        
        df.printSchema()
        
        # Transform
        logger.info("Transforming to Silver...")
        df_silver = transform_silver(df)
        
        # Merge
        logger.info("Merging into Silver...")
        merge_into_silver(spark, df_silver)
        
        logger.info("✅ Silver job completed successfully.")
        
    except Exception as e:
        logger.exception(f"❌ Silver job failed: {e}")
        sys.exit(1)
    finally:
        if "spark" in locals():
            spark.stop()
        logger.info("Spark session stopped.")

if __name__ == "__main__":
    main()

