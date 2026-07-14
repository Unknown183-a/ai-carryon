# app_cricket.py — minimal trigger endpoint for Render free tier
import os
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)
TRIGGER_SECRET = os.getenv("TRIGGER_SECRET", "")
_running = {"busy": False}


@app.route("/")
def health():
    return jsonify({"status": "ok", "service": "ai-carryon-cricket"})


@app.route("/trigger")
def trigger():
    secret = request.args.get("secret", "")
    if not TRIGGER_SECRET or secret != TRIGGER_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    if _running["busy"]:
        return jsonify({"status": "already_running"}), 202

    def _run():
        _running["busy"] = True
        try:
            from scheduler_cricket import run_cricket_cycle
            result = run_cricket_cycle()
            print(f"Cycle result: {result}")
        except Exception as e:
            print(f"Cycle failed: {e}")
        finally:
            _running["busy"] = False

    threading.Thread(target=_run).start()
    return jsonify({"status": "started"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
