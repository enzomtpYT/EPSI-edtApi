# Use a multi-arch base image
FROM --platform=$BUILDPLATFORM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies for lxml and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies for lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed dependencies from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app .

EXPOSE 5000

CMD ["python", "wsgi.py"] 