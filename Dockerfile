FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-enchant \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 botuser

WORKDIR /bot

# Copy requirements and install dependencies
COPY requirements.txt /bot/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /bot

# Create data directory and set permissions
RUN mkdir -p /data && chown -R botuser:botuser /bot /data

# Switch to non-root user
USER botuser

CMD ["python", "dejavu_bot.py"]
