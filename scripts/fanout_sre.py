from __future__ import annotations

import argparse
import random
import sys
import threading
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


@dataclass
class Incident:
    id: str
    scenario_id: str
    severity: str
    created_at: float


def severity_weight(sev: str) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(sev, 1)


def choose_hint(mode: str, optimizer: str, runner: OpenHandsSRE, examples: list[dict[str, Any]]) -> tuple[str, float | None]:
    if mode == "baseline":
        return BASELINE_HINT, None
    if optimizer == "manual":
        return OPTIMIZED_HINT, None
    hint, score, _ = get_best_hint(optimizer, runner, examples)
    return hint, score


def generate_incident(idx: int) -> Incident:
    scenario_id = random.choice(list(SCENARIO_ERRORS.keys()))
    severity = random.choices(
        population=["critical", "high", "medium", "low"],
        weights=[1, 2, 4, 3],
        k=1,
    )[0]
    return Incident(
        id=f"inc-{idx:05d}",
        scenario_id=scenario_id,
        severity=severity,
        created_at=time.time(),
    )


def process_incident(
    incident: Incident,
    runner: OpenHandsSRE,
    hint: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    started_at = time.time()
    result = runner.forward(
        strategy_hint=hint,
        error_report=SCENARIO_ERRORS[incident.scenario_id],
        scenario_id=incident.scenario_id,
        stream=False,
        dry_run=args.simulate,
        max_security_risk=args.max_security_risk,
        require_confirmation_for_risk=args.require_confirmation_for_risk,
        auto_confirm=args.auto_confirm,
    )
    ended_at = time.time()

    return {
        "incident_id": incident.id,
        "scenario_id": incident.scenario_id,
        "severity": incident.severity,
        "created_at": incident.created_at,
        "started_at": started_at,
        "ended_at": ended_at,
        "latency_s": ended_at - started_at,
        "service_up": bool(result.get("service_up", False)),
        "step_count": int(result.get("step_count", 999)),
        "fallback_used": bool(result.get("fallback_used", False)),
        "max_security_risk_seen": str(result.get("max_security_risk_seen", "UNKNOWN")),
        "confirmation_required": bool(result.get("confirmation_required", False)),
        "tool_actions": list(result.get("tool_actions", [])),
    }


def print_scorecard(completed: list[dict[str, Any]], active: int, generated: int, started_at: float) -> None:
    elapsed = max(0.001, time.time() - started_at)
    fixed = sum(1 for r in completed if r["service_up"])
    failed = len(completed) - fixed
    avg_steps = (sum(r["step_count"] for r in completed) / len(completed)) if completed else 0.0
    avg_latency = (sum(r["latency_s"] for r in completed) / len(completed)) if completed else 0.0
    fallback_count = sum(1 for r in completed if r["fallback_used"])
    confirmation_count = sum(1 for r in completed if r["confirmation_required"])

    throughput = len(completed) / elapsed

    scenario_counts: dict[str, int] = {}
    for r in completed:
        scenario_counts[r["scenario_id"]] = scenario_counts.get(r["scenario_id"], 0) + 1

    print("\n=== Fan-Out Scorecard ===")
    print(f"generated={generated} active={active} completed={len(completed)}")
    print(f"fixed={fixed} failed={failed} fallback_used={fallback_count}")
    print(f"avg_steps={avg_steps:.2f} avg_latency_s={avg_latency:.2f} throughput_incidents_per_s={throughput:.2f}")
    print(f"confirmation_required_count={confirmation_count}")
    print("scenario_mix=", scenario_counts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Parallel fan-out SRE remediation demo")
    parser.add_argument("--mode", choices=["baseline", "optimized"], default="optimized")
    parser.add_argument("--optimizer", choices=["manual", "gepa", "iterative"], default="gepa")
    parser.add_argument("--incidents", type=int, default=20, help="Total incidents for one-shot mode")
    parser.add_argument("--concurrency", type=int, default=6, help="Worker concurrency")
    parser.add_argument("--continuous", action="store_true", help="Generate incidents continuously")
    parser.add_argument("--duration-s", type=int, default=60, help="Duration for continuous mode")
    parser.add_argument("--arrival-rate", type=float, default=2.0, help="Incidents per second in continuous mode")
    parser.add_argument("--scorecard-interval-s", type=float, default=5.0, help="Scorecard print interval")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for reproducible incident mixes")
    parser.add_argument("--runtime-image", default="openhands-gepa-sre-target:latest")
    parser.add_argument("--simulate", action="store_true", help="Use simulation execution path")
    parser.add_argument("--mock", dest="simulate", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--model", default=None)
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--allow-fallback", action="store_true")
    parser.add_argument("--max-security-risk", choices=["LOW", "MEDIUM", "HIGH"], default="HIGH")
    parser.add_argument("--require-confirmation-for-risk", choices=["LOW", "MEDIUM", "HIGH"], default=None)
    parser.add_argument("--auto-confirm", action="store_true")
    args = parser.parse_args()
    random.seed(args.seed)

    env_path = load_project_env(args.env_file)
    env = runtime_env_status()

    print(f"[env] loaded from: {env_path}")
    print(
        "[env] openai_api_key=%s lmnr_project_api_key=%s lamini_api_key=%s"
        % (env["openai_api_key"], env["lmnr_project_api_key"], env["lamini_api_key"])
    )

    if not args.simulate:
        ensure_real_call_requirements()

    runner = OpenHandsSRE(
        runtime_image=args.runtime_image,
        model=args.model,
        use_mock_if_sdk_missing=args.allow_fallback,
    )

    examples = load_examples()
    hint, score = choose_hint(args.mode, args.optimizer, runner, examples)
    print(f"[strategy] mode={args.mode} optimizer={args.optimizer} score={None if score is None else round(score,3)}")
    print(f"[policy] max_security_risk={args.max_security_risk} require_confirmation_for_risk={args.require_confirmation_for_risk} auto_confirm={args.auto_confirm}")
    print(f"[fanout] concurrency={args.concurrency} continuous={args.continuous} seed={args.seed}")

    completed: list[dict[str, Any]] = []
    completed_lock = threading.Lock()
    last_scorecard_print = 0.0

    start = time.time()
    next_incident_id = 1

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        active: dict[Future, Incident] = {}

        def submit_one(incident: Incident) -> None:
            fut = ex.submit(process_incident, incident, runner, hint, args)
            active[fut] = incident

        if args.continuous:
            end_time = start + args.duration_s
            next_arrival = start
            while time.time() < end_time or active:
                now = time.time()
                while now >= next_arrival and now < end_time:
                    incident = generate_incident(next_incident_id)
                    next_incident_id += 1
                    submit_one(incident)
                    next_arrival += 1.0 / max(0.1, args.arrival_rate)
                    now = time.time()

                if not active:
                    time.sleep(0.05)
                    continue

                done, _ = wait(active.keys(), timeout=0.2, return_when=FIRST_COMPLETED)
                for fut in done:
                    inc = active.pop(fut)
                    try:
                        res = fut.result()
                    except Exception as exc:
                        res = {
                            "incident_id": inc.id,
                            "scenario_id": inc.scenario_id,
                            "severity": inc.severity,
                            "created_at": inc.created_at,
                            "started_at": time.time(),
                            "ended_at": time.time(),
                            "latency_s": 0.0,
                            "service_up": False,
                            "step_count": 999,
                            "fallback_used": False,
                            "max_security_risk_seen": "UNKNOWN",
                            "confirmation_required": False,
                            "tool_actions": [],
                            "error": str(exc),
                        }
                    with completed_lock:
                        completed.append(res)
                now = time.time()
                if (now - last_scorecard_print) >= max(0.1, args.scorecard_interval_s):
                    print_scorecard(completed, len(active), next_incident_id - 1, start)
                    last_scorecard_print = now

        else:
            total = args.incidents
            queue = [generate_incident(i + 1) for i in range(total)]
            queue.sort(key=lambda x: severity_weight(x.severity), reverse=True)

            while queue and len(active) < args.concurrency:
                submit_one(queue.pop(0))

            while active:
                done, _ = wait(active.keys(), return_when=FIRST_COMPLETED)
                for fut in done:
                    inc = active.pop(fut)
                    try:
                        res = fut.result()
                    except Exception as exc:
                        res = {
                            "incident_id": inc.id,
                            "scenario_id": inc.scenario_id,
                            "severity": inc.severity,
                            "created_at": inc.created_at,
                            "started_at": time.time(),
                            "ended_at": time.time(),
                            "latency_s": 0.0,
                            "service_up": False,
                            "step_count": 999,
                            "fallback_used": False,
                            "max_security_risk_seen": "UNKNOWN",
                            "confirmation_required": False,
                            "tool_actions": [],
                            "error": str(exc),
                        }
                    with completed_lock:
                        completed.append(res)
                    if queue:
                        submit_one(queue.pop(0))

                if len(completed) % max(1, args.concurrency) == 0 or not active:
                    print_scorecard(completed, len(active), args.incidents, start)

    print("\n=== Final Results ===")
    print_scorecard(completed, 0, (next_incident_id - 1) if args.continuous else args.incidents, start)


if __name__ == "__main__":
    main()
