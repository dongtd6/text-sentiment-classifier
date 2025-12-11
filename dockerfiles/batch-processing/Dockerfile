FROM python:3.9-slim

WORKDIR /app

# Install Java (required for Spark)
RUN apt-get update && \
    apt-get install -y default-jdk && \
    apt-get clean;

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
