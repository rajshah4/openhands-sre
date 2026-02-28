from __future__ import annotations

import os
from flask import Flask, jsonify, request

app = Flask(__name__)
LOCKFILE = "/tmp/service.lock"
READY_FILE = "/tmp/ready.flag"
REQUIRED_ENV = "REQUIRED_API_KEY"
SCENARIO = os.getenv("SCENARIO", "stale_lockfile")


def render_html(status: str, title: str, message: str, details: str = "") -> str:
    """Render a nice HTML status page."""
    if status == "ok":
        bg_color = "#10b981"  # green
        icon = "✅"
        status_text = "HEALTHY"
    else:
        bg_color = "#ef4444"  # red
        icon = "❌"
        status_text = "ERROR"
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, {bg_color}22 0%, {bg_color}44 100%);
        }}
        .container {{
            background: white;
            border-radius: 20px;
            padding: 60px 80px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            text-align: center;
            max-width: 600px;
        }}
        .icon {{
            font-size: 80px;
            margin-bottom: 20px;
        }}
        .status {{
            font-size: 14px;
            font-weight: 600;
            letter-spacing: 2px;
            color: {bg_color};
            margin-bottom: 10px;
        }}
        h1 {{
            font-size: 32px;
            color: #1f2937;
            margin-bottom: 20px;
        }}
        .message {{
            font-size: 18px;
            color: #6b7280;
            line-height: 1.6;
            margin-bottom: 30px;
        }}
        .details {{
            background: #f3f4f6;
            border-radius: 10px;
            padding: 20px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 14px;
            color: #374151;
            text-align: left;
            word-break: break-all;
        }}
        .scenario {{
            margin-top: 30px;
            font-size: 12px;
            color: #9ca3af;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">{icon}</div>
        <div class="status">{status_text}</div>
        <h1>{title}</h1>
        <p class="message">{message}</p>
        {f'<div class="details">{details}</div>' if details else ''}
        <p class="scenario">Scenario: {SCENARIO}</p>
    </div>
</body>
</html>'''


def wants_json() -> bool:
    """Check if client wants JSON (curl, API) vs HTML (browser)."""
    accept = request.headers.get('Accept', '')
    user_agent = request.headers.get('User-Agent', '').lower()
    # curl and most CLI tools don't send Accept: text/html
    if 'text/html' in accept and 'curl' not in user_agent:
        return False
    if 'application/json' in accept:
        return True
    if 'curl' in user_agent:
        return True
    return False


@app.route("/")
def healthcheck():
    if SCENARIO == "stale_lockfile":
        if os.path.exists(LOCKFILE):
            if wants_json():
                return jsonify({"status": "error", "reason": f"stale lockfile present at {LOCKFILE}"}), 500
            return render_html(
                "error",
                "Service Unavailable",
                "The service failed to start due to a stale lockfile from a previous crash.",
                f"🔒 Lockfile: {LOCKFILE}"
            ), 500
        if wants_json():
            return jsonify({"status": "ok", "scenario": SCENARIO}), 200
        return render_html(
            "ok",
            "Service Running",
            "All systems operational. The health-api is responding normally.",
        ), 200

    if SCENARIO == "bad_env_config":
        if not os.getenv(REQUIRED_ENV):
            if wants_json():
                return jsonify({"status": "error", "reason": f"missing required env {REQUIRED_ENV}"}), 500
            return render_html(
                "error",
                "Configuration Error",
                "Required environment variable is not set.",
                f"Missing: {REQUIRED_ENV}"
            ), 500
        if wants_json():
            return jsonify({"status": "ok", "scenario": SCENARIO}), 200
        return render_html("ok", "Service Running", "Configuration loaded successfully.")

    if SCENARIO == "readiness_probe_fail":
        if not os.path.exists(READY_FILE):
            if wants_json():
                return jsonify({"status": "error", "reason": f"missing readiness file {READY_FILE}"}), 500
            return render_html(
                "error",
                "Not Ready",
                "The service is starting but not yet ready to accept traffic.",
                f"Waiting for: {READY_FILE}"
            ), 500
        if wants_json():
            return jsonify({"status": "ok", "scenario": SCENARIO}), 200
        return render_html("ok", "Service Ready", "Readiness probe passing. Service is ready for traffic.")

    if SCENARIO == "port_mismatch":
        if wants_json():
            return jsonify({"status": "ok", "scenario": SCENARIO, "note": "service listens on non-default port"}), 200
        return render_html("ok", "Service Running", "Service is running on a non-default port.")

    if wants_json():
        return jsonify({"status": "error", "reason": f"unknown scenario {SCENARIO}"}), 500
    return render_html("error", "Unknown Error", f"Unknown scenario: {SCENARIO}")


if __name__ == "__main__":
    bind_port = 5001 if SCENARIO == "port_mismatch" else 5000
    app.run(host="0.0.0.0", port=bind_port)
