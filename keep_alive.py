from flask import Flask, jsonify, request
from threading import Thread
import os
import sys
import signal
import subprocess
import threading
from datetime import datetime, timezone

app = Flask('')

start_time = datetime.now(timezone.utc)

# Prevent multiple simultaneous deploy calls
_deploy_lock = threading.Lock()
_deploy_in_progress = False

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
    global _deploy_in_progress

    # Verify secret
    secret = request.headers.get('X-Deploy-Secret', '')
    expected = os.getenv('DEPLOY_SECRET', '')
    if not expected or secret != expected:
        return jsonify({"error": "Unauthorized"}), 401

    # Block duplicate deploy calls
    if not _deploy_lock.acquire(blocking=False):
        return jsonify({"error": "Deploy already in progress"}), 429
    _deploy_in_progress = True

    try:
        # Pull latest code from GitHub
        pull = subprocess.run(
            ['git', 'pull', 'origin', 'main'],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        print(f"[Deploy] git pull stdout: {pull.stdout}", flush=True)
        print(f"[Deploy] git pull stderr: {pull.stderr}", flush=True)

        if pull.returncode != 0:
            return jsonify({"error": "git pull failed", "details": pull.stderr}), 500

        git_out = pull.stdout.strip()

        # Send response BEFORE restarting so GitHub Actions gets a 200
        response = jsonify({
            "status": "deploying",
            "git_output": git_out,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # Schedule restart — SIGTERM to self; Replit restarts the process cleanly
        def do_restart():
            import time
            time.sleep(2)  # Give Flask time to send the response
            print("[Deploy] Restarting bot process...", flush=True)
            os.kill(os.getpid(), signal.SIGTERM)

        threading.Thread(target=do_restart, daemon=True).start()

        return response

    finally:
        # Release lock after a delay so rapid retries are still blocked
        def release():
            import time
            time.sleep(10)
            global _deploy_in_progress
            _deploy_in_progress = False
            _deploy_lock.release()
        threading.Thread(target=release, daemon=True).start()


def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
