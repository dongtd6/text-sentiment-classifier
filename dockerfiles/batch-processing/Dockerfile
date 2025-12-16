FROM python:3.9-slim

WORKDIR /app

# Install Java (required for Spark)
RUN apt-get update && \
    apt-get install -y default-jdk curl && \
    apt-get clean;

# Create jars directory
RUN mkdir -p /jars

# Copy all JAR files from the local directory
COPY dockerfiles/batch-processing/jars/ /jars/

# Download AWS SDK Bundle (ensure this specific version matches what Hadoop expects if not provided locally)
# If it's already in the jars folder, this might overwrite or be redundant, but safe to keep if unsure
RUN curl -o /jars/aws-java-sdk-bundle-1.11.1026.jar \
    https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.11.1026/aws-java-sdk-bundle-1.11.1026.jar

# Copy requirements
COPY dockerfiles/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Pin Spark versions to ensure Scala 2.12 compatibility (matching Deequ/Hadoop jars)
RUN pip install pyspark==3.5.3 delta-spark==3.2.0 pyyaml

# Copy necessary scripts from root dockerfiles
COPY dockerfiles/utils.py /app/utils.py
COPY dockerfiles/data_ingestion.py /app/data_ingestion.py

# Copy common modules and configs
COPY dockerfiles/batch-processing/common /app/common
COPY dockerfiles/batch-processing/configs /app/configs

# Copy ETL jobs
COPY dockerfiles/batch-processing/etl_jobs /app/etl_jobs

# PYTHONPATH
ENV PYTHONPATH=/app
ENV SPARK_CLASSPATH="/jars/*"

CMD ["python", "etl_jobs/ingestion.py"]
