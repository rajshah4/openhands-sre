from __future__ import annotations

import os
import random
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

import sys

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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RunManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self.state: dict[str, Any] = self._initial_state()

    def _initial_state(self) -> dict[str, Any]:
        return {
            "run_id": None,
            "status": "idle",
            "started_at": None,
            "finished_at": None,
            "config": {},
            "summary": {
                "total": 0,
                "queue": 0,
                "active": 0,
                "completed": 0,
                "fixed": 0,
                "failed": 0,
                "avg_steps": 0.0,
                "avg_latency_s": 0.0,
                "throughput_per_s": 0.0,
            },
            "queue": [],
            "active": [],
            "completed": [],
            "logs": [],
            "env": runtime_env_status(),
            "error": None,
        }

    def _log(self, message: str) -> None:
        with self._lock:
            self.state["logs"].append({"ts": time.time(), "message": message})
            self.state["logs"] = self.state["logs"][-200:]

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                **self.state,
                "queue": list(self.state["queue"]),
                "active": list(self.state["active"]),
                "completed": list(self.state["completed"]),
                "logs": list(self.state["logs"]),
                "summary": dict(self.state["summary"]),
                "config": dict(self.state["config"]),
                "env": dict(self.state["env"]),
            }

    def stop(self) -> bool:
        with self._lock:
            running = self.state["status"] == "running"
        if running:
            self._cancel.set()
            self._log("Stop requested by user")
            return True
        return False

    def start(self, payload: dict[str, Any]) -> tuple[bool, str]:
        with self._lock:
            if self.state["status"] == "running":
                return False, "A run is already in progress"

            self._cancel.clear()
            self.state = self._initial_state()
            self.state["status"] = "running"
            self.state["run_id"] = time.strftime("%Y%m%d-%H%M%S")
            self.state["started_at"] = time.time()
            self.state["config"] = payload
            self.state["env"] = runtime_env_status()

        self._thread = threading.Thread(target=self._run_job, args=(payload,), daemon=True)
        self._thread.start()
        return True, "started"

    def _update_metrics(self, now: float) -> None:
        completed = self.state["completed"]
        fixed = sum(1 for r in completed if r["service_up"])
        failed = len(completed) - fixed
        avg_steps = (sum(r["step_count"] for r in completed) / len(completed)) if completed else 0.0
        avg_latency = (sum(r["latency_s"] for r in completed) / len(completed)) if completed else 0.0
        started_at = self.state["started_at"] or now
        elapsed = max(0.001, now - started_at)
        throughput = len(completed) / elapsed

        self.state["summary"] = {
            "total": self.state["summary"]["total"],
            "queue": len(self.state["queue"]),
            "active": len(self.state["active"]),
            "completed": len(completed),
            "fixed": fixed,
            "failed": failed,
            "avg_steps": round(avg_steps, 2),
            "avg_latency_s": round(avg_latency, 2),
            "throughput_per_s": round(throughput, 2),
        }

    def _run_job(self, payload: dict[str, Any]) -> None:
        try:
            load_project_env(payload.get("env_file"))

            simulate = bool(payload.get("simulate", payload.get("mock", True)))
            if not simulate:
                ensure_real_call_requirements()

            mode = payload.get("mode", "optimized")
            optimizer = payload.get("optimizer", "gepa")
            incidents = int(payload.get("incidents", 20))
            concurrency = int(payload.get("concurrency", 4))
            seed = int(payload.get("seed", 7))
            runtime_image = payload.get("runtime_image", "openhands-gepa-sre-target:latest")
            model = payload.get("model") or None
            allow_fallback = bool(payload.get("allow_fallback", False))
            max_security_risk = payload.get("max_security_risk", "HIGH")
            require_confirmation_for_risk = payload.get("require_confirmation_for_risk")
            auto_confirm = bool(payload.get("auto_confirm", False))
            trace_url_template = payload.get("trace_url_template") or None
            simulate_latency_ms = int(payload.get("simulate_latency_ms", payload.get("mock_latency_ms", 0)))
            target_url = payload.get("target_url", "http://127.0.0.1:15000")
            target_container = payload.get("target_container")
            remote_host = payload.get("remote_host") or os.getenv("OPENHANDS_REMOTE_HOST")
            remote_working_dir = payload.get("remote_working_dir", "/workspace")
            remote_api_key = payload.get("remote_api_key") or os.getenv("OPENHANDS_REMOTE_API_KEY")
            allow_local_workspace = bool(payload.get("allow_local_workspace", False))

            if not simulate and not remote_host and not allow_local_workspace:
                raise RuntimeError(
                    "Real mode requires remote_host (OpenHands agent server) unless allow_local_workspace=true."
                )
            if not simulate and concurrency > 1:
                self._log("Real mode concurrency capped to 1 for reliability (set simulate=true for fan-out demos).")
                concurrency = 1

            random.seed(seed)

            runner = OpenHandsSRE(
                runtime_image=runtime_image,
                model=model,
                use_mock_if_sdk_missing=allow_fallback,
                remote_host=remote_host,
                remote_working_dir=remote_working_dir,
                remote_api_key=remote_api_key,
                allow_local_workspace=allow_local_workspace,
                real_max_retries=int(payload.get("real_max_retries", 2)),
                real_run_timeout_s=int(payload.get("real_run_timeout_s", 180)),
            )

            examples = load_examples()
            if mode == "baseline":
                strategy_hint = BASELINE_HINT
                strategy_score = None
            elif optimizer == "manual":
                strategy_hint = OPTIMIZED_HINT
                strategy_score = None
            else:
                strategy_hint, strategy_score, _ = get_best_hint(optimizer, runner, examples)

            with self._lock:
                self.state["config"]["strategy_hint"] = strategy_hint
                self.state["config"]["strategy_score"] = strategy_score

            items: list[Incident] = []
            for i in range(1, incidents + 1):
                items.append(
                    Incident(
                        id=f"inc-{i:04d}",
                        scenario_id=random.choice(list(SCENARIO_ERRORS.keys())),
                        severity=random.choices(SEVERITIES, weights=SEVERITY_WEIGHTS, k=1)[0],
                        created_at=time.time(),
                    )
                )
            items.sort(key=lambda x: SEVERITY_RANK[x.severity], reverse=True)

            run_id = self.state["run_id"]

            with self._lock:
                self.state["queue"] = [it.to_dict() for it in items]
                self.state["summary"]["total"] = incidents
                self._update_metrics(time.time())

            self._log(f"Run {run_id} started: mode={mode} optimizer={optimizer} incidents={incidents} concurrency={concurrency}")

            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                active: dict[Future, tuple[int, Incident]] = {}
                queue = items[:]
                worker_ids = list(range(1, concurrency + 1))
                next_worker = 0

                def submit_next(worker_id: int | None = None) -> None:
                    nonlocal next_worker
                    if not queue:
                        return
                    if worker_id is None:
                        worker_id = worker_ids[next_worker % len(worker_ids)]
                        next_worker += 1

                    inc = queue.pop(0)
                    trace_key = f"{run_id}:{inc.id}"

                    def task() -> dict[str, Any]:
                        started = time.time()
                        if simulate and simulate_latency_ms > 0:
                            time.sleep(simulate_latency_ms / 1000.0)

                        result = runner.forward(
                            strategy_hint=strategy_hint,
                            error_report=SCENARIO_ERRORS[inc.scenario_id],
                            scenario_id=inc.scenario_id,
                            stream=False,
                            dry_run=simulate,
                            max_security_risk=max_security_risk,
                            require_confirmation_for_risk=require_confirmation_for_risk,
                            auto_confirm=auto_confirm,
                            target_url=target_url,
                            target_container=target_container,
                            trace_key=trace_key,
                        )
                        ended = time.time()

                        trace_url = None
                        if trace_url_template:
                            trace_url = (
                                trace_url_template
                                .replace("{run_id}", str(run_id))
                                .replace("{incident_id}", inc.id)
                                .replace("{trace_key}", trace_key)
                                .replace("{trace_id}", "")
                            )

                        return {
                            "incident_id": inc.id,
                            "worker_id": worker_id,
                            "scenario_id": inc.scenario_id,
                            "severity": inc.severity,
                            "service_up": bool(result.get("service_up", False)),
                            "step_count": int(result.get("step_count", 999)),
                            "latency_s": round(ended - started, 2),
                            "max_security_risk_seen": str(result.get("max_security_risk_seen", "UNKNOWN")),
                            "fallback_used": bool(result.get("fallback_used", False)),
                            "trace_key": trace_key,
                            "trace_url": trace_url,
                        }

                    fut = pool.submit(task)
                    active[fut] = (worker_id, inc)

                while queue and len(active) < concurrency:
                    submit_next()

                while active:
                    if self._cancel.is_set():
                        self._log("Cancellation signal received")
                        break

                    done, _ = wait(active.keys(), timeout=0.2, return_when=FIRST_COMPLETED)
                    for fut in done:
                        worker_id, inc = active.pop(fut)
                        try:
                            result_row = fut.result()
                        except Exception as exc:
                            result_row = {
                                "incident_id": inc.id,
                                "worker_id": worker_id,
                                "scenario_id": inc.scenario_id,
                                "severity": inc.severity,
                                "service_up": False,
                                "step_count": 999,
                                "latency_s": 0.0,
                                "max_security_risk_seen": "UNKNOWN",
                                "fallback_used": False,
                                "trace_key": f"{run_id}:{inc.id}",
                                "trace_url": None,
                                "error": str(exc),
                            }

                        with self._lock:
                            self.state["completed"].append(result_row)
                            self.state["completed"] = self.state["completed"][-400:]
                            self.state["queue"] = [q.to_dict() for q in queue]
                            active_items = [
                                {
                                    "worker_id": wid,
                                    "incident_id": item.id,
                                    "scenario_id": item.scenario_id,
                                    "severity": item.severity,
                                }
                                for (_f, (wid, item)) in active.items()
                            ]
                            self.state["active"] = active_items
                            self._update_metrics(time.time())

                        status = "FIXED" if result_row["service_up"] else "FAILED"
                        self._log(
                            f"worker-{worker_id} {inc.id} {inc.scenario_id} {status} "
                            f"steps={result_row['step_count']} risk={result_row['max_security_risk_seen']}"
                        )

                        if not self._cancel.is_set() and queue:
                            submit_next(worker_id)

                    with self._lock:
                        self.state["queue"] = [q.to_dict() for q in queue]
                        active_items = [
                            {
                                "worker_id": wid,
                                "incident_id": item.id,
                                "scenario_id": item.scenario_id,
                                "severity": item.severity,
                            }
                            for (_f, (wid, item)) in active.items()
                        ]
                        self.state["active"] = active_items
                        self._update_metrics(time.time())

            with self._lock:
                self.state["finished_at"] = time.time()
                self.state["status"] = "cancelled" if self._cancel.is_set() else "completed"
                self._update_metrics(time.time())

            self._log(f"Run {run_id} {self.state['status']}")

        except Exception as exc:
            with self._lock:
                self.state["status"] = "failed"
                self.state["error"] = str(exc)
                self.state["finished_at"] = time.time()
            self._log(f"Run failed: {exc}")


app = Flask(__name__, template_folder="templates")
manager = RunManager()


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/api/state")
def api_state() -> Any:
    return jsonify(manager.get_state())


@app.post("/api/run")
def api_run() -> Any:
    payload = request.get_json(silent=True) or {}
    ok, msg = manager.start(payload)
    code = 200 if ok else 409
    return jsonify({"ok": ok, "message": msg, "state": manager.get_state()}), code


@app.post("/api/stop")
def api_stop() -> Any:
    stopped = manager.stop()
    return jsonify({"ok": stopped, "state": manager.get_state()})


if __name__ == "__main__":
    print("Web demo: http://127.0.0.1:8008")
    app.run(host="127.0.0.1", port=8008, debug=False)
