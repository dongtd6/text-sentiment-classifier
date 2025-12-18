#!/usr/bin/env python3
"""
Flink Job: C2C Trading Telegram Notifier (SAFE VERSION)

- Consume CDC events from Kafka (Debezium)
- Send Telegram notifications
- NO Markdown
- Emoji only
- NEVER causes Telegram 400
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaOffsetsInitializer,
    KafkaSource,
)

# =========================================================
# Logging
# =========================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =========================================================
# Utils
# =========================================================
def format_timestamp(timestamp_ms):
    if not timestamp_ms:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(int(timestamp_ms) / 1000)
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(timestamp_ms)


def format_number(value, decimals=8):
    try:
        num = float(value)
        if decimals == 2:
            return f"{num:,.2f}"
        return f"{num:,.{decimals}f}".rstrip("0").rstrip(".")
    except Exception:
        return "N/A"


# =========================================================
# Telegram Sender (SAFE)
# =========================================================
def send_c2c_to_telegram(value, bot_token, chat_id):
    try:
        data = json.loads(value)

        op = data.get("op", "unknown")
        trade = data.get("after") if op != "d" else data.get("before")
        if not trade:
            return None

        # Icons
        event_icon = {
            "c": "🆕",
            "u": "🔄",
            "d": "🗑️",
            "r": "📸",
        }.get(op, "❓")

        trade_type = trade.get("trade_type", "N/A")
        trade_icon = "🟢" if trade_type == "BUY" else "🔴"

        order_number = trade.get("order_number", "N/A")
        asset = trade.get("asset", "N/A")
        fiat_symbol = trade.get("fiat_symbol", "")
        amount = format_number(trade.get("amount"), 8)
        unit_price = format_number(trade.get("unit_price"), 2)
        total_price = format_number(trade.get("total_price"), 2)
        commission = format_number(trade.get("commission"), 8)
        status = trade.get("order_status", "N/A")
        counter_part = trade.get("counter_part_nick_name", "N/A")
        role = trade.get("advertisement_role", "N/A")
        trade_time = format_timestamp(trade.get("create_time_ms"))

        # TEXT ONLY (NO MARKDOWN)
        message = (
            f"{event_icon} C2C TRADE ALERT {trade_icon}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📄 Order ID : {order_number}\n"
            f"🔁 Type     : {trade_type}\n"
            f"💰 Asset   : {asset}\n"
            f"📦 Amount  : {amount} {asset}\n"
            f"💵 Price   : {fiat_symbol}{unit_price}\n"
            f"💲 Total   : {fiat_symbol}{total_price}\n"
            f"💸 Fee     : {commission} {asset}\n"
            f"📌 Status  : {status}\n"
            f"👤 Partner : {counter_part}\n"
            f"🏷️ Role    : {role}\n"
            f"🕒 Time    : {trade_time}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )

        session = requests.Session()
        session.mount(
            "https://",
            HTTPAdapter(
                max_retries=Retry(
                    total=3,
                    backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504],
                )
            ),
        )

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
        }

        response = session.post(url, json=payload, timeout=10)
        response.raise_for_status()

        logger.info(f"✅ Telegram sent: {order_number}")
        return value

    except Exception as e:
        logger.error(f"❌ Telegram send failed: {e}")
        return None


# =========================================================
# Main
# =========================================================
def main(args):
    logger.info("🚀 Starting Flink C2C Telegram Notification Job")

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", args.telegram_bot_token)
    chat_id = os.getenv("TELEGRAM_CHAT_ID", args.telegram_chat_id)

    if not bot_token or not chat_id:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")

    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)

    bootstrap_servers = args.bootstrap.replace(
        "kafka-kafka-bootstrap.infrastructure.svc",
        "kafka-kafka-bootstrap.infrastructure.svc.cluster.local",
    )

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(bootstrap_servers)
        .set_topics(args.topic)
        .set_group_id("flink-c2c-telegram-consumer")
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    datastream = env.from_source(
        source,
        WatermarkStrategy.no_watermarks(),
        "C2CTelegramSource",
    )

    datastream.map(
        lambda v: send_c2c_to_telegram(v, bot_token, chat_id),
        output_type=Types.STRING(),
    ).filter(lambda v: v is not None)

    env.execute("Flink C2C Telegram Notification Job")


# =========================================================
# Entry
# =========================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--telegram-bot-token", default="missing")
    parser.add_argument("--telegram-chat-id", default="missing")

    args = parser.parse_args()

    try:
        main(args)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
