# flink_job_telegram.py
import argparse
import json
import logging
import os
import sys

# from pyflink.datastream.connectors.kafka import KafkaSource
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    KafkaSink,
    KafkaSource,
)
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from utils import send_to_telegram

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(args):
    print(f"Starting Flink Telegram Notification Job... Python version: {sys.version}")
    # Use environment variables directly
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", args.telegram_bot_token)
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", args.telegram_chat_id)
    # print(f"Using Telegram bot token: {telegram_bot_token}")
    # print(f"Using Telegram chat ID: {telegram_chat_id}")
    execution_environment = (
        StreamExecutionEnvironment.get_execution_environment()
    )  # type: StreamExecutionEnvironment
    execution_environment.set_parallelism(
        1
    )  # Set parallelism to 1 for ordered processing
    logger.info("Execution environment initialized")

    # Kafka configuration
    bootstrap_servers = args.bootstrap.replace(
        "kafka-kafka-bootstrap.infrastructure.svc",
        "kafka-kafka-bootstrap.infrastructure.svc.cluster.local",
    )
    print(f"Using Kafka bootstrap servers: {bootstrap_servers}")
    try:
        # Test Kafka connection
        import socket

        host, port = bootstrap_servers.split(":")
        with socket.create_connection((host, int(port)), timeout=10):
            print(f"Successfully connected to Kafka at {bootstrap_servers}")
    except Exception as e:
        print(f"Failed to connect to Kafka at {bootstrap_servers}: {e}")
        raise

    # Start from earliest offset        .set_starting_offset("earliest") \
    print(f"Creating Kafka source with topic:", args.topic)
    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(bootstrap_servers)
        .set_topics(args.topic)
        .set_group_id("flink-telegram-consumer")
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())
        .set_property("socket.connection.setup.timeout.ms", "60000")
        .set_property("socket.connection.setup.timeout.max.ms", "120000")
        .set_property("request.timeout.ms", "60000")
        .set_property("metadata.max.age.ms", "60000")
        .build()
    )

    logger.info("Kafka source created, starting to process messages...")
    try:
        datastream = execution_environment.from_source(
            source, WatermarkStrategy.no_watermarks(), "TelegramSource"
        )
    except Exception as e:
        print(f"Error creating data stream from source: {e}")
        raise

    # print message from datastream for debugging
    logger.info("Subscribing to Kafka topic and waiting for messages...")
    datastream = datastream.map(
        lambda value: send_to_telegram(value, telegram_bot_token, telegram_chat_id),
        output_type=Types.STRING(),
    ).filter(lambda result: result is not None)

    execution_environment.execute("Flink Telegram Notification Job")
    logger.info("Flink job execution started")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", required=True, help="Kafka bootstrap servers")
    parser.add_argument("--topic", required=True, help="Input Kafka topic")
    parser.add_argument(
        "--telegram-bot-token",
        required=False,
        default="missing-token",
        help="Telegram Bot Token",
    )  # not working cause flink_job_telegram.py read as text, not env variable
    parser.add_argument(
        "--telegram-chat-id",
        required=False,
        default="missing-chat-id",
        help="Telegram Chat ID",
    )  # same
    logger.info("Parsing arguments...")
    args = parser.parse_args()
    print(f"Arguments: {vars(args)}")
    main(args)
