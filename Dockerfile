FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including git
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY .env .env

WORKDIR /app/src

CMD ["python3", "run_node.py"]
