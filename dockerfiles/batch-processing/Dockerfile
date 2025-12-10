FROM python:3.9-slim

WORKDIR /app

# Install Java (required for Spark)
RUN apt-get update && \
    apt-get install -y default-jdk && \
    apt-get clean;

# Copy requirements if you have one
COPY dockerfiles/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install pyspark delta-spark pyyaml

# Copy necessary scripts
# We assume build context is the repository root
COPY dockerfiles/utils.py /app/utils.py
COPY dockerfiles/data_ingestion.py /app/data_ingestion.py
COPY dockerfiles/batch-processing/ingestion.py /app/ingestion.py
COPY dockerfiles/batch-processing/bronze_job.py /app/bronze_job.py
COPY dockerfiles/batch-processing/ingest_to_bronze.py /app/ingest_to_bronze.py

# Copy common modules and configs
COPY dockerfiles/batch-processing/common /app/common
COPY dockerfiles/batch-processing/configs /app/configs

# Make sure the application code is in PYTHONPATH
ENV PYTHONPATH=/app

CMD ["python", "ingestion.py"]
