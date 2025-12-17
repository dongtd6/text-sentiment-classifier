#!/usr/bin/env python3
"""
Flink Job: C2C Trading Telegram Notifier
Consumes CDC events from c2c.trades table and sends Telegram notifications for new trades
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaOffsetsInitializer,
    KafkaSource,
)
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_timestamp(timestamp_ms):
    """Format timestamp from milliseconds to readable format"""
    if not timestamp_ms or timestamp_ms == "N/A":
        return "N/A"
    try:
        if isinstance(timestamp_ms, (int, float)):
            dt = datetime.fromtimestamp(int(timestamp_ms) / 1000)
            return dt.strftime("%d/%m/%Y %H:%M:%S")
        return str(timestamp_ms)
    except (ValueError, TypeError, OverflowError) as e:
        logger.error(f"Error parsing timestamp {timestamp_ms}: {e}")
        return str(timestamp_ms)


def format_number(value, decimals=8):
    """Format number with proper decimal places"""
    try:
        if value is None or value == "N/A":
            return "N/A"
        num = float(value)
        if decimals == 2:
            return f"{num:,.2f}"
        return f"{num:,.{decimals}f}".rstrip('0').rstrip('.')
    except (ValueError, TypeError):
        return str(value)


def send_c2c_to_telegram(value, bot_token, chat_id):
    """
    Parse C2C trade CDC event and send formatted notification to Telegram
    
    Args:
        value: JSON string from Kafka (Debezium CDC format)
        bot_token: Telegram bot token
        chat_id: Telegram chat/channel ID
    
    Returns:
        Original value if successful, None if error
    """
    logger.info(f"Processing C2C trade event: {value}")
    
    try:
        data = json.loads(value)
        
        # Extract operation type (c=create, u=update, d=delete, r=read/snapshot)
        op = data.get("op", "unknown")
        
        # Extract trade data from 'after' field (for create/update)
        # For delete, use 'before' field
        trade_data = data.get("after") if op != "d" else data.get("before")
        
        if not trade_data:
            logger.warning(f"No trade data found in event: {value}")
            return None
        
        # Determine event type for notification
        event_emoji = {
            "c": "🆕",  # Create
            "u": "🔄",  # Update
            "d": "🗑️",  # Delete
            "r": "📸",  # Snapshot/Read
        }.get(op, "❓")
        
        event_type = {
            "c": "New Trade",
            "u": "Trade Updated",
            "d": "Trade Deleted",
            "r": "Historical Trade",
        }.get(op, "Unknown")
        
        # Skip snapshot/read events if only interested in real-time changes
        # Uncomment the following lines to skip historical data
        # if op == "r":
        #     logger.info(f"Skipping snapshot event for order: {trade_data.get('order_number')}")
        #     return None
        
        # Extract trade fields
        order_number = trade_data.get("order_number", "N/A")
        trade_type = trade_data.get("trade_type", "N/A")
        asset = trade_data.get("asset", "N/A")
        fiat = trade_data.get("fiat", "N/A")
        fiat_symbol = trade_data.get("fiat_symbol", "N/A")
        amount = format_number(trade_data.get("amount"), decimals=8)
        total_price = format_number(trade_data.get("total_price"), decimals=2)
        unit_price = format_number(trade_data.get("unit_price"), decimals=2)
        order_status = trade_data.get("order_status", "N/A")
        create_time_ms = trade_data.get("create_time_ms")
        commission = format_number(trade_data.get("commission"), decimals=8)
        counter_part = trade_data.get("counter_part_nick_name", "N/A")
        adv_role = trade_data.get("advertisement_role", "N/A")
        
        # Format timestamp
        trade_time = format_timestamp(create_time_ms)
        
        # Determine trade direction emoji
        trade_emoji = "🟢" if trade_type == "BUY" else "🔴"
        
        # Build Telegram message
        message = (
            f"{event_emoji} *{event_type}* {trade_emoji}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 *Order*: `{order_number}`\n"
            f"💱 *Type*: {trade_type}\n"
            f"💰 *Asset*: {asset}\n"
            f"💵 *Fiat*: {fiat} ({fiat_symbol})\n"
            f"\n"
            f"📊 *Trade Details*:\n"
            f"  • Amount: {amount} {asset}\n"
            f"  • Unit Price: {fiat_symbol}{unit_price}\n"
            f"  • Total: {fiat_symbol}{total_price}\n"
            f"  • Commission: {commission} {asset}\n"
            f"\n"
            f"📌 *Status*: {order_status}\n"
            f"👤 *Counterpart*: {counter_part}\n"
            f"🏷️ *Role*: {adv_role}\n"
            f"🕐 *Time*: {trade_time}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        # Send to Telegram
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        logger.info(f"Sending notification to Telegram for order: {order_number}")
        
        # Create session with retries
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))
        
        response = session.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        logger.info(f"✅ Notification sent successfully for order: {order_number}")
        return value
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decode error: {e}, value={value}")
        return None
    except requests.RequestException as e:
        logger.error(f"❌ Telegram API error: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}, value={value}")
        return None


def main(args):
    """Main Flink job execution"""
    logger.info("=" * 70)
    logger.info("🚀 Starting Flink C2C Telegram Notification Job")
    logger.info("=" * 70)
    logger.info(f"Python version: {sys.version}")
    
    # Get credentials from environment
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", args.telegram_bot_token)
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", args.telegram_chat_id)
    
    if not telegram_bot_token or telegram_bot_token == "missing-token":
        logger.error("❌ TELEGRAM_BOT_TOKEN not set!")
        raise ValueError("TELEGRAM_BOT_TOKEN must be set")
    
    if not telegram_chat_id or telegram_chat_id == "missing-chat-id":
        logger.error("❌ TELEGRAM_CHAT_ID not set!")
        raise ValueError("TELEGRAM_CHAT_ID must be set")
    
    logger.info("✅ Telegram credentials loaded")
    
    # Initialize Flink environment
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)  # Single parallelism for ordered processing
    logger.info("✅ Execution environment initialized")
    
    # Kafka configuration
    bootstrap_servers = args.bootstrap.replace(
        "kafka-kafka-bootstrap.infrastructure.svc",
        "kafka-kafka-bootstrap.infrastructure.svc.cluster.local",
    )
    
    logger.info(f"Kafka bootstrap servers: {bootstrap_servers}")
    logger.info(f"Kafka topic: {args.topic}")
    
    # Test Kafka connectivity
    try:
        import socket
        host, port = bootstrap_servers.split(":")
        with socket.create_connection((host, int(port)), timeout=10):
            logger.info(f"✅ Connected to Kafka at {bootstrap_servers}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Kafka: {e}")
        raise
    
    # Create Kafka source
    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(bootstrap_servers)
        .set_topics(args.topic)
        .set_group_id("flink-c2c-telegram-consumer")
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())  # Process all messages
        .set_value_only_deserializer(SimpleStringSchema())
        .set_property("socket.connection.setup.timeout.ms", "60000")
        .set_property("socket.connection.setup.timeout.max.ms", "120000")
        .set_property("request.timeout.ms", "60000")
        .set_property("metadata.max.age.ms", "60000")
        .build()
    )
    
    logger.info("✅ Kafka source created")
    
    # Create datastream
    try:
        datastream = env.from_source(
            source,
            WatermarkStrategy.no_watermarks(),
            "C2CTelegramSource"
        )
        logger.info("✅ Datastream created")
    except Exception as e:
        logger.error(f"❌ Error creating datastream: {e}")
        raise
    
    # Process and filter
    processed_stream = datastream.map(
        lambda value: send_c2c_to_telegram(value, telegram_bot_token, telegram_chat_id),
        output_type=Types.STRING()
    ).filter(lambda result: result is not None)
    
    logger.info("✅ Processing pipeline configured")
    logger.info("⏳ Waiting for C2C trade events...")
    
    # Execute job
    env.execute("Flink C2C Telegram Notification Job")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Flink job to send Telegram notifications for C2C trades"
    )
    parser.add_argument(
        "--bootstrap",
        required=True,
        help="Kafka bootstrap servers"
    )
    parser.add_argument(
        "--topic",
        required=True,
        help="Input Kafka topic (CDC topic for c2c.trades)"
    )
    parser.add_argument(
        "--telegram-bot-token",
        required=False,
        default="missing-token",
        help="Telegram Bot Token (can also use TELEGRAM_BOT_TOKEN env var)"
    )
    parser.add_argument(
        "--telegram-chat-id",
        required=False,
        default="missing-chat-id",
        help="Telegram Chat ID (can also use TELEGRAM_CHAT_ID env var)"
    )
    
    args = parser.parse_args()
    logger.info(f"Arguments: {vars(args)}")
    
    try:
        main(args)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

