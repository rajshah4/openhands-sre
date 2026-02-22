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
    lock_path: str = "/tmp/service.lock",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "target_url": target_url,
        "target_container": target_container,
        "lock_path": lock_path,
        "pre_http_code": _curl_code(target_url),
    }

    if target_container:
        rm = subprocess.run(
            ["docker", "exec", target_container, "rm", "-f", lock_path],
            capture_output=True,
            text=True,
            check=False,
        )
        result["scope"] = "container"
        result["remove_returncode"] = rm.returncode
        result["remove_error"] = (rm.stderr or "").strip()
    else:
        rm = subprocess.run(["rm", "-f", lock_path], capture_output=True, text=True, check=False)
        result["scope"] = "host"
        result["remove_returncode"] = rm.returncode
        result["remove_error"] = (rm.stderr or "").strip()

    result["post_http_code"] = _curl_code(target_url)
    result["fixed"] = result["post_http_code"] == "200"
    return result


if __name__ == "__main__":
    url = os.getenv("TARGET_URL", "http://127.0.0.1:15000")
    container = os.getenv("TARGET_CONTAINER", "openhands-gepa-demo")
    if container.strip().lower() in {"", "none", "null"}:
        container = None
    print(json.dumps(remediate(target_url=url, target_container=container), indent=2))
