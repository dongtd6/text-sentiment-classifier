# Dockerfile for C2C Streaming Processing
# Supports both:
# 1. Standalone Python script (c2c_data_streaming.py) for Airflow DAGs
# 2. Flink jobs (flink_job_c2c_telegram.py) for Flink deployments

# Image base: Flink 1.19 + Java 17
FROM flink:1.19.1-scala_2.12-java17

# Install Python and system dependencies
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-setuptools \
    python3-wheel \
    gcc \
    libpq-dev \
    curl \
 && ln -s /usr/bin/python3 /usr/bin/python \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY dockerfiles/streaming-processing/requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Debug Python and PyFlink installation
RUN python3 --version && \
    python --version && \
    pip3 show apache-flink && \
    pip3 show requests && \
    pip3 show urllib3 && \
    pip3 show psycopg2-binary && \
    pip3 show binance-sdk-c2c

# Copy Kafka connector and Kafka clients jars for Flink
COPY dockerfiles/streaming-processing/flink-connector-kafka-3.3.0-1.19.jar /opt/flink/lib/
COPY dockerfiles/streaming-processing/kafka-clients-3.3.0.jar /opt/flink/lib/

# ============================================================
# Setup for Standalone Python Script (for Airflow DAG)
# ============================================================
WORKDIR /app

# Copy standalone streaming script and dependencies
COPY dockerfiles/streaming-processing/c2c_data_streaming.py ./
# Copy shared modules from parent dockerfiles directory
COPY dockerfiles/data_ingestion.py ./
COPY dockerfiles/utils.py ./

# Make scripts executable and ensure flink user can access /app
RUN chmod +x /app/c2c_data_streaming.py && \
    chmod -R a+r /app && \
    chown -R flink:flink /app || true

# ============================================================
# Setup for Flink Jobs (for Flink Kubernetes Operator)
# ============================================================
WORKDIR /opt/flink/usrlib
COPY dockerfiles/streaming-processing/flink_job_c2c_telegram.py ./
COPY dockerfiles/streaming-processing/utils.py ./

# Set PYTHONPATH for both standalone and Flink
ENV PYTHONPATH="/app:/opt/flink/usrlib:/usr/local/lib/python3.10/dist-packages"
ENV FLINK_PYTHON_EXECUTABLE="/usr/bin/python3"

# Set default environment variables (can be overridden via Kubernetes)
ENV DB_HOST=airflow-postgresql.orchestration.svc.cluster.local \
    DB_PORT=5432 \
    DB_NAME=postgres \
    DB_USER=postgres \
    FETCH_MODE=latest_month \
    TELEGRAM_BOT_TOKEN="8285678859:AAHEIsShJXwhIRWSplg3MLBQ3n9Laq7GdfY" \
    TELEGRAM_CHAT_ID="1968033655"

# Switch back to flink user
USER flink
