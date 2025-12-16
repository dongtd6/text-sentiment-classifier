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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ingestion_to_bronze")

# Configs
BRONZE_TABLE_NAME = "c2c_trades_bronze"
BRONZE_PATH = os.getenv("BRONZE_PATH", "s3a://bronze/c2c_trades/")
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
    # Using get_latest_by_month() based on manual change requirement
    data = client.get_latest_by_month()
    logger.info(f"Successfully retrieved {len(data)} records from API.")
    return data

def process_and_write(spark, data_list):
    """Convert list of objects to Spark DF, process, and write to MinIO"""
    if not data_list:
        logger.warning("No data to process.")
        return

    # 1. Convert API objects to Dicts
    rows = []
    for item in data_list:
        rows.append({
            'order_number': item.order_number,
            'adv_no': item.adv_no,
            'trade_type': item.trade_type,
            'asset': item.asset,
            'fiat': item.fiat,
            'fiat_symbol': item.fiat_symbol,
            'amount': str(item.amount),
            'total_price': str(item.total_price),
            'unit_price': str(item.unit_price),
            'order_status': item.order_status,
            'create_time': getattr(item, 'create_time', None),
            'commission': str(item.commission),
            'counter_part_nick_name': item.counter_part_nick_name,
            'advertisement_role': item.advertisement_role
        })

    # Define Explicit Schema to avoid [CANNOT_DETERMINE_TYPE] error
    schema = StructType([
        StructField("order_number", StringType(), True),
        StructField("adv_no", StringType(), True),
        StructField("trade_type", StringType(), True),
        StructField("asset", StringType(), True),
        StructField("fiat", StringType(), True),
        StructField("fiat_symbol", StringType(), True),
        StructField("amount", StringType(), True),
        StructField("total_price", StringType(), True),
        StructField("unit_price", StringType(), True),
        StructField("order_status", StringType(), True),
        StructField("create_time", LongType(), True), # Typically milliseconds
        StructField("commission", StringType(), True),
        StructField("counter_part_nick_name", StringType(), True),
        StructField("advertisement_role", StringType(), True)
    ])

    # 2. Create Spark DataFrame with explicit schema
    df = spark.createDataFrame(rows, schema=schema)

    # 3. Process (Add partitions)
    logger.info("Processing DataFrame...")
    
    if "create_time" in df.columns:
        # Cast to Long just in case, though schema says Long
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
    
    (
        df.write.format("delta")
        .mode("append")
        .partitionBy("year", "month", "day")
        .save(BRONZE_PATH)
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
