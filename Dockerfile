FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    yt-dlp \
    libopus0 \
    libffi-dev \
    libnacl-dev \
    libsodium-dev \
    build-essential \
    python3-nacl \
    git \
    libssl-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    # && pip install --no-cache-dir --only-binary=:all: PyNaCl \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 10000

CMD ["python", "bot.py"]
