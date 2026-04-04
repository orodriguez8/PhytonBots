# Mera Victorino Pro v3.0 — Lightweight Docker Image
FROM python:3.11-bookworm

WORKDIR /code

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose WebSocket-capable port
EXPOSE 7860

# Start with Python directly (socketio.run handles serving)
CMD ["python", "main.py"]
