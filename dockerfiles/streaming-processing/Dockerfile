# Dockerfile for C2C Trading Data Streaming Service
# Fetches historical trading data from Binance C2C API and streams to PostgreSQL

FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY dockerfiles/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules from parent dockerfiles directory
COPY dockerfiles/utils.py /app/utils.py
COPY dockerfiles/data_ingestion.py /app/data_ingestion.py

# Copy the streaming processing script
COPY dockerfiles/streaming-processing/c2c_data_streaming.py /app/c2c_data_streaming.py

# Make the script executable
RUN chmod +x /app/c2c_data_streaming.py

# Set environment variables with defaults
# These can be overridden at runtime via Kubernetes
ENV DB_HOST=postgresql.storage.svc.cluster.local \
    DB_PORT=5432 \
    DB_NAME=postgres \
    DB_USER=pgadmin \
    FETCH_MODE=latest_month

# Health check (optional)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the streaming job
CMD ["python3", "/app/c2c_data_streaming.py"]

