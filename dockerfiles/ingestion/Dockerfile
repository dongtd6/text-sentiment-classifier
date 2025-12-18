# Dockerfile
FROM python:3.10-slim

# =========================
# System deps (minimal)
# =========================
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# =========================
# Workdir
# =========================
WORKDIR /app

# =========================
# Python deps (INGESTION ONLY)
# =========================
COPY dockerfiles/ingestion/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# =========================
# Ingestion source code ONLY
# =========================
COPY dockerfiles/ingestion/c2c_ingestion.py /app/c2c_ingestion.py
COPY dockerfiles/ingestion/data_ingestion.py /app/data_ingestion.py
COPY dockerfiles/ingestion/utils.py /app/utils.py

# =========================
# Runtime
# =========================
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

ENTRYPOINT ["python3", "/app/c2c_ingestion.py"]
