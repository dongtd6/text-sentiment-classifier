FROM python:3.9-slim

WORKDIR /app

# Copy requirements if you have one
COPY dockerfiles/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy necessary scripts
# Since the Dockerfile is in dockerfiles/batch-processing/
# and utils.py and data_ingestion.py are in dockerfiles/
# We need to set the build context correctly when running 'docker build'
# For example: docker build -f dockerfiles/batch-processing/Dockerfile . (from repo root)
COPY dockerfiles/utils.py /app/utils.py
COPY dockerfiles/data_ingestion.py /app/data_ingestion.py
COPY dockerfiles/batch-processing/ingestion.py /app/ingestion.py

# Make sure the application code is in PYTHONPATHadf
ENV PYTHONPATH=/app

CMD ["python", "ingestion.py"]
