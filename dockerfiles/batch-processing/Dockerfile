FROM python:3.9-slim

WORKDIR /app

# Install Java (required for Spark)
RUN apt-get update && \
    apt-get install -y default-jdk curl && \
    apt-get clean;

# Create jars directory
RUN mkdir -p /jars

# Copy all JAR files from the local directory (includes delta jars, deequ, etc.)
COPY dockerfiles/batch-processing/jars/ /jars/

# Download Hadoop AWS and AWS SDK Bundle compatible with Spark 3.4.1 (Hadoop 3.3.4)
# Overwriting or adding to what might be in local jars
RUN curl -o /jars/hadoop-aws-3.3.4.jar \
    https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar

RUN curl -o /jars/aws-java-sdk-bundle-1.12.262.jar \
    https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar

# Remove potentially conflicting older versions if they exist from COPY
RUN rm -f /jars/hadoop-aws-3.3.2.jar /jars/aws-java-sdk-bundle-1.11.1026.jar

# Copy requirements
COPY dockerfiles/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Downgrade to match user's working local setup and existing Delta jars (2.4.0)
RUN pip install pyspark==3.4.1 delta-spark==2.4.0 pyyaml

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
