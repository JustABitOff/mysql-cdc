# Dockerfile for CDC MySQL-to-Iceberg Service

FROM python:3.11-slim

# Install system dependencies for MySQL client
RUN apt-get update && \
    apt-get install -y gcc default-libmysqlclient-dev && \
    rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY cdc_service/ cdc_service/

# Set default environment variables
# Note: AWS_REGION will be overridden by .env file
ENV PYICEBERG_HOME=/app

# Set entrypoint
ENTRYPOINT ["python", "-m", "cdc_service.main"]
