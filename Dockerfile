# syntax=docker/dockerfile:1

FROM python:3.12-slim

# Application directory
WORKDIR /app

# Python / Cloud Run environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for better Docker caching
COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . .

# Cloud Run sends traffic to this port
EXPOSE 8080

# Start FastAPI
# Cloud Run requires 0.0.0.0 and uses the PORT environment variable
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT}"]