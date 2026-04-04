# Mera Victorino Pro v3.0 — Lightweight Docker Image
FROM python:3.9-slim

WORKDIR /code

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose WebSocket-capable port
EXPOSE 7860

# Start with Python directly (socketio.run handles serving)
CMD ["python", "app.py"]