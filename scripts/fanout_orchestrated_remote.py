from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openhands_driver import OpenHandsSRE
from openhands_driver.runtime_env import ensure_real_call_requirements, load_project_env, runtime_env_status
from optimize import get_best_hint, load_examples
from run_demo import BASELINE_HINT, OPTIMIZED_HINT, SCENARIO_ERRORS


SEVERITIES = ["critical", "high", "medium", "low"]
SEVERITY_WEIGHTS = [1, 2, 4, 3]
SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}


@dataclass
class Incident:
    id: str
    scenario_id: str
    severity: str
    created_at: float


@dataclass
class Worker:
    id: int
    agent_container: str
    agent_port: int
    remote_host: str


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=check)


def _docker_ok() -> bool:
    proc = _run(["docker", "version"], check=False)
    return proc.returncode == 0


def _rm_container(name: str) -> None:
    _run(["docker", "rm", "-f", name], check=False)


def _wait_http(url: str, timeout_s: float = 15.0) -> bool:
    end = time.time() + timeout_s
    while time.time() < end:
        proc = _run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url], check=False)
        if proc.returncode == 0 and proc.stdout.strip() in {"200", "401", "403", "404"}:
            return True
        time.sleep(0.4)
    return False


def _worker_exec(worker: Worker, script: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(["docker", "exec", worker.agent_container, "bash", "-lc", script], check=check)


def choose_hint(mode: str, optimizer: str, runner: OpenHandsSRE, examples: list[dict[str, Any]]) -> tuple[str, float | None]:
    if mode == "baseline":
        return BASELINE_HINT, None
    if optimizer == "manual":
        return OPTIMIZED_HINT, None
    hint, score, _ = get_best_hint(optimizer, runner, examples)
    return hint, score


def _worker_env_args() -> list[str]:
    keys = [
        "OPENAI_API_KEY",
        "LMNR_PROJECT_API_KEY",
        "LMNR_BASE_URL",
        "LMNR_HTTP_ENDPOINT",
        "LAMINI_API_KEY",
        "LAMINAR_API_KEY",
    ]
    args: list[str] = []
    for k in keys:
        v = os.getenv(k)
        if v:
            args.extend(["-e", f"{k}={v}"])
    return args


def create_workers(args: argparse.Namespace, run_id: str) -> list[Worker]:
    workers: list[Worker] = []
    for idx in range(1, args.concurrency + 1):
        port = args.agent_port_start + idx - 1
        name = f"{run_id}-agent-w{idx}"
        _rm_container(name)

        cmd = [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "-p",
            f"{port}:8000",
            "-v",
            f"{ROOT}:/workspace",
            *_worker_env_args(),
            args.agent_image,
        ]
        proc = _run(cmd, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to start agent server {name}: {proc.stderr or proc.stdout}")

        host = f"http://127.0.0.1:{port}"
        if not _wait_http(host, timeout_s=25):
            raise RuntimeError(f"Agent server {name} did not become healthy at {host}")

        workers.append(Worker(id=idx, agent_container=name, agent_port=port, remote_host=host))

    return workers


def bootstrap_worker(worker: Worker) -> None:
    script = """
set -e
python3 -m pip install --user -q flask >/tmp/sre_bootstrap.log 2>&1 || python -m pip install --user -q flask >/tmp/sre_bootstrap.log 2>&1 || true
""".strip()
    _worker_exec(worker, script, check=False)


def _incident_runtime_dir(incident: Incident) -> str:
    return f"/tmp/sre_incident_{incident.id}"


def prepare_incident(worker: Worker, incident: Incident) -> tuple[str, str]:
    runtime_dir = _incident_runtime_dir(incident)
    scenario = incident.scenario_id

    script = f"""
set -e
if [ -f /tmp/sre_app.pid ]; then
  kill $(cat /tmp/sre_app.pid) >/dev/null 2>&1 || true
fi
rm -f /tmp/sre_app.pid /tmp/sre_app.log /tmp/service.lock /tmp/ready.flag
rm -rf '{runtime_dir}'
mkdir -p '{runtime_dir}'
cp -R /workspace/target_service/. '{runtime_dir}'/
case '{scenario}' in
  stale_lockfile)
    touch /tmp/service.lock
    ;;
  readiness_probe_fail)
    rm -f /tmp/ready.flag
    ;;
  bad_env_config)
    :
    ;;
  port_mismatch)
    :
    ;;
  *)
    :
    ;;
esac
env -u REQUIRED_API_KEY SCENARIO='{scenario}' nohup python3 '{runtime_dir}/app.py' >/tmp/sre_app.log 2>&1 &
echo $! >/tmp/sre_app.pid
""".strip()

    proc = _worker_exec(worker, script, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to prepare incident {incident.id} on worker-{worker.id} rc={proc.returncode}: {proc.stderr or proc.stdout}")

    target_url = "http://127.0.0.1:5000"
    return runtime_dir, target_url


def verify_incident(worker: Worker) -> tuple[bool, str]:
    probe = _worker_exec(
        worker,
        "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5000",
        check=False,
    )
    code = (probe.stdout or "").strip()
    return code == "200", code


def cleanup_incident(worker: Worker) -> None:
    script = """
if [ -f /tmp/sre_app.pid ]; then
  kill $(cat /tmp/sre_app.pid) >/dev/null 2>&1 || true
fi
rm -f /tmp/sre_app.pid
""".strip()
    _worker_exec(worker, script, check=False)


def generate_incidents(total: int, seed: int) -> list[Incident]:
    random.seed(seed)
    rows: list[Incident] = []
    for i in range(1, total + 1):
        rows.append(
            Incident(
                id=f"inc-{i:04d}",
                scenario_id=random.choice(list(SCENARIO_ERRORS.keys())),
                severity=random.choices(SEVERITIES, weights=SEVERITY_WEIGHTS, k=1)[0],
                created_at=time.time(),
            )
        )
    rows.sort(key=lambda r: SEVERITY_RANK[r.severity], reverse=True)
    return rows


def solve_incident(
    incident: Incident,
    worker: Worker,
    args: argparse.Namespace,
    strategy_hint: str,
    run_id: str,
) -> dict[str, Any]:
    started = time.time()
    runtime_dir = ""

    try:
        if not args.simulate:
            runtime_dir, target_url = prepare_incident(worker, incident)
        else:
            target_url = "http://127.0.0.1:15000"

        runner = OpenHandsSRE(
            runtime_image=args.runtime_image,
            model=args.model,
            use_mock_if_sdk_missing=args.allow_fallback,
            remote_host=worker.remote_host if not args.simulate else None,
            remote_working_dir=args.remote_working_dir,
            allow_local_workspace=args.simulate,
            real_max_retries=args.real_max_retries,
            real_run_timeout_s=args.real_run_timeout_s,
        )

        error_report = SCENARIO_ERRORS[incident.scenario_id]
        if runtime_dir:
            error_report += (
                f" Active service runtime is at {runtime_dir} in this worker container. "
                "Diagnose/fix inside this runtime and verify with curl localhost:5000."
            )

        result = runner.forward(
            strategy_hint=strategy_hint,
            error_report=error_report,
            scenario_id=incident.scenario_id,
            stream=False,
            dry_run=args.simulate,
            max_security_risk=args.max_security_risk,
            require_confirmation_for_risk=args.require_confirmation_for_risk,
            auto_confirm=args.auto_confirm,
            target_url=target_url,
            target_container=None,
            trace_key=f"{run_id}:{incident.id}",
        )

        if args.simulate:
            verified_up = bool(result.get("service_up", False))
            verify_code = "200" if verified_up else "500"
        else:
            verified_up, verify_code = verify_incident(worker)

        return {
            "incident_id": incident.id,
            "scenario_id": incident.scenario_id,
            "severity": incident.severity,
            "worker_id": worker.id,
            "agent_host": worker.remote_host,
            "runtime_dir": runtime_dir,
            "target_url": target_url,
            "service_up": verified_up,
            "verify_code": verify_code,
            "step_count": int(result.get("step_count", 999)),
            "fallback_used": bool(result.get("fallback_used", False)),
            "max_security_risk_seen": str(result.get("max_security_risk_seen", "UNKNOWN")),
            "error": result.get("fallback_reason"),
            "latency_s": round(time.time() - started, 2),
        }
    finally:
        if not args.keep_artifacts and not args.simulate:
            cleanup_incident(worker)


def print_summary(results: list[dict[str, Any]], started: float, score: float | None) -> None:
    fixed = sum(1 for x in results if x["service_up"])
    elapsed = max(0.001, time.time() - started)
    avg_steps = sum(x["step_count"] for x in results) / max(1, len(results))
    avg_latency = sum(x["latency_s"] for x in results) / max(1, len(results))

    print("\n=== Orchestrated Fan-Out Summary ===")
    print(f"completed={len(results)} fixed={fixed} failed={len(results) - fixed}")
    print(f"optimizer_score={None if score is None else round(score, 3)}")
    print(
        f"avg_steps={avg_steps:.2f} avg_latency_s={avg_latency:.2f} "
        f"throughput_incidents_per_s={len(results)/elapsed:.2f}"
    )

    for row in results:
        status = "FIXED" if row["service_up"] else "FAILED"
        print(
            f"{row['incident_id']} worker={row['worker_id']} scenario={row['scenario_id']} "
            f"{status} verify={row['verify_code']} steps={row['step_count']} "
            f"latency_s={row['latency_s']:.2f} agent={row['agent_host']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote orchestrator + worker-agent fan-out demo")
    parser.add_argument("--mode", choices=["baseline", "optimized"], default="optimized")
    parser.add_argument("--optimizer", choices=["manual", "gepa", "iterative"], default="gepa")
    parser.add_argument("--incidents", type=int, default=8)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--runtime-image", default="openhands-gepa-sre-target:latest")
    parser.add_argument("--agent-image", default="ghcr.io/openhands/agent-server:1.11.5-python")
    parser.add_argument("--agent-port-start", type=int, default=3300)
    parser.add_argument("--remote-working-dir", default="/workspace")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--mock", dest="simulate", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--keep-artifacts", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--allow-fallback", action="store_true")
    parser.add_argument("--real-max-retries", type=int, default=2)
    parser.add_argument("--real-run-timeout-s", type=int, default=180)
    parser.add_argument("--max-security-risk", choices=["LOW", "MEDIUM", "HIGH"], default="HIGH")
    parser.add_argument("--require-confirmation-for-risk", choices=["LOW", "MEDIUM", "HIGH"], default=None)
    parser.add_argument("--auto-confirm", action="store_true")
    args = parser.parse_args()

    env_path = load_project_env(args.env_file)
    status = runtime_env_status()
    print(f"[env] loaded from: {env_path}")
    print(
        "[env] openai_api_key=%s lmnr_project_api_key=%s lamini_api_key=%s"
        % (status["openai_api_key"], status["lmnr_project_api_key"], status["lamini_api_key"])
    )

    if not args.simulate:
        ensure_real_call_requirements()
        if not _docker_ok():
            raise SystemExit("Docker is required for orchestrated remote mode.")

    run_id = f"oh-orch-{time.strftime('%Y%m%d-%H%M%S')}"
    incidents = generate_incidents(args.incidents, args.seed)
    workers: list[Worker] = []
    results: list[dict[str, Any]] = []
    started = time.time()

    try:
        if args.simulate:
            workers = [
                Worker(id=i, agent_container=f"sim-w{i}", agent_port=0, remote_host=f"simulate://worker-{i}")
                for i in range(1, args.concurrency + 1)
            ]
        else:
            print(f"[setup] starting {args.concurrency} agent-server workers from {args.agent_image}")
            workers = create_workers(args, run_id)
            for w in workers:
                bootstrap_worker(w)

        hint_runner = OpenHandsSRE(runtime_image=args.runtime_image, use_mock_if_sdk_missing=True)
        strategy_hint, score = choose_hint(args.mode, args.optimizer, hint_runner, load_examples())
        print(f"[strategy] mode={args.mode} optimizer={args.optimizer} score={None if score is None else round(score, 3)}")
        print("[intake]")
        for inc in incidents:
            print(f"  - {inc.id} severity={inc.severity} scenario={inc.scenario_id}")

        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            active: dict[Future, tuple[Worker, Incident]] = {}
            queue = incidents[:]
            next_worker_idx = 0

            def submit(worker: Worker | None = None) -> None:
                nonlocal next_worker_idx
                if not queue:
                    return
                if worker is None:
                    worker = workers[next_worker_idx % len(workers)]
                    next_worker_idx += 1
                inc = queue.pop(0)
                fut = pool.submit(solve_incident, inc, worker, args, strategy_hint, run_id)
                active[fut] = (worker, inc)

            while queue and len(active) < args.concurrency:
                submit()

            while active:
                done, _ = wait(active.keys(), return_when=FIRST_COMPLETED)
                for fut in done:
                    worker, inc = active.pop(fut)
                    try:
                        res = fut.result()
                    except Exception as exc:
                        print(f"[worker-{worker.id}] exception: {exc}")
                        res = {
                            "incident_id": inc.id,
                            "scenario_id": inc.scenario_id,
                            "severity": inc.severity,
                            "worker_id": worker.id,
                            "agent_host": worker.remote_host,
                            "runtime_dir": "",
                            "target_url": "",
                            "service_up": False,
                            "verify_code": "ERR",
                            "step_count": 999,
                            "fallback_used": False,
                            "max_security_risk_seen": "UNKNOWN",
                            "error": str(exc),
                            "latency_s": 0.0,
                        }
                    results.append(res)
                    status_txt = "FIXED" if res["service_up"] else "FAILED"
                    print(
                        f"[worker-{worker.id}] {inc.id} {inc.scenario_id} {status_txt} "
                        f"verify={res['verify_code']} steps={res['step_count']} latency_s={res['latency_s']:.2f}"
                    )
                    if queue:
                        submit(worker)

        print_summary(results, started, score)

    finally:
        if workers and not args.keep_artifacts and not args.simulate:
            print("[teardown] stopping agent-server workers")
            for w in workers:
                _rm_container(w.agent_container)


if __name__ == "__main__":
    main()
