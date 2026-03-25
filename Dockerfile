FROM python:3.10-slim

# System deps: ffmpeg for audio, libopus for voice, libsodium for PyNaCl
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    libffi-dev \
    libsodium-dev \
    libssl-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Install PyNaCl first using a pre-built wheel (no compilation needed)
# This fixes the "nacl library needed for voice" error
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --only-binary=:all: PyNaCl \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 10000

CMD ["python", "bot.py"]
