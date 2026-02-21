from __future__ import annotations

import argparse
import random
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


def choose_hint(mode: str, optimizer: str, runner: OpenHandsSRE, examples: list[dict[str, Any]]) -> tuple[str, float | None]:
    if mode == "baseline":
        return BASELINE_HINT, None
    if optimizer == "manual":
        return OPTIMIZED_HINT, None
    hint, score, _ = get_best_hint(optimizer, runner, examples)
    return hint, score


def generate_incidents(count: int) -> list[Incident]:
    items: list[Incident] = []
    for i in range(1, count + 1):
        items.append(
            Incident(
                id=f"inc-{i:04d}",
                scenario_id=random.choice(list(SCENARIO_ERRORS.keys())),
                severity=random.choices(SEVERITIES, weights=SEVERITY_WEIGHTS, k=1)[0],
                created_at=time.time(),
            )
        )
    items.sort(key=lambda x: SEVERITY_RANK[x.severity], reverse=True)
    return items


def solve_incident(
    incident: Incident,
    worker_id: int,
    runner: OpenHandsSRE,
    hint: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    started = time.time()
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
    ended = time.time()

    return {
        "incident_id": incident.id,
        "worker_id": worker_id,
        "scenario_id": incident.scenario_id,
        "severity": incident.severity,
        "service_up": bool(result.get("service_up", False)),
        "step_count": int(result.get("step_count", 999)),
        "latency_s": ended - started,
        "fallback_used": bool(result.get("fallback_used", False)),
        "max_security_risk_seen": str(result.get("max_security_risk_seen", "UNKNOWN")),
        "tool_actions": list(result.get("tool_actions", [])),
    }


def print_header(args: argparse.Namespace, strategy_hint: str, score: float | None) -> None:
    print("\n" + "=" * 84)
    print("OpenHands Fan-Out SRE Demo")
    print("=" * 84)
    print(f"mode={args.mode} optimizer={args.optimizer} simulate={args.simulate}")
    print(f"concurrency={args.concurrency} incidents={args.incidents} seed={args.seed}")
    print(f"optimizer_score={None if score is None else round(score, 3)}")
    print(f"max_security_risk={args.max_security_risk} require_confirmation_for_risk={args.require_confirmation_for_risk}")
    print("strategy_hint:")
    print(strategy_hint)


def print_intake(incidents: list[Incident]) -> None:
    print("\n[controller] incident intake (sorted by severity):")
    for inc in incidents:
        print(f"  - {inc.id} severity={inc.severity:8s} scenario={inc.scenario_id}")


def print_result_line(res: dict[str, Any]) -> None:
    status = "FIXED" if res["service_up"] else "FAILED"
    print(
        f"[worker-{res['worker_id']}] {res['incident_id']} {res['scenario_id']} "
        f"severity={res['severity']} -> {status} "
        f"steps={res['step_count']} latency_s={res['latency_s']:.2f} risk={res['max_security_risk_seen']}"
    )


def print_summary(results: list[dict[str, Any]], started: float) -> None:
    elapsed = max(0.001, time.time() - started)
    fixed = sum(1 for r in results if r["service_up"])
    failed = len(results) - fixed
    avg_steps = sum(r["step_count"] for r in results) / len(results)
    avg_latency = sum(r["latency_s"] for r in results) / len(results)
    throughput = len(results) / elapsed
    fallback_count = sum(1 for r in results if r["fallback_used"])

    scenario_counts: dict[str, int] = {}
    for r in results:
        scenario_counts[r["scenario_id"]] = scenario_counts.get(r["scenario_id"], 0) + 1

    by_worker: dict[int, int] = {}
    for r in results:
        by_worker[r["worker_id"]] = by_worker.get(r["worker_id"], 0) + 1

    slowest = sorted(results, key=lambda r: r["latency_s"], reverse=True)[:3]

    print("\n" + "=" * 84)
    print("Final Scorecard")
    print("=" * 84)
    print(f"completed={len(results)} fixed={fixed} failed={failed} fallback_used={fallback_count}")
    print(f"avg_steps={avg_steps:.2f} avg_latency_s={avg_latency:.2f} throughput_incidents_per_s={throughput:.2f}")
    print(f"scenario_mix={scenario_counts}")
    print(f"worker_load={by_worker}")
    print("top3_slowest_incidents:")
    for r in slowest:
        print(
            f"  - {r['incident_id']} scenario={r['scenario_id']} latency_s={r['latency_s']:.2f} steps={r['step_count']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage-friendly OpenHands fan-out SRE demo")
    parser.add_argument("--mode", choices=["baseline", "optimized"], default="optimized")
    parser.add_argument("--optimizer", choices=["manual", "gepa", "iterative"], default="gepa")
    parser.add_argument("--incidents", type=int, default=12)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--runtime-image", default="openhands-gepa-sre-target:latest")
    parser.add_argument("--simulate", action="store_true")
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
    strategy_hint, score = choose_hint(args.mode, args.optimizer, runner, examples)

    print_header(args, strategy_hint, score)

    incidents = generate_incidents(args.incidents)
    print_intake(incidents)

    started = time.time()
    results: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        active: dict[Future, tuple[int, Incident]] = {}
        queue = incidents[:]

        worker_cycle = list(range(1, args.concurrency + 1))
        next_worker = 0

        while queue and len(active) < args.concurrency:
            incident = queue.pop(0)
            worker_id = worker_cycle[next_worker % len(worker_cycle)]
            next_worker += 1
            print(f"[controller] assigned {incident.id} ({incident.severity}) -> worker-{worker_id}")
            future = pool.submit(solve_incident, incident, worker_id, runner, strategy_hint, args)
            active[future] = (worker_id, incident)

        while active:
            done, _ = wait(active.keys(), return_when=FIRST_COMPLETED)
            for fut in done:
                worker_id, incident = active.pop(fut)
                try:
                    res = fut.result()
                except Exception as exc:
                    res = {
                        "incident_id": incident.id,
                        "worker_id": worker_id,
                        "scenario_id": incident.scenario_id,
                        "severity": incident.severity,
                        "service_up": False,
                        "step_count": 999,
                        "latency_s": 0.0,
                        "fallback_used": False,
                        "max_security_risk_seen": "UNKNOWN",
                        "tool_actions": [],
                        "error": str(exc),
                    }
                results.append(res)
                print_result_line(res)

                if queue:
                    nxt = queue.pop(0)
                    print(f"[controller] assigned {nxt.id} ({nxt.severity}) -> worker-{worker_id}")
                    future = pool.submit(solve_incident, nxt, worker_id, runner, strategy_hint, args)
                    active[future] = (worker_id, nxt)

    print_summary(results, started)


if __name__ == "__main__":
    main()
