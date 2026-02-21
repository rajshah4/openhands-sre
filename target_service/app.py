from __future__ import annotations

import os
from flask import Flask, jsonify

app = Flask(__name__)
LOCKFILE = "/tmp/service.lock"
READY_FILE = "/tmp/ready.flag"
REQUIRED_ENV = "REQUIRED_API_KEY"
SCENARIO = os.getenv("SCENARIO", "stale_lockfile")


@app.route("/")
def healthcheck():
    if SCENARIO == "stale_lockfile":
        if os.path.exists(LOCKFILE):
            return jsonify({"status": "error", "reason": f"stale lockfile present at {LOCKFILE}"}), 500
        return jsonify({"status": "ok", "scenario": SCENARIO}), 200

    if SCENARIO == "bad_env_config":
        if not os.getenv(REQUIRED_ENV):
            return jsonify({"status": "error", "reason": f"missing required env {REQUIRED_ENV}"}), 500
        return jsonify({"status": "ok", "scenario": SCENARIO}), 200

    if SCENARIO == "readiness_probe_fail":
        if not os.path.exists(READY_FILE):
            return jsonify({"status": "error", "reason": f"missing readiness file {READY_FILE}"}), 500
        return jsonify({"status": "ok", "scenario": SCENARIO}), 200

    if SCENARIO == "port_mismatch":
        return jsonify({"status": "ok", "scenario": SCENARIO, "note": "service listens on non-default port"}), 200

    return jsonify({"status": "error", "reason": f"unknown scenario {SCENARIO}"}), 500


if __name__ == "__main__":
    bind_port = 5001 if SCENARIO == "port_mismatch" else 5000
    app.run(host="0.0.0.0", port=bind_port)
