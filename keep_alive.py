from flask import Flask, jsonify
from threading import Thread
import os
from datetime import datetime, timezone

app = Flask('')

start_time = datetime.now(timezone.utc)

@app.route('/')
def home():
    return "✅ NinjuBot is alive!"

@app.route('/health')
def health():
    uptime = datetime.now(timezone.utc) - start_time
    return jsonify({
        "status": "online",
        "uptime_seconds": int(uptime.total_seconds()),
        "uptime": str(uptime).split(".")[0],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
