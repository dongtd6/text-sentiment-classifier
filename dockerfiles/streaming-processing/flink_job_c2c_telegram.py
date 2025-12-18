#!/usr/bin/env python3
"""
Flink Job: Stream CDC C2C trades from Kafka and send Telegram notifications
Only handles CDC op = 'c' (INSERT)
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
    KafkaSource,
    KafkaOffsetsInitializer,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =========================================================
# Utils
# =========================================================

def format_timestamp(ts_ms):
    if not ts_ms:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(int(ts_ms) / 1000)
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(ts_ms)


def format_number(v, decimals=8):
    try:
        return f"{float(v):,.{decimals}f}".rstrip("0").rstrip(".")
    except Exception:
        return str(v)


# =========================================================
# Telegram sender
# =========================================================

def send_c2c_to_telegram(value, bot_token, chat_id):
    try:
        data = json.loads(value)

        # CDC operation
        op = data.get("op")
        if op != "c":
            return None

        trade = data.get("after")
        if not trade:
            return None

        order_number = trade.get("order_number", "N/A")
        trade_type = trade.get("trade_type", "N/A")
        asset = trade.get("asset", "N/A")
        fiat_symbol = trade.get("fiat_symbol", "")
        amount = format_number(trade.get("amount"), 8)
        total_price = format_number(trade.get("total_price"), 2)
        create_time = format_timestamp(trade.get("create_time_ms"))

        emoji = "🟢" if trade_type == "BUY" else "🔴"

        message = (
            f"🆕 *New C2C Trade* {emoji}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📋 Order: `{order_number}`\n"
            f"💱 Type: {trade_type}\n"
            f"💰 Amount: {amount} {asset}\n"
            f"💵 Total: {fiat_symbol}{total_price}\n"
            f"🕐 Time: {create_time}"
        )

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        session.mount("https://", HTTPAdapter(max_retries=retries))

        session.post(
            url,
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            },
            timeout=10,
        ).raise_for_status()

        logger.info(f"Telegram sent for order {order_number}")
        return value

    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return None


# =========================================================
# Main
# =========================================================

def main(args):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set")

    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(args.bootstrap)
        .set_topics(args.topic)
        .set_group_id("flink-c2c-telegram")
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    stream = env.from_source(
        source,
        WatermarkStrategy.no_watermarks(),
        "c2c-cdc-source",
    )

    (
        stream
        .map(
            lambda v: send_c2c_to_telegram(v, bot_token, chat_id),
            output_type=Types.STRING(),
        )
        .filter(lambda x: x is not None)
    )

    env.execute("C2C CDC → Telegram Streaming Job")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", required=True)
    parser.add_argument("--topic", required=True)
    args = parser.parse_args()

    main(args)
