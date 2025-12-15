FROM python:3.9-slim

WORKDIR /app

# Install Java and curl (required for Spark)
RUN apt-get update && \
    apt-get install -y default-jdk curl && \
    apt-get clean;

# Download Hadoop AWS and AWS SDK JARs for S3 support ...
RUN mkdir -p /jars && \
    curl -o /jars/hadoop-aws-3.3.2.jar https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.2/hadoop-aws-3.3.2.jar && \
    curl -o /jars/aws-java-sdk-bundle-1.11.1026.jar https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.11.1026/aws-java-sdk-bundle-1.11.1026.jar

# Copy requirements
COPY dockerfiles/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install pyspark delta-spark pyyaml

# Copy necessary scripts
COPY dockerfiles/utils.py /app/utils.py
COPY dockerfiles/data_ingestion.py /app/data_ingestion.py

# Copy the main ingestion script (which now handles bronze logic too)
COPY dockerfiles/batch-processing/ingestion.py /app/ingestion.py

# Copy common modules and configs
COPY dockerfiles/batch-processing/common /app/common
COPY dockerfiles/batch-processing/configs /app/configs

# PYTHONPATH
ENV PYTHONPATH=/app

CMD ["python", "ingestion.py"]
