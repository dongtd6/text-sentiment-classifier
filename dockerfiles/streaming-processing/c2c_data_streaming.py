#!/usr/bin/env python3
# c2c_data_streaming.py
"""
C2C Trading Data Streaming Job
Fetches historical trading data from Binance C2C API and inserts into PostgreSQL c2c.trades table
"""

import os
import sys
import logging
import time
import psycopg2
import requests
from datetime import datetime
from typing import List

# Add parent directory to path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from binance_sdk_c2c.c2c import ConfigurationRestAPI, C2C_REST_API_PROD_URL
from binance_sdk_c2c.rest_api.models import GetC2CTradeHistoryResponseDataInner
from data_ingestion import C2CExtended

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class C2CDataStreaming:
    """Streams C2C trading data from Binance API to PostgreSQL"""
    
    def __init__(self):
        """Initialize API client and database connection"""
        # Get API credentials from environment
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        
        if not self.api_key or not self.api_secret:
            raise ValueError("BINANCE_API_KEY and BINANCE_API_SECRET must be set")
        
        # Get database credentials from environment
        # Defaults point to the orchestration Postgres service (Airflow's Postgres)
        self.db_host = os.getenv("DB_HOST", "airflow-postgresql.orchestration.svc.cluster.local")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_name = os.getenv("DB_NAME", "c2c_trade")
        self.db_user = os.getenv("DB_USER", "postgres")
        self.db_password = os.getenv("DB_PASSWORD")
        
        if not self.db_password:
            raise ValueError("DB_PASSWORD must be set")
        
        # Initialize API client
        config = ConfigurationRestAPI(
            api_key=self.api_key,
            api_secret=self.api_secret,
            base_path=C2C_REST_API_PROD_URL
        )
        self.client = C2CExtended(config)
        
        # Database connection
        self.conn = None
        self.cursor = None
        
    def connect_db(self):
        """Establish connection to PostgreSQL"""
        try:
            logger.info(f"Connecting to PostgreSQL at {self.db_host}:{self.db_port}/{self.db_name}")
            self.conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
            self.cursor = self.conn.cursor()
            logger.info("✅ Connected to PostgreSQL successfully")
        except psycopg2.Error as e:
            logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
            raise
    
    def close_db(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Database connection closed")
    
    def ensure_schema_exists(self):
        """Ensure c2c schema and trades table exist"""
        try:
            # Create schema if not exists
            self.cursor.execute("CREATE SCHEMA IF NOT EXISTS c2c;")
            
            # Create table if not exists
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS c2c.trades (
                    order_number TEXT PRIMARY KEY,
                    adv_no TEXT,
                    trade_type TEXT CHECK (trade_type IN ('BUY','SELL')),
                    asset VARCHAR(16),
                    fiat VARCHAR(16),
                    fiat_symbol VARCHAR(16),
                    amount NUMERIC(38, 8) CHECK (amount >= 0),
                    total_price NUMERIC(38, 8) CHECK (total_price >= 0),
                    unit_price NUMERIC(38, 8) CHECK (unit_price >= 0),
                    order_status TEXT,
                    create_time_ms BIGINT,
                    commission NUMERIC(38, 8) CHECK (commission >= 0),
                    counter_part_nick_name TEXT,
                    advertisement_role TEXT
                );
            """)
            
            self.conn.commit()
            logger.info("✅ Schema and table verified/created successfully")
        except psycopg2.Error as e:
            self.conn.rollback()
            logger.error(f"❌ Failed to create schema/table: {e}")
            raise
    
    def fetch_trading_data(self, mode: str = "latest_month") -> List[GetC2CTradeHistoryResponseDataInner]:
        """
        Fetch trading data from Binance API
        
        Args:
            mode: One of 'latest', 'latest_week', 'latest_month', 'yesterday', 
                  'prev_week', 'prev_month', or 'custom' (requires START_DATE and END_DATE env vars)
        
        Returns:
            List of trade records
        """
        logger.info(f"Fetching trading data using mode: {mode}")
        
        try:
            if mode == "latest":
                data = self.client.get_latest()
            elif mode == "latest_week":
                data = self.client.get_latest_by_week()
            elif mode == "latest_month":
                data = self.client.get_latest_by_month()
            elif mode == "yesterday":
                data = self.client.get_yesterday()
            elif mode == "prev_week":
                data = self.client.get_prev_week_data()
            elif mode == "prev_month":
                data = self.client.get_prev_month()
            elif mode == "custom":
                start_date = os.getenv("START_DATE")
                end_date = os.getenv("END_DATE")
                if not start_date or not end_date:
                    raise ValueError("START_DATE and END_DATE must be set for custom mode")
                data = self.client.get_custom_range(start_date, end_date)
            else:
                raise ValueError(f"Unknown mode: {mode}")
            
            logger.info(f"✅ Fetched {len(data)} trade records from API")
            return data
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch data from API: {e}")
            raise
    
    def insert_trade(self, trade: GetC2CTradeHistoryResponseDataInner) -> bool:
        """
        Insert a single trade record into database
        
        Args:
            trade: Trade record from API
            
        Returns:
            True if inserted, False if skipped (duplicate)
        """
        insert_query = """
            INSERT INTO c2c.trades (
                order_number, adv_no, trade_type, asset, fiat, fiat_symbol,
                amount, total_price, unit_price, order_status, create_time,
                commission, counter_part_nick_name, advertisement_role
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (order_number) DO NOTHING;
        """
        
        try:
            raw_ct = getattr(trade, "create_time_ms", None) \
                or getattr(trade, "create_time", None) \
                or getattr(trade, "timestamp", None)
            values = (
                trade.order_number,
                trade.adv_no,
                trade.trade_type,
                trade.asset,
                trade.fiat,
                trade.fiat_symbol,
                float(trade.amount) if trade.amount else 0,
                float(trade.total_price) if trade.total_price else 0,
                float(trade.unit_price) if trade.unit_price else 0,
                trade.order_status,
                int(raw_ct) if raw_ct else None,
                float(trade.commission) if trade.commission else 0,
                trade.counter_part_nick_name,
                trade.advertisement_role
            )
            
            self.cursor.execute(insert_query, values)
            return self.cursor.rowcount > 0
            
        except psycopg2.Error as e:
            logger.error(f"Error inserting trade {trade.order_number}: {e}")
            return False
    
    def insert_trades_batch(self, trades: List[GetC2CTradeHistoryResponseDataInner]):
        """
        Insert multiple trade records into database
        
        Args:
            trades: List of trade records
        """
        logger.info(f"Inserting {len(trades)} trades into database...")
        
        inserted_count = 0
        skipped_count = 0
        error_count = 0
        
        try:
            for i, trade in enumerate(trades, 1):
                try:
                    if self.insert_trade(trade):
                        inserted_count += 1
                    else:
                        skipped_count += 1
                    
                    # Sleep 10 seconds after each insert
                    time.sleep(10)
                    
                    # Log progress every 100 records
                    if i % 100 == 0:
                        logger.info(f"Progress: {i}/{len(trades)} processed")
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing trade #{i}: {e}")
                    continue
            
            # Commit all changes
            self.conn.commit()
            
            logger.info(f"""
            ✅ Batch insert completed:
               - Inserted: {inserted_count} new records
               - Skipped: {skipped_count} duplicates
               - Errors: {error_count}
               - Total processed: {len(trades)}
            """)
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ Batch insert failed: {e}")
            raise
    
    def get_table_stats(self):
        """Get statistics about the c2c.trades table"""
        try:
            # Total count
            self.cursor.execute("SELECT COUNT(*) FROM c2c.trades;")
            total_count = self.cursor.fetchone()[0]
            
            # Count by trade type
            self.cursor.execute("""
                SELECT trade_type, COUNT(*) as count, SUM(total_price) as total_volume
                FROM c2c.trades 
                GROUP BY trade_type;
            """)
            trade_type_stats = self.cursor.fetchall()
            
            # Count by asset
            self.cursor.execute("""
                SELECT asset, COUNT(*) as count, SUM(amount) as total_amount
                FROM c2c.trades 
                GROUP BY asset
                ORDER BY count DESC
                LIMIT 5;
            """)
            asset_stats = self.cursor.fetchall()
            
            logger.info(f"""
            📊 Database Statistics:
            
            Total Records: {total_count}
            
            By Trade Type:
            {chr(10).join([f"  - {row[0]}: {row[1]} trades, Total: {row[2]:,.2f}" for row in trade_type_stats])}
            
            Top Assets:
            {chr(10).join([f"  - {row[0]}: {row[1]} trades, Total: {row[2]:,.8f}" for row in asset_stats])}
            """)
            
        except psycopg2.Error as e:
            logger.error(f"Failed to get table stats: {e}")
    
    def send_telegram_notification(self, inserted_count: int, total_count: int):
        """Send Telegram notification after data insertion"""
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not bot_token or not chat_id:
            logger.warning("⚠️  Telegram credentials not set, skipping notification")
            return False
        
        try:
            message = (
                f"🎉 *C2C Data Ingestion Complete!*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ New records inserted: {inserted_count}\n"
                f"📊 Total records in DB: {total_count}\n"
                f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Pipeline executed successfully! 🚀"
            )
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            logger.info("📤 Sending Telegram notification...")
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("✅ Telegram notification sent successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram notification: {e}")
            return False
    
    def run(self):
        """Main execution method"""
        start_time = datetime.now()
        logger.info("=" * 70)
        logger.info("🚀 Starting C2C Data Streaming Job")
        logger.info("=" * 70)
        
        try:
            # Connect to database
            self.connect_db()
            
            # Ensure schema exists
            self.ensure_schema_exists()
            
            # Get fetch mode from environment (default: latest_month)
            fetch_mode = os.getenv("FETCH_MODE", "latest_month")
            
            # Fetch data from API
            trades = self.fetch_trading_data(fetch_mode)
            
            if not trades:
                logger.warning("⚠️  No trades fetched from API")
                return
            
            # Insert data into database
            self.insert_trades_batch(trades)
            
            # Show statistics
            self.get_table_stats()
            
            # Get counts for Telegram notification
            self.cursor.execute("SELECT COUNT(*) FROM c2c.trades;")
            total_count = self.cursor.fetchone()[0]
            inserted_count = len(trades)
            
            # Send Telegram notification
            self.send_telegram_notification(inserted_count, total_count)
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            logger.info("=" * 70)
            logger.info(f"✅ Job completed successfully in {duration:.2f} seconds")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"❌ Job failed: {e}")
            raise
        finally:
            self.close_db()


if __name__ == "__main__":
    """Entry point for the streaming job"""
    try:
        job = C2CDataStreaming()
        job.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

