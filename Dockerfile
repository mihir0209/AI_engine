FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt requirements_server.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements_server.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p templates static/css static/js static/img uploads logs cache data

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "server.py"]
