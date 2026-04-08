from flask import Flask, jsonify, request
from threading import Thread
import os
import sys
import subprocess
import threading
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

@app.route('/deploy', methods=['POST'])
def deploy():
    # Verify the secret sent by GitHub Actions
    secret = request.headers.get('X-Deploy-Secret', '')
    expected = os.getenv('DEPLOY_SECRET', '')
    if not expected or secret != expected:
        return jsonify({"error": "Unauthorized"}), 401

    # Pull latest code from GitHub
    pull = subprocess.run(
        ['git', 'pull', 'origin', 'main'],
        capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))
    )
    print(f"[Deploy] git pull stdout: {pull.stdout}", flush=True)
    print(f"[Deploy] git pull stderr: {pull.stderr}", flush=True)

    if pull.returncode != 0:
        return jsonify({"error": "git pull failed", "details": pull.stderr}), 500

    # Restart the bot process after a short delay (Replit will rerun bot.py)
    def restart():
        import time
        time.sleep(1)
        os.execv(sys.executable, [sys.executable, 'bot.py'])

    threading.Thread(target=restart, daemon=True).start()

    return jsonify({
        "status": "deploying",
        "git_output": pull.stdout.strip(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
