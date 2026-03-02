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
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# Lock down to only this container
CONTAINER_NAME = "openhands-gepa-demo"
LOCAL_URL = "http://127.0.0.1:15000"
PORT = 8080

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
    print(">>> MCP TOOL CALLED: diagnose_service1", flush=True)
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
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def diagnose_service2() -> str:
    """
    Diagnose service2 (readiness probe scenario).
    Checks if /tmp/ready.flag exists and the HTTP status.
    """
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
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def diagnose_service3() -> str:
    """
    Diagnose service3 (bad env config scenario).
    Checks if REQUIRED_API_KEY is set and the HTTP status.
    """
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
    print(">>> MCP TOOL CALLED: fix_service1", flush=True)
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
    result = {
        "service1": _check_service("/service1"),
        "service2": _check_service("/service2"),
        "service3": _check_service("/service3"),
    }
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    # Run with uvicorn for HTTP access
    import uvicorn
    
    print(f"Starting MCP Server on http://0.0.0.0:{PORT}")
    print(f"SSE endpoint: http://0.0.0.0:{PORT}/sse")
    print(f"Expose with: tailscale funnel {PORT}")
    print()
    print("Available tools:")
    print("  - diagnose_service1, diagnose_service2, diagnose_service3")
    print("  - fix_service1, fix_service2, fix_service3")
    print("  - get_all_service_status")
    print()
    
    # Get the ASGI app from FastMCP and run directly
    # Note: FastMCP's DNS rebinding protection may reject non-localhost hosts
    # The middleware approach had timing issues with SSE, so running direct
    app = mcp.sse_app()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
