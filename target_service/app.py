from __future__ import annotations

import os
from flask import Flask, jsonify, request

app = Flask(__name__)

# State files for each scenario
LOCKFILE = "/tmp/service.lock"
READY_FILE = "/tmp/ready.flag"
REQUIRED_ENV = "REQUIRED_API_KEY"

# Legacy support for single-scenario mode
SCENARIO = os.getenv("SCENARIO", "")


def render_html(status: str, title: str, message: str, details: str = "", scenario: str = "") -> str:
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
        <p class="scenario">Scenario: {scenario}</p>
    </div>
</body>
</html>'''


def render_index() -> str:
    """Render the index page with links to all scenarios."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenHands SRE Demo</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 60px 80px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            text-align: center;
            max-width: 700px;
        }
        h1 {
            font-size: 36px;
            color: #1f2937;
            margin-bottom: 10px;
        }
        .subtitle {
            font-size: 18px;
            color: #6b7280;
            margin-bottom: 40px;
        }
        .scenarios {
            display: grid;
            gap: 20px;
        }
        .scenario-card {
            background: #f9fafb;
            border-radius: 12px;
            padding: 25px;
            text-align: left;
            text-decoration: none;
            color: inherit;
            transition: transform 0.2s, box-shadow 0.2s;
            border: 2px solid transparent;
        }
        .scenario-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
            border-color: #667eea;
        }
        .scenario-card h2 {
            font-size: 20px;
            color: #1f2937;
            margin-bottom: 8px;
        }
        .scenario-card p {
            font-size: 14px;
            color: #6b7280;
            margin-bottom: 12px;
        }
        .risk {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .risk.medium { background: #fef3c7; color: #d97706; }
        .risk.low { background: #d1fae5; color: #059669; }
        .footer {
            margin-top: 30px;
            font-size: 12px;
            color: #9ca3af;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 OpenHands SRE Demo</h1>
        <p class="subtitle">Select a scenario to simulate an incident</p>
        
        <div class="scenarios">
            <a href="/service1" class="scenario-card">
                <h2>🔧 Service 1</h2>
                <p>Production health-api instance</p>
                <span class="risk medium">MEDIUM RISK</span>
            </a>
            
            <a href="/service2" class="scenario-card">
                <h2>🔧 Service 2</h2>
                <p>Production auth-api instance</p>
                <span class="risk low">LOW RISK</span>
            </a>
            
            <a href="/service3" class="scenario-card">
                <h2>🔧 Service 3</h2>
                <p>Production config-api instance</p>
                <span class="risk medium">MEDIUM RISK</span>
            </a>
        </div>
        
        <p class="footer">Each scenario can be broken and fixed independently</p>
    </div>
</body>
</html>'''


def wants_json() -> bool:
    """Check if client wants JSON (curl, API) vs HTML (browser)."""
    accept = request.headers.get('Accept', '')
    user_agent = request.headers.get('User-Agent', '').lower()
    if 'text/html' in accept and 'curl' not in user_agent:
        return False
    if 'application/json' in accept:
        return True
    if 'curl' in user_agent:
        return True
    return False


@app.route("/")
def index():
    """Index page - show all scenarios or legacy single-scenario mode."""
    if SCENARIO:
        # Legacy mode: single scenario via env var
        return healthcheck_scenario(SCENARIO)
    # Multi-scenario mode: show index
    if wants_json():
        return jsonify({
            "status": "ok",
            "services": {
                "/service1": "health-api",
                "/service2": "auth-api", 
                "/service3": "config-api"
            }
        }), 200
    return render_index()


@app.route("/service1")
def service1():
    """Service 1 - stale lockfile scenario."""
    return healthcheck_scenario("stale_lockfile")


@app.route("/service2")
def service2():
    """Service 2 - readiness probe failure scenario."""
    return healthcheck_scenario("readiness_probe_fail")


@app.route("/service3")
def service3():
    """Service 3 - bad environment config scenario."""
    return healthcheck_scenario("bad_env_config")


# Keep old routes for backward compatibility
@app.route("/lockfile")
def lockfile_scenario():
    return healthcheck_scenario("stale_lockfile")


@app.route("/ready")
def ready_scenario():
    return healthcheck_scenario("readiness_probe_fail")


@app.route("/config")
def config_scenario():
    return healthcheck_scenario("bad_env_config")


def healthcheck_scenario(scenario: str):
    """Check health for a specific scenario."""
    if scenario == "stale_lockfile":
        if os.path.exists(LOCKFILE):
            if wants_json():
                return jsonify({"status": "error", "reason": f"stale lockfile present at {LOCKFILE}"}), 500
            return render_html(
                "error",
                "Service Unavailable",
                "The service failed to start due to a stale lockfile from a previous crash.",
                f"🔒 Lockfile: {LOCKFILE}",
                scenario
            ), 500
        if wants_json():
            return jsonify({"status": "ok", "scenario": scenario}), 200
        return render_html(
            "ok",
            "Service Running",
            "All systems operational. The health-api is responding normally.",
            scenario=scenario
        ), 200

    if scenario == "bad_env_config":
        if not os.getenv(REQUIRED_ENV):
            if wants_json():
                return jsonify({"status": "error", "reason": f"missing required env {REQUIRED_ENV}"}), 500
            return render_html(
                "error",
                "Configuration Error",
                "Required environment variable is not set.",
                f"Missing: {REQUIRED_ENV}",
                scenario
            ), 500
        if wants_json():
            return jsonify({"status": "ok", "scenario": scenario}), 200
        return render_html("ok", "Service Running", "Configuration loaded successfully.", scenario=scenario)

    if scenario == "readiness_probe_fail":
        if not os.path.exists(READY_FILE):
            if wants_json():
                return jsonify({"status": "error", "reason": f"missing readiness file {READY_FILE}"}), 500
            return render_html(
                "error",
                "Not Ready",
                "The service is starting but not yet ready to accept traffic.",
                f"Waiting for: {READY_FILE}",
                scenario
            ), 500
        if wants_json():
            return jsonify({"status": "ok", "scenario": scenario}), 200
        return render_html("ok", "Service Ready", "Readiness probe passing. Service is ready for traffic.", scenario=scenario)

    if wants_json():
        return jsonify({"status": "error", "reason": f"unknown scenario {scenario}"}), 500
    return render_html("error", "Unknown Error", f"Unknown scenario: {scenario}", scenario=scenario)


if __name__ == "__main__":
    bind_port = 5001 if SCENARIO == "port_mismatch" else 5000
    app.run(host="0.0.0.0", port=bind_port)
