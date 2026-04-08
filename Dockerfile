FROM python:3.10-slim

# System libs required for PyNaCl and FFmpeg audio
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

# Install PyNaCl FIRST using a prebuilt wheel - required for Discord voice
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "PyNaCl>=1.5.0" \
    && python -c "import nacl.secret; print('PyNaCl OK:', nacl.__version__)" \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 10000

CMD ["python", "bot.py"]