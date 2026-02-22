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


def _container_file_state(container: str, path: str) -> dict[str, Any]:
    check = subprocess.run(
        ["docker", "exec", container, "sh", "-lc", f"test -f {path} && echo present || echo absent"],
        capture_output=True,
        text=True,
        check=False,
    )
    if check.returncode != 0:
        return {"present": None, "error": (check.stderr or check.stdout or "").strip()}
    state = (check.stdout or "").strip()
    return {"present": state == "present", "error": ""}


def _host_file_state(path: str) -> dict[str, Any]:
    return {"present": os.path.exists(path), "error": ""}


def diagnose(
    target_url: str = "http://127.0.0.1:15000",
    target_container: str | None = "openhands-gepa-demo",
    lock_path: str = "/tmp/service.lock",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "target_url": target_url,
        "target_container": target_container,
        "lock_path": lock_path,
        "http_code": _curl_code(target_url),
    }
    if target_container:
        file_state = _container_file_state(target_container, lock_path)
        result["scope"] = "container"
    else:
        file_state = _host_file_state(lock_path)
        result["scope"] = "host"
    result.update(file_state)
    result["is_stale_lockfile_candidate"] = result["http_code"] == "500" and bool(result.get("present"))
    return result


if __name__ == "__main__":
    url = os.getenv("TARGET_URL", "http://127.0.0.1:15000")
    container = os.getenv("TARGET_CONTAINER", "openhands-gepa-demo")
    if container.strip().lower() in {"", "none", "null"}:
        container = None
    print(json.dumps(diagnose(target_url=url, target_container=container), indent=2))
