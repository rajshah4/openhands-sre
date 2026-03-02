#!/usr/bin/env python3
"""
MCP Server for OpenHands SRE Demo

Exposes tools to diagnose and fix services in the demo Docker container.
This bridges OpenHands Cloud to local infrastructure execution.

Run with: 
    uv run python mcp_server/server.py

The server runs on port 8080 by default.
Expose with: tailscale funnel 8080
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings


def _log_tool(name: str):
    """Log MCP tool invocation with timestamp."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f">>> [{ts}] MCP TOOL CALLED: {name}", flush=True)

# Lock down to only this container
CONTAINER_NAME = "openhands-gepa-demo"
LOCAL_URL = "http://127.0.0.1:15000"
PORT = 8080

# Base path for reverse proxy (e.g., "/mcp" when behind Tailscale Funnel)
# This rewrites SSE endpoint URLs so MCP clients can find /messages/
BASE_PATH = os.getenv("MCP_BASE_PATH", "/mcp")

# Disable DNS rebinding protection to allow Tailscale Funnel access
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False
)

mcp = FastMCP("sre-demo", transport_security=transport_security)


def _run_in_container(cmd: list[str]) -> dict[str, Any]:
    """Execute a command inside the demo container."""
    full_cmd = ["docker", "exec", CONTAINER_NAME] + cmd
    result = subprocess.run(full_cmd, capture_output=True, text=True)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def _check_service(path: str) -> dict[str, Any]:
    """Check HTTP status of a service endpoint."""
    result = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"{LOCAL_URL}{path}"],
        capture_output=True,
        text=True,
    )
    http_code = result.stdout.strip()
    return {
        "path": path,
        "http_code": http_code,
        "healthy": http_code == "200",
    }


@mcp.tool()
def diagnose_service1() -> str:
    """
    Diagnose service1 (stale lockfile scenario).
    Checks if /tmp/service.lock exists and the HTTP status.
    """
    _log_tool("diagnose_service1")
    lock_check = _run_in_container(["ls", "-la", "/tmp/service.lock"])
    http_check = _check_service("/service1")
    
    lock_exists = lock_check["returncode"] == 0
    
    result = {
        "service": "service1",
        "scenario": "stale_lockfile",
        "http_status": http_check["http_code"],
        "healthy": http_check["healthy"],
        "lock_file_exists": lock_exists,
        "diagnosis": "Stale lockfile present - needs removal" if lock_exists else "No lockfile found",
        "recommended_action": "fix_service1" if lock_exists else "No action needed",
        "next_step": "IMPORTANT: Call the fix_service1 tool NOW to remove the lockfile. This is MEDIUM risk and auto-approved per AGENTS.md." if lock_exists else "Service is healthy.",
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def diagnose_service2() -> str:
    """
    Diagnose service2 (readiness probe scenario).
    Checks if /tmp/ready.flag exists and the HTTP status.
    """
    _log_tool("diagnose_service2")
    flag_check = _run_in_container(["ls", "-la", "/tmp/ready.flag"])
    http_check = _check_service("/service2")
    
    flag_exists = flag_check["returncode"] == 0
    
    result = {
        "service": "service2",
        "scenario": "readiness_probe_fail",
        "http_status": http_check["http_code"],
        "healthy": http_check["healthy"],
        "ready_flag_exists": flag_exists,
        "diagnosis": "Ready flag missing - service not ready" if not flag_exists else "Ready flag present",
        "recommended_action": "fix_service2" if not flag_exists else "No action needed",
        "next_step": "IMPORTANT: Call the fix_service2 tool NOW to create the readiness flag. This is LOW risk." if not flag_exists else "Service is healthy.",
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def diagnose_service3() -> str:
    """
    Diagnose service3 (bad env config scenario).
    Checks if REQUIRED_API_KEY is set and the HTTP status.
    """
    _log_tool("diagnose_service3")
    env_check = _run_in_container(["sh", "-c", "echo $REQUIRED_API_KEY"])
    http_check = _check_service("/service3")
    
    env_set = bool(env_check["stdout"].strip())
    
    result = {
        "service": "service3",
        "scenario": "bad_env_config",
        "http_status": http_check["http_code"],
        "healthy": http_check["healthy"],
        "required_api_key_set": env_set,
        "diagnosis": "REQUIRED_API_KEY not set" if not env_set else "Environment configured correctly",
        "recommended_action": "fix_service3" if not env_set else "No action needed",
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def fix_service1() -> str:
    """
    Fix service1 by removing the stale lockfile.
    Risk level: MEDIUM (removes a temp file)
    """
    _log_tool("fix_service1")
    # Pre-check
    pre_http = _check_service("/service1")
    
    # Execute fix
    rm_result = _run_in_container(["rm", "-f", "/tmp/service.lock"])
    
    # Post-check
    post_http = _check_service("/service1")
    
    result = {
        "service": "service1",
        "action": "rm -f /tmp/service.lock",
        "risk_level": "MEDIUM",
        "pre_http_status": pre_http["http_code"],
        "post_http_status": post_http["http_code"],
        "fixed": post_http["healthy"],
        "rm_returncode": rm_result["returncode"],
        "rm_error": rm_result["stderr"] if rm_result["stderr"] else None,
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def fix_service2() -> str:
    """
    Fix service2 by creating the readiness flag.
    Risk level: LOW (creates a flag file)
    """
    _log_tool("fix_service2")
    # Pre-check
    pre_http = _check_service("/service2")
    
    # Execute fix
    touch_result = _run_in_container(["touch", "/tmp/ready.flag"])
    
    # Post-check
    post_http = _check_service("/service2")
    
    result = {
        "service": "service2",
        "action": "touch /tmp/ready.flag",
        "risk_level": "LOW",
        "pre_http_status": pre_http["http_code"],
        "post_http_status": post_http["http_code"],
        "fixed": post_http["healthy"],
        "touch_returncode": touch_result["returncode"],
        "touch_error": touch_result["stderr"] if touch_result["stderr"] else None,
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def fix_service3() -> str:
    """
    Fix service3 - requires container restart with REQUIRED_API_KEY.
    Risk level: MEDIUM (container restart)
    
    NOTE: This cannot be done from inside the container. 
    Returns instructions for the operator to restart the container.
    """
    _log_tool("fix_service3")
    pre_http = _check_service("/service3")
    
    result = {
        "service": "service3",
        "action": "Container restart required with REQUIRED_API_KEY env var",
        "risk_level": "MEDIUM",
        "pre_http_status": pre_http["http_code"],
        "fixed": False,
        "manual_action_required": True,
        "instructions": (
            "Run the following command to fix service3:\n"
            "docker rm -f openhands-gepa-demo && "
            "docker run -d -p 15000:5000 -e REQUIRED_API_KEY=secret "
            "--name openhands-gepa-demo openhands-gepa-sre-target:latest"
        ),
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def get_all_service_status() -> str:
    """
    Get the current HTTP status of all services.
    Quick health check without detailed diagnosis.
    """
    _log_tool("get_all_service_status")
    result = {
        "service1": _check_service("/service1"),
        "service2": _check_service("/service2"),
        "service3": _check_service("/service3"),
    }
    return json.dumps(result, indent=2)


class BasePathMiddleware:
    """ASGI middleware for reverse proxy subpath support (e.g., /mcp).

    Handles two directions:
    - Outbound: Rewrites SSE endpoint paths /messages/ → /mcp/messages/
      so clients behind the proxy resolve the correct POST URL.
    - Inbound: Strips /mcp prefix from incoming requests so /mcp/messages/
      reaches the /messages/ handler (needed for direct local connections).
    """

    def __init__(self, app, base_path: str):
        self.app = app
        self.base_path = base_path.rstrip("/")

    async def __call__(self, scope, receive, send):
        if not self.base_path:
            return await self.app(scope, receive, send)

        # Inbound: handle path rewriting for reverse proxy
        if scope["type"] == "http":
            path = scope.get("path", "")
            method = scope.get("method", "GET")
            if path.startswith(self.base_path + "/"):
                # Strip prefix: /mcp/messages/... → /messages/...
                scope = dict(scope)
                scope["path"] = path[len(self.base_path):]
            elif path == "/" and method in ("POST", "DELETE"):
                # Root POST/DELETE → route to streamable HTTP at /mcp
                # (Tailscale stripped /mcp, we add it back)
                scope = dict(scope)
                scope["path"] = self.base_path

        # Outbound: rewrite SSE data to include base path in messages URL
        async def rewrite_send(message):
            if message.get("type") == "http.response.body":
                body = message.get("body", b"")
                if body:
                    text = body.decode("utf-8", errors="replace")
                    if "/messages/" in text:
                        text = text.replace(
                            "/messages/",
                            f"{self.base_path}/messages/",
                        )
                        message = {**message, "body": text.encode("utf-8")}
            await send(message)

        await self.app(scope, receive, rewrite_send)


if __name__ == "__main__":
    # Run with uvicorn for HTTP access
    import uvicorn
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route, Mount

    print(f"Starting MCP Server on http://0.0.0.0:{PORT}")
    print(f"Base path: {BASE_PATH or '(none)'}")
    print(f"SSE endpoint: http://0.0.0.0:{PORT}/sse")
    print(f"Expose with: tailscale funnel {PORT}")
    print()
    print("Available tools:")
    print("  - diagnose_service1, diagnose_service2, diagnose_service3")
    print("  - fix_service1, fix_service2, fix_service3")
    print("  - get_all_service_status")
    print()

    # Use streamable HTTP app as primary (has proper lifespan/task group).
    # This handles POST/GET/DELETE at /mcp for the streamable HTTP transport.
    # OpenHands Cloud uses: https://host/mcp → Tailscale strips /mcp → arrives as /
    # The BasePathMiddleware rewrites incoming / back to /mcp for the handler.
    http_app = mcp.streamable_http_app()

    # Also get SSE app for backward compatibility
    sse_app = mcp.sse_app()

    async def health(request):
        return JSONResponse({
            "status": "ok",
            "server": "sre-demo",
            "transports": {"streamable_http": "/mcp", "sse": "/sse"},
            "tools": [
                "diagnose_service1", "diagnose_service2", "diagnose_service3",
                "fix_service1", "fix_service2", "fix_service3",
                "get_all_service_status",
            ],
        })

    # Add health and SSE routes to the streamable HTTP app
    http_app.routes.insert(0, Route("/", health))
    http_app.routes.append(Mount("/sse-transport", app=sse_app))

    app = http_app

    # Route SSE paths (/sse, /messages/) to SSE transport app
    class DualTransportApp:
        """Routes requests to SSE or streamable HTTP transport."""
        def __init__(self, primary, sse):
            self.primary = primary
            self.sse = sse

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                path = scope.get("path", "")
                if path == "/sse" or path.startswith("/messages"):
                    return await self.sse(scope, receive, send)
            return await self.primary(scope, receive, send)

    app = DualTransportApp(app, sse_app)

    # Apply base path middleware for reverse proxy support
    if BASE_PATH:
        app = BasePathMiddleware(app, BASE_PATH)

    uvicorn.run(app, host="0.0.0.0", port=PORT)
