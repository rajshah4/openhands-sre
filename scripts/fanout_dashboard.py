from __future__ import annotations

import argparse
import os
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

try:
    from lmnr import Laminar  # type: ignore
except Exception:
    Laminar = None

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


def render_trace_url(template: str | None, run_id: str, incident_id: str, trace_key: str, trace_id: str | None) -> str | None:
    if not template:
        return None
    if "{trace_id}" in template and not trace_id:
        return None
    try:
        return template.format(
            run_id=run_id,
            incident_id=incident_id,
            trace_key=trace_key,
            trace_id=(trace_id or ""),
        )
    except Exception:
        return None


def _run_with_optional_laminar_span(
    incident: Incident,
    run_id: str,
    runner: OpenHandsSRE,
    hint: str,
    args: argparse.Namespace,
    trace_key: str,
) -> tuple[dict[str, Any], str | None]:
    if Laminar is None or args.simulate:
        result = runner.forward(
            strategy_hint=hint,
            error_report=SCENARIO_ERRORS[incident.scenario_id],
            scenario_id=incident.scenario_id,
            stream=False,
            dry_run=args.simulate,
            max_security_risk=args.max_security_risk,
            require_confirmation_for_risk=args.require_confirmation_for_risk,
            auto_confirm=args.auto_confirm,
            trace_key=trace_key,
        )
        return result, None

    with Laminar.start_as_current_span(
        name="sre_incident",
        session_id=run_id,
        metadata={"incident_id": incident.id, "scenario_id": incident.scenario_id, "trace_key": trace_key},
    ):
        result = runner.forward(
            strategy_hint=hint,
            error_report=SCENARIO_ERRORS[incident.scenario_id],
            scenario_id=incident.scenario_id,
            stream=False,
            dry_run=args.simulate,
            max_security_risk=args.max_security_risk,
            require_confirmation_for_risk=args.require_confirmation_for_risk,
            auto_confirm=args.auto_confirm,
            trace_key=trace_key,
        )
        trace_uuid = Laminar.get_trace_id()
        trace_id = str(trace_uuid) if trace_uuid is not None else None
        return result, trace_id


def run_incident(
    incident: Incident,
    worker_id: int,
    run_id: str,
    runner: OpenHandsSRE,
    hint: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    started = time.time()
    trace_key = f"{run_id}:{incident.id}"
    result, trace_id = _run_with_optional_laminar_span(incident, run_id, runner, hint, args, trace_key)
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
        "trace_key": trace_key,
        "trace_id": trace_id,
        "trace_url": render_trace_url(args.trace_url_template, run_id, incident.id, trace_key, trace_id),
    }


def render_dashboard(
    mode: str,
    optimizer: str,
    score: float | None,
    started: float,
    total: int,
    queue: list[Incident],
    active_by_worker: dict[int, Incident],
    completed: list[dict[str, Any]],
    run_id: str,
) -> None:
    elapsed = max(0.001, time.time() - started)
    fixed = sum(1 for r in completed if r["service_up"])
    failed = len(completed) - fixed
    avg_steps = (sum(r["step_count"] for r in completed) / len(completed)) if completed else 0.0
    throughput = len(completed) / elapsed

    print("\033[2J\033[H", end="")
    print("=" * 94)
    print("OpenHands Fan-Out Dashboard")
    print("=" * 94)
    print(
        f"mode={mode} optimizer={optimizer} optimizer_score={None if score is None else round(score,3)} "
        f"elapsed_s={elapsed:.1f} run_id={run_id}"
    )
    print(
        f"total={total} queue={len(queue)} active={len(active_by_worker)} completed={len(completed)} "
        f"fixed={fixed} failed={failed} avg_steps={avg_steps:.2f} throughput={throughput:.2f}/s"
    )

    print("\nWorkers")
    print("worker | incident | severity | scenario")
    for worker_id in sorted(active_by_worker):
        inc = active_by_worker[worker_id]
        print(f"{worker_id:>6} | {inc.id:>8} | {inc.severity:>8} | {inc.scenario_id}")
    if not active_by_worker:
        print("(idle)")

    print("\nQueue (next 8)")
    if queue:
        for inc in queue[:8]:
            print(f"- {inc.id} [{inc.severity}] {inc.scenario_id}")
    else:
        print("(empty)")

    print("\nRecent Completions (last 8)")
    if completed:
        for r in completed[-8:]:
            status = "FIXED" if r["service_up"] else "FAILED"
            trace_suffix = f" trace={r['trace_key']}" if r.get("trace_key") else ""
            if r.get("trace_id"):
                trace_suffix += f" trace_id={r['trace_id']}"
            print(
                f"- {r['incident_id']} worker-{r['worker_id']} {status} "
                f"steps={r['step_count']} risk={r['max_security_risk_seen']} latency={r['latency_s']:.2f}s{trace_suffix}"
            )
    else:
        print("(none)")


def print_final(completed: list[dict[str, Any]], started: float, run_id: str, trace_url_template: str | None) -> None:
    elapsed = max(0.001, time.time() - started)
    fixed = sum(1 for r in completed if r["service_up"])
    failed = len(completed) - fixed
    avg_steps = sum(r["step_count"] for r in completed) / max(1, len(completed))
    avg_latency = sum(r["latency_s"] for r in completed) / max(1, len(completed))
    throughput = len(completed) / elapsed

    scenario_counts: dict[str, int] = {}
    for r in completed:
        scenario_counts[r["scenario_id"]] = scenario_counts.get(r["scenario_id"], 0) + 1

    print("\n" + "=" * 94)
    print("Dashboard Final Summary")
    print("=" * 94)
    print(f"run_id={run_id}")
    print(f"completed={len(completed)} fixed={fixed} failed={failed}")
    print(f"avg_steps={avg_steps:.2f} avg_latency_s={avg_latency:.2f} throughput_incidents_per_s={throughput:.2f}")
    print(f"scenario_mix={scenario_counts}")

    if trace_url_template:
        print("\nTrace Links")
        print("template:", trace_url_template)
        for r in completed[-8:]:
            if r.get("trace_url"):
                print(f"- {r['incident_id']}: {r['trace_url']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Single-screen dashboard for fan-out SRE demo")
    parser.add_argument("--mode", choices=["baseline", "optimized"], default="optimized")
    parser.add_argument("--optimizer", choices=["manual", "gepa", "iterative"], default="gepa")
    parser.add_argument("--incidents", type=int, default=12)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--refresh-s", type=float, default=0.5)
    parser.add_argument("--trace-url-template", default=os.getenv("TRACE_URL_TEMPLATE"))
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
    hint, score = choose_hint(args.mode, args.optimizer, runner, examples)

    queue = generate_incidents(args.incidents)
    started = time.time()
    run_id = time.strftime("%Y%m%d-%H%M%S")
    completed: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        active: dict[Future, tuple[int, Incident]] = {}
        active_by_worker: dict[int, Incident] = {}
        workers = list(range(1, args.concurrency + 1))
        next_worker = 0

        def assign_next(worker_id: int | None = None) -> None:
            nonlocal next_worker
            if not queue:
                return
            if worker_id is None:
                worker_id = workers[next_worker % len(workers)]
                next_worker += 1
            incident = queue.pop(0)
            future = pool.submit(run_incident, incident, worker_id, run_id, runner, hint, args)
            active[future] = (worker_id, incident)
            active_by_worker[worker_id] = incident

        while queue and len(active) < args.concurrency:
            assign_next()

        last_refresh = 0.0
        while active:
            done, _ = wait(active.keys(), timeout=0.2, return_when=FIRST_COMPLETED)

            for fut in done:
                worker_id, incident = active.pop(fut)
                active_by_worker.pop(worker_id, None)
                try:
                    res = fut.result()
                except Exception as exc:
                    trace_key = f"{run_id}:{incident.id}"
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
                        "trace_key": trace_key,
                        "trace_id": None,
                        "trace_url": render_trace_url(args.trace_url_template, run_id, incident.id, trace_key, None),
                        "error": str(exc),
                    }
                completed.append(res)
                assign_next(worker_id)

            now = time.time()
            if (now - last_refresh) >= max(0.1, args.refresh_s) or not active:
                render_dashboard(
                    mode=args.mode,
                    optimizer=args.optimizer,
                    score=score,
                    started=started,
                    total=args.incidents,
                    queue=queue,
                    active_by_worker=active_by_worker,
                    completed=completed,
                    run_id=run_id,
                )
                last_refresh = now

    print_final(completed, started, run_id, args.trace_url_template)


if __name__ == "__main__":
    main()
