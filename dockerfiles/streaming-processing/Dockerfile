FROM flink:1.19.1-scala_2.12-java17

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip curl \
 && ln -s /usr/bin/python3 /usr/bin/python \
 && rm -rf /var/lib/apt/lists/*

# Python deps (streaming only)
RUN pip3 install --no-cache-dir \
    apache-flink==1.19.1 \
    requests \
    urllib3

# Kafka connector
COPY dockerfiles/streaming-processing/flink-connector-kafka-3.3.0-1.19.jar /opt/flink/lib/
COPY dockerfiles/streaming-processing/kafka-clients-3.3.0.jar /opt/flink/lib/

# Flink job
WORKDIR /opt/flink/usrlib
COPY dockerfiles/streaming-processing/flink_job_c2c_telegram.py ./

ENV PYTHONPATH="/opt/flink/usrlib"
ENV FLINK_PYTHON_EXECUTABLE="/usr/bin/python3"

USER flink
# new build