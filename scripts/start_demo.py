from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMAGE = "openhands-gepa-sre-target:latest"


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=check)


def docker_available() -> bool:
    try:
        run(["docker", "version"])
        return True
    except Exception:
        return False


def container_exists(name: str) -> bool:
    proc = run(["docker", "ps", "-a", "--format", "{{.Names}}"], check=False)
    if proc.returncode != 0:
        return False
    return name in (proc.stdout or "")


def rm_container(name: str) -> None:
    run(["docker", "rm", "-f", name], check=False)


def wait_for_endpoint(url: str, timeout_s: float = 15.0) -> str:
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        proc = run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url], check=False)
        last = (proc.stdout or "").strip()
        if last in {"200", "500", "403"}:
            return last
        time.sleep(0.4)
    return last


def main() -> None:
    parser = argparse.ArgumentParser(description="Easy start wrapper for the OpenHands SRE demo")
    parser.add_argument("--mode", choices=["baseline", "optimized"], default="optimized")
    parser.add_argument("--strategy-source", choices=["skills", "optimizer", "manual", "auto"], default="skills")
    parser.add_argument("--optimizer", choices=["manual", "gepa", "iterative"], default="manual")
    parser.add_argument("--scenario", choices=["stale_lockfile", "bad_env_config", "readiness_probe_fail", "port_mismatch"], default="stale_lockfile")
    parser.add_argument("--port", type=int, default=15000)
    parser.add_argument("--container-name", default="openhands-gepa-demo")
    parser.add_argument("--runtime-image", default=IMAGE)
    parser.add_argument("--model", default=None)
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--allow-fallback", action="store_true")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--allow-local-workspace", action="store_true", help="Allow local workspace real run (host execution)")
    parser.add_argument("--mock", dest="simulate", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--keep-container", action="store_true")
    parser.add_argument("--max-security-risk", choices=["LOW", "MEDIUM", "HIGH"], default="HIGH")
    parser.add_argument("--require-confirmation-for-risk", choices=["LOW", "MEDIUM", "HIGH"], default=None)
    parser.add_argument("--auto-confirm", action="store_true")
    args = parser.parse_args()

    if not docker_available():
        raise SystemExit("Docker is not available. Start Docker Desktop and retry.")

    if not args.skip_build:
        print(f"[setup] building image {args.runtime_image} ...")
        proc = run(["docker", "build", "-t", args.runtime_image, "target_service"], check=False)
        if proc.returncode != 0:
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
            raise SystemExit(proc.returncode)

    if container_exists(args.container_name):
        print(f"[setup] removing existing container {args.container_name}")
        rm_container(args.container_name)

    print(f"[setup] starting container {args.container_name} on 127.0.0.1:{args.port}")
    proc = run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            args.container_name,
            "-p",
            f"{args.port}:5000",
            "-e",
            f"SCENARIO={args.scenario}",
            args.runtime_image,
        ],
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)

    target_url = f"http://127.0.0.1:{args.port}"
    status = wait_for_endpoint(target_url)
    print(f"[setup] initial healthcheck {target_url} -> HTTP {status or 'unknown'}")

    cmd = [
        sys.executable,
        "run_demo.py",
        "--mode",
        args.mode,
        "--strategy-source",
        args.strategy_source,
        "--optimizer",
        args.optimizer,
        "--scenario",
        args.scenario,
        "--runtime-image",
        args.runtime_image,
        "--target-url",
        target_url,
        "--target-container",
        args.container_name,
        "--max-security-risk",
        args.max_security_risk,
    ]

    if args.model:
        cmd.extend(["--model", args.model])
    if args.env_file:
        cmd.extend(["--env-file", args.env_file])
    if args.allow_fallback:
        cmd.append("--allow-fallback")
    if args.allow_local_workspace:
        cmd.append("--allow-local-workspace")
    if args.simulate:
        cmd.append("--simulate")
    if args.require_confirmation_for_risk:
        cmd.extend(["--require-confirmation-for-risk", args.require_confirmation_for_risk])
    if args.auto_confirm:
        cmd.append("--auto-confirm")

    print("[run]", " ".join(cmd))
    code = subprocess.call(cmd, cwd=ROOT)

    if not args.keep_container:
        print(f"[teardown] removing container {args.container_name}")
        rm_container(args.container_name)

    raise SystemExit(code)


if __name__ == "__main__":
    main()
