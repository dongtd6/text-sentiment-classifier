FROM python:3.9-slim

WORKDIR /app

# Install Java (required for Spark)
RUN apt-get update && \
    apt-get install -y default-jdk curl && \
    apt-get clean;

# Create jars directory
RUN mkdir -p /jars

# Copy local JAR files for Spark and Hadoop
COPY dockerfiles/batch-processing/jars/hadoop-aws-3.3.2.jar /jars/
COPY dockerfiles/batch-processing/jars/postgresql-42.6.0.jar /jars/
COPY dockerfiles/batch-processing/jars/deequ-2.0.3-spark-3.3.jar /jars/

# Download AWS SDK Bundle (not in local jars)
RUN curl -o /jars/aws-java-sdk-bundle-1.11.1026.jar \
    https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.11.1026/aws-java-sdk-bundle-1.11.1026.jar

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
