from __future__ import annotations

import json
import os
import subprocess
from typing import Any


def _curl_code(url: str) -> str:
    proc = subprocess.run(
        ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", url],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return "000"
    return (proc.stdout or "000").strip()


def remediate(
    target_url: str = "http://127.0.0.1:15000",
    target_container: str | None = "openhands-gepa-demo",
    ready_path: str = "/tmp/ready.flag",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "target_url": target_url,
        "target_container": target_container,
        "ready_path": ready_path,
        "pre_http_code": _curl_code(target_url),
    }
    if target_container:
        touch = subprocess.run(
            ["docker", "exec", target_container, "sh", "-lc", f"touch {ready_path}"],
            capture_output=True,
            text=True,
            check=False,
        )
        result["scope"] = "container"
        result["touch_returncode"] = touch.returncode
        result["touch_error"] = (touch.stderr or "").strip()
    else:
        touch = subprocess.run(["sh", "-lc", f"touch {ready_path}"], capture_output=True, text=True, check=False)
        result["scope"] = "host"
        result["touch_returncode"] = touch.returncode
        result["touch_error"] = (touch.stderr or "").strip()

    result["post_http_code"] = _curl_code(target_url)
    result["fixed"] = result["post_http_code"] == "200"
    return result


if __name__ == "__main__":
    url = os.getenv("TARGET_URL", "http://127.0.0.1:15000")
    container = os.getenv("TARGET_CONTAINER", "openhands-gepa-demo")
    if container.strip().lower() in {"", "none", "null"}:
        container = None
    print(json.dumps(remediate(target_url=url, target_container=container), indent=2))
