# MTEC Schedule Bot Dockerfile
FROM python:3.13-slim

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Work directory
WORKDIR /app

# Install system dependencies and Poetry
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
RUN pip install -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY assets/ ./assets/

# Create non-root user
RUN useradd -m -s /bin/bash botuser \
    && chown -R botuser:botuser /app
USER botuser

# Run the application
CMD ["python", "src/bot/main.py"]
