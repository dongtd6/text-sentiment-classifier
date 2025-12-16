# Use official Spark image with Python support
# Spark 3.4.1 is compatible with Delta Lake 2.4.0
FROM apache/spark:3.4.1-python3

# Switch to root to install packages
USER root

WORKDIR /app

# Install Python 3.9 (binance-sdk-c2c requires Python>=3.9, but image has 3.8)
RUN apt-get update && \
    apt-get install -y software-properties-common curl && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.9 python3.9-dev python3.9-venv python3-pip && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1 && \
    ln -sf /usr/bin/python3.9 /usr/bin/python && \
    rm -rf /var/lib/apt/lists/*

# Create jars directory and download required JARs for MinIO/S3A and Delta Lake
RUN mkdir -p /opt/spark/jars && \
    curl -L -o /opt/spark/jars/hadoop-aws-3.3.4.jar \
    https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    curl -L -o /opt/spark/jars/aws-java-sdk-bundle-1.12.262.jar \
    https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar && \
    curl -L -o /opt/spark/jars/delta-core_2.12-2.4.0.jar \
    https://repo1.maven.org/maven2/io/delta/delta-core_2.12/2.4.0/delta-core_2.12-2.4.0.jar && \
    curl -L -o /opt/spark/jars/delta-storage-2.4.0.jar \
    https://repo1.maven.org/maven2/io/delta/delta-storage/2.4.0/delta-storage-2.4.0.jar

# Copy additional local JARs if any (e.g., Deequ, PostgreSQL driver)
COPY dockerfiles/batch-processing/jars/*.jar /opt/spark/jars/

# Copy requirements file
COPY dockerfiles/requirements.txt .

# Install uv (fast Python package installer)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Install Python dependencies (apache/spark image already has PySpark 3.4.1)
RUN uv pip install --system -r requirements.txt && \
    uv pip install --system delta-spark==2.4.0 pyyaml minio google-cloud-storage

# Copy necessary scripts from root dockerfiles
COPY dockerfiles/utils.py /app/utils.py
COPY dockerfiles/data_ingestion.py /app/data_ingestion.py

# Copy common modules and configs
COPY dockerfiles/batch-processing/common /app/common
COPY dockerfiles/batch-processing/configs /app/configs

# Copy ETL jobs
COPY dockerfiles/batch-processing/etl_jobs /app/etl_jobs

# Option 1 (Development): Copy GCS credentials into image - NOT RECOMMENDED for production
# COPY dockerfiles/batch-processing/google-auth.json /app/google-auth.json
# ENV GOOGLE_APPLICATION_CREDENTIALS=/app/google-auth.json

# Option 2 (Production): Mount GCS credentials from K8s secret at runtime
# Secret will be mounted at /secrets/google-auth.json via Kubernetes volumeMount
# GOOGLE_APPLICATION_CREDENTIALS will be set via DAG env_vars

# Set environment variables
ENV SPARK_HOME=/opt/spark
ENV PYTHONPATH=$SPARK_HOME/python:$SPARK_HOME/python/lib/py4j-0.10.9.7-src.zip:/app
ENV PATH=$SPARK_HOME/bin:$PATH

# Create Ivy cache directory with proper permissions for spark user
RUN mkdir -p /home/spark/.ivy2/cache && \
    mkdir -p /home/spark/.ivy2/jars && \
    chown -R spark:spark /home/spark/.ivy2

# Switch back to spark user for security
USER spark

# Default command: run the ingestion script
CMD ["python3", "etl_jobs/ingestion.py"]
