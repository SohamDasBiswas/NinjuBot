FROM python:3.11-slim

# Install system dependencies including ffmpeg for music
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus0 \
    libffi-dev \
    libnacl-dev \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all bot files
COPY . .

# Create data directory for SQLite database (persistent volume mount point)
RUN mkdir -p /app/data

# Expose port for keep_alive Flask server (UptimeRobot pings this)
EXPOSE 8080

# Run the bot
CMD ["python", "bot.py"]
