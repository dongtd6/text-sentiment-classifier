import os
import sys
import logging
from datetime import datetime, timedelta

# Add /app to python path
sys.path.append("/app")

# Spark imports
from pyspark.sql import DataFrame
from pyspark.sql.types import *
from pyspark.sql.functions import col, year, month, dayofmonth, from_unixtime, from_utc_timestamp, to_date

# Common imports
from common.utils import get_spark
from common.io import write_delta

# API imports
from binance_sdk_c2c.c2c import ConfigurationRestAPI, C2C_REST_API_PROD_URL
from data_ingestion import C2CExtended

# --------------------- LOGGING & CONFIG ---------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingest_to_bronze")

# Configs
BRONZE_TABLE_NAME = "c2c_trades_bronze"
BRONZE_PATH = os.getenv("BRONZE_PATH", "s3a://tsc-bucket/bronze/c2c_trades/")
APP_NAME = "C2CIngestToBronze"

def get_c2c_data_yesterday():
    """Fetch yesterday's data from Binance API"""
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    
    if not api_key or not api_secret:
        raise ValueError("BINANCE_API_KEY/BINANCE_API_SECRET are missing")

    config = ConfigurationRestAPI(
        api_key=api_key,
        api_secret=api_secret,
        base_path=C2C_REST_API_PROD_URL
    )
    
    client = C2CExtended(config)
    logger.info("Fetching trade history for yesterday...")
    # Using get_latest() based on your previous ingestion.py, 
    # but normally for 'yesterday' specifically we'd use get_yesterday()
    # Let's stick to get_latest() if that's what you tested, or switch to get_yesterday() if desired.
    # Given the previous ingestion.py used get_latest(), I will use that, BUT typically 'daily' jobs want yesterday's closed data.
    # I will use get_latest() to match your last known good ingestion.py logic, but please verify if you want get_yesterday()
    data = client.get_latest() 
    logger.info(f"Successfully retrieved {len(data)} records from API.")
    return data

def process_and_write(spark, data_list):
    """Convert list of objects to Spark DF, process, and write to MinIO"""
    if not data_list:
        logger.warning("No data to process.")
        return

    # 1. Convert API objects (pydantic/custom class) to Dicts
    rows = []
    for item in data_list:
        rows.append({
            'order_number': item.order_number,
            'adv_no': item.adv_no,
            'trade_type': item.trade_type,
            'asset': item.asset,
            'fiat': item.fiat,
            'fiat_symbol': item.fiat_symbol,
            'amount': str(item.amount), # Spark might prefer string for decimals/float to avoid precision loss or just float
            'total_price': str(item.total_price),
            'unit_price': str(item.unit_price),
            'order_status': item.order_status,
            'create_time': getattr(item, 'create_time', None), # Ensure attribute exists
            'commission': str(item.commission),
            'counter_part_nick_name': item.counter_part_nick_name,
            'advertisement_role': item.advertisement_role
        })

    # 2. Create Spark DataFrame
    df = spark.createDataFrame(rows)

    # 3. Process (Add partitions)
    logger.info("Processing DataFrame...")
    
    # Cast timestamp
    if "create_time" in df.columns:
        df = df.withColumn("create_time", col("create_time").cast(LongType()))
        
        # Add partitions
        df = df.withColumn(
            "create_ts_utc", from_unixtime(col("create_time") / 1000)
        ).withColumn(
            "create_ts", from_utc_timestamp("create_ts_utc", "Asia/Ho_Chi_Minh")
        ).withColumn(
            "trade_date", to_date("create_ts")
        ).withColumn("year", year("trade_date")) \
         .withColumn("month", month("trade_date")) \
         .withColumn("day", dayofmonth("trade_date")) \
         .drop("create_ts_utc", "create_ts")
         
    # Deduplicate
    if "order_number" in df.columns:
        df = df.dropDuplicates(["order_number"])

    # 4. Write to Delta
    logger.info(f"Writing to Bronze Delta → {BRONZE_PATH}")
    
    # Using the write logic directly here for clarity, or could use common.io.write_delta
    (
        df.write.format("delta")
        .mode("append")
        .option("path", BRONZE_PATH)
        .partitionBy("year", "month", "day")
        .saveAsTable(BRONZE_TABLE_NAME)
    )
    logger.info("✅ Write success!")

def main():
    try:
        # 1. Fetch Data (No Spark needed yet)
        data = get_c2c_data_yesterday()
        
        if not data:
            logger.info("No data found, exiting.")
            return

        # 2. Init Spark only if we have data
        spark = get_spark(APP_NAME)
        spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
        
        # 3. Process
        process_and_write(spark, data)
        
    except Exception as e:
        logger.exception(f"Job failed: {e}")
        sys.exit(1)
    finally:
        if "spark" in locals():
            spark.stop()

if __name__ == "__main__":
    main()

