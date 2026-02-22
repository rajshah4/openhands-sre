from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMAGE = "openhands-gepa-sre-target:latest"
RISK_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


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


def proposed_action_for_scenario(scenario: str, container_name: str) -> str:
    if scenario == "stale_lockfile":
        return f"docker exec {container_name} rm -f /tmp/service.lock"
    if scenario == "readiness_probe_fail":
        return f"docker exec {container_name} sh -lc 'touch /tmp/ready.flag'"
    if scenario == "port_mismatch":
        return f"docker exec {container_name} sh -lc 'ss -lntp || netstat -lnt || lsof -iTCP -sTCP:LISTEN -n -P'"
    return f"docker exec {container_name} sh -lc 'echo no-op'"


def run_intervention_prompt(default_command: str) -> int:
    if not sys.stdin.isatty():
        raise SystemExit("Interactive mode requires a TTY stdin.")

    print("\n=== Live Intervention Mode ===")
    print("Agent proposes:", default_command)
    print()
    print("[y]es / [n]o / [e]dit > ", end="", flush=True)
    choice = (input().strip().lower() or "n")

    if choice.startswith("n"):
        print("Rejected command; skipping manual intervention step.")
        return 0

    command = default_command
    if choice.startswith("e"):
        print("Modified command: ", end="", flush=True)
        edited = input().strip()
        if not edited:
            print("Empty edit; skipping manual intervention step.")
            return 0
        command = edited
        print("Executing modified command...")
    else:
        print("Executing approved command...")

    try:
        parsed = shlex.split(command)
        if not parsed:
            print("No command parsed; skipping.")
            return 0
        proc = subprocess.run(parsed, cwd=ROOT, text=True, check=False)
        return proc.returncode
    except ValueError:
        proc = subprocess.run(command, cwd=ROOT, shell=True, text=True, check=False)
        return proc.returncode


def _risk_value(level: str) -> int:
    return RISK_ORDER.get(level.upper(), 0)


def run_security_gates_demo() -> int:
    actions = [
        {"command": "rm -rf /tmp/*", "risk": "HIGH"},
        {"command": "rm -f /tmp/service.lock", "risk": "LOW"},
    ]

    cases = [
        {
            "title": "Case 1: max_security_risk=MEDIUM",
            "max_security_risk": "MEDIUM",
            "require_confirmation_for_risk": None,
            "auto_confirm": False,
        },
        {
            "title": "Case 2: require_confirmation_for_risk=MEDIUM (auto_confirm=False)",
            "max_security_risk": "HIGH",
            "require_confirmation_for_risk": "MEDIUM",
            "auto_confirm": False,
        },
        {
            "title": "Case 3: require_confirmation_for_risk=MEDIUM (auto_confirm=True)",
            "max_security_risk": "HIGH",
            "require_confirmation_for_risk": "MEDIUM",
            "auto_confirm": True,
        },
    ]

    print("=== Security Gates Demo ===")
    print("This demo simulates OpenHands security policy behavior using representative actions.")
    print("No destructive commands are executed.")
    print()

    for case in cases:
        print(case["title"])
        print(
            "policy: max_security_risk=%s require_confirmation_for_risk=%s auto_confirm=%s"
            % (
                case["max_security_risk"],
                case["require_confirmation_for_risk"],
                case["auto_confirm"],
            )
        )

        for action in actions:
            cmd = action["command"]
            risk = action["risk"]
            blocked_reason = ""

            if _risk_value(risk) > _risk_value(str(case["max_security_risk"])):
                blocked_reason = (
                    f"BLOCKED: Action exceeds policy "
                    f"(max_security_risk={case['max_security_risk']})"
                )
            elif case["require_confirmation_for_risk"] is not None and (
                _risk_value(risk) >= _risk_value(str(case["require_confirmation_for_risk"]))
            ):
                if not bool(case["auto_confirm"]):
                    blocked_reason = (
                        f"BLOCKED: Confirmation required for risk >= "
                        f"{case['require_confirmation_for_risk']}"
                    )

            print(f"Agent Action: {cmd}")
            print(f"Security Risk: {risk}")
            if blocked_reason:
                print(blocked_reason)
            else:
                print("ALLOWED")
            print()
        print("-" * 72)

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Easy start wrapper for the OpenHands SRE demo")
    parser.add_argument("--mode", choices=["baseline", "optimized"], default="optimized")
    parser.add_argument("--strategy-source", choices=["skills", "optimizer", "manual", "auto"], default="skills")
    parser.add_argument("--optimizer", choices=["manual", "gepa", "iterative"], default="manual")
    parser.add_argument("--scenario", choices=["stale_lockfile", "readiness_probe_fail", "port_mismatch"], default="stale_lockfile")
    parser.add_argument("--port", type=int, default=15000)
    parser.add_argument("--container-name", default="openhands-gepa-demo")
    parser.add_argument("--runtime-image", default=IMAGE)
    parser.add_argument("--model", default=None)
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--remote-host", default=None, help="OpenHands agent-server host for remote sandbox execution")
    parser.add_argument("--remote-working-dir", default="/workspace", help="Remote workspace directory when using --remote-host")
    parser.add_argument("--remote-api-key", default=None, help="Optional OpenHands remote API key")
    parser.add_argument("--allow-fallback", action="store_true")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--allow-local-workspace", action="store_true", help="Allow local workspace real run (host execution)")
    parser.add_argument("--mock", dest="simulate", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--keep-container", action="store_true")
    parser.add_argument("--interactive", action="store_true", help="Pause for human approve/reject/edit on a proposed remediation command")
    parser.add_argument("--vnc", action="store_true", help="Observer mode: print remote host/workspace for VNC/VSCode session tracking")
    parser.add_argument("--demo-security-gates", action="store_true", help="Run a safety-gates demonstration and exit")
    parser.add_argument("--max-security-risk", choices=["LOW", "MEDIUM", "HIGH"], default="HIGH")
    parser.add_argument("--require-confirmation-for-risk", choices=["LOW", "MEDIUM", "HIGH"], default=None)
    parser.add_argument("--auto-confirm", action="store_true")
    args = parser.parse_args()

    if args.demo_security_gates:
        raise SystemExit(run_security_gates_demo())

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

    if args.interactive:
        proposed = proposed_action_for_scenario(args.scenario, args.container_name)
        code = run_intervention_prompt(proposed)
        print(f"[interactive] intervention step exit={code}")

    if args.vnc:
        if args.remote_host:
            print("[observer] VNC/VSCode observer mode enabled")
            print(f"[observer] remote_host={args.remote_host}")
            print(f"[observer] remote_working_dir={args.remote_working_dir}")
            print("[observer] open the agent-server UI/session view to watch or intervene live.")
        else:
            print("[observer] --vnc requested but --remote-host is not set; running without remote observer mode.")

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
    if args.remote_host:
        cmd.extend(["--remote-host", args.remote_host])
    if args.remote_working_dir:
        cmd.extend(["--remote-working-dir", args.remote_working_dir])
    if args.remote_api_key:
        cmd.extend(["--remote-api-key", args.remote_api_key])
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
