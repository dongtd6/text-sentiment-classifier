# flink_job_sentiment.py
import argparse
import json

from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaRecordSerializationSchema,
    KafkaSink,
    KafkaSource,
)
from utils import call_model_api, process_comment


def main(args):
    execution_environment = StreamExecutionEnvironment.get_execution_environment()
    execution_environment.set_parallelism(1)

    bootstrap_servers = args.bootstrap.replace(
        "kafka-kafka-bootstrap.infrastructure.svc",
        "kafka-kafka-bootstrap.infrastructure.svc.cluster.local",
    )
    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(bootstrap_servers)
        .set_topics(args.in_topic)
        .set_group_id("flink-sentiment-consumer")
        .set_value_only_deserializer(SimpleStringSchema())
        .set_property("socket.connection.setup.timeout.ms", "60000")
        .set_property("socket.connection.setup.timeout.max.ms", "120000")
        .set_property("request.timeout.ms", "60000")
        .set_property("metadata.max.age.ms", "60000")
        .build()
    )

    datastream = execution_environment.from_source(
        source, WatermarkStrategy.no_watermarks(), "KafkaSource"
    )

    processed_stream = datastream.map(
        lambda value: process_comment(value, args.model_url), output_type=Types.STRING()
    ).filter(lambda result: result is not None)

    sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(bootstrap_servers)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(args.out_topic)
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .build()
    )

    processed_stream.sink_to(sink)

    execution_environment.execute("Flink Sentiment Analysis Job")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", required=True, help="Kafka bootstrap servers")
    parser.add_argument("--in-topic", required=True, help="Input Kafka topic")
    parser.add_argument("--out-topic", required=True, help="Output Kafka topic for NEG")
    parser.add_argument("--model-url", required=True, help="Model serving API URL")

    args = parser.parse_args()
    main(args)
