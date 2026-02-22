from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.benchmark_itbench_sample import map_itbench_to_demo_scenario


def _pick(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else None


def _short_status(row: dict[str, Any]) -> str:
    if row.get("status") == "queued":
        return "QUEUED"
    if row.get("status") == "running":
        return "RUNNING"
    if row.get("status") == "timeout":
        return "TIMEOUT"
    if row.get("status") in {"setup_failed", "failed"}:
        return "FAILED"
    if str(row.get("service_up", "")).lower() == "true":
        return "FIXED"
    return "DONE"


def _render_table(rows: list[dict[str, Any]]) -> str:
    headers = ["Incident", "Sandbox", "Status", "Steps"]
    data = []
    for row in rows:
        data.append(
            [
                str(row.get("incident_id", "-")),
                str(row.get("sandbox_id", "-")),
                _short_status(row),
                str(row.get("step_count", "-") if row.get("step_count") is not None else "-"),
            ]
        )
    widths = [len(h) for h in headers]
    for r in data:
        for i, c in enumerate(r):
            widths[i] = max(widths[i], len(c))

    def line(ch: str = "-") -> str:
        return "+" + "+".join(ch * (w + 2) for w in widths) + "+"

    out = [line("-")]
    out.append(
        "| "
        + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers)))
        + " |"
    )
    out.append(line("="))
    for r in data:
        out.append("| " + " | ".join(r[i].ljust(widths[i]) for i in range(len(headers))) + " |")
    out.append(line("-"))
    return "\n".join(out)


def _run_one(
    *,
    incident_id: str,
    sandbox_id: str,
    working_dir: str,
    mapped_scenario: str,
    runtime_image: str,
    remote_host: str,
    remote_api_key: str | None,
    model: str | None,
    simulate: bool,
    real_max_retries: int,
    real_run_timeout_s: int,
) -> dict[str, Any]:
    cmd = [
        "uv",
        "run",
        "python",
        "run_demo.py",
        "--mode",
        "optimized",
        "--strategy-source",
        "skills",
        "--scenario",
        mapped_scenario,
        "--runtime-image",
        runtime_image,
        "--remote-host",
        remote_host,
        "--remote-working-dir",
        working_dir,
        "--real-max-retries",
        str(real_max_retries),
        "--real-run-timeout-s",
        str(real_run_timeout_s),
        "--auto-confirm",
    ]
    if simulate:
        cmd.append("--simulate")
    if model:
        cmd.extend(["--model", model])
    if remote_api_key:
        cmd.extend(["--remote-api-key", remote_api_key])

    t0 = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    elapsed = round(time.time() - t0, 1)
    return {
        "incident_id": incident_id,
        "sandbox_id": sandbox_id,
        "working_dir": working_dir,
        "mapped_scenario": mapped_scenario,
        "status": "ok" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "elapsed_s": elapsed,
        "run_id": _pick(r"run_id:\s*(.+)", out),
        "service_up": _pick(r"service_up:\s*(.+)", out),
        "step_count": _pick(r"step_count:\s*(.+)", out),
        "fallback_used": _pick(r"fallback_used:\s*(.+)", out),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-incident isolation demo using per-incident remote workspaces")
    parser.add_argument("--training-data", default="training_data/atlas_sre_scenarios.json")
    parser.add_argument("--incidents", type=int, default=4)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--seed", type=int, default=33)
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--runtime-image", default="openhands-gepa-sre-target:latest")
    parser.add_argument("--remote-host", default="http://localhost:3000")
    parser.add_argument("--remote-api-key", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--workspace-root", default="/workspace/incidents")
    parser.add_argument("--real-max-retries", type=int, default=0)
    parser.add_argument("--real-run-timeout-s", type=int, default=120)
    parser.add_argument("--output", default="artifacts/runs/fanout_isolated.json")
    args = parser.parse_args()

    data_path = Path(args.training_data)
    if not data_path.exists():
        raise FileNotFoundError(f"training data not found: {data_path}")
    examples = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(examples, list) or not examples:
        raise RuntimeError(f"invalid/empty training data: {data_path}")

    random.seed(args.seed)
    random.shuffle(examples)
    selected = examples[: max(1, min(args.incidents, len(examples)))]
    incidents = []
    for i, ex in enumerate(selected, 1):
        sandbox_id = f"sandbox-{random.randint(0, 0xFFFF):04x}"
        incidents.append(
            {
                "incident_id": f"inc-{i:03d}",
                "sandbox_id": sandbox_id,
                "working_dir": f"{args.workspace_root}/{sandbox_id}",
                "mapped_scenario": map_itbench_to_demo_scenario(ex),
            }
        )

    started = time.time()
    rows: list[dict[str, Any]] = [
        {
            "incident_id": it["incident_id"],
            "sandbox_id": it["sandbox_id"],
            "working_dir": it["working_dir"],
            "mapped_scenario": it["mapped_scenario"],
            "status": "queued",
            "step_count": None,
        }
        for it in incidents
    ]
    print(_render_table(rows))

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        pending: dict[Future, int] = {}
        queue = list(enumerate(incidents))

        def submit(idx: int, item: dict[str, Any]) -> None:
            rows[idx]["status"] = "running"
            fut = pool.submit(
                _run_one,
                incident_id=item["incident_id"],
                sandbox_id=item["sandbox_id"],
                working_dir=item["working_dir"],
                mapped_scenario=item["mapped_scenario"],
                runtime_image=args.runtime_image,
                remote_host=args.remote_host,
                remote_api_key=args.remote_api_key,
                model=args.model,
                simulate=bool(args.simulate),
                real_max_retries=max(0, args.real_max_retries),
                real_run_timeout_s=max(30, args.real_run_timeout_s),
            )
            pending[fut] = idx

        while queue and len(pending) < max(1, args.concurrency):
            idx, item = queue.pop(0)
            submit(idx, item)

        while pending:
            done, _ = wait(pending.keys(), return_when=FIRST_COMPLETED)
            for fut in done:
                idx = pending.pop(fut)
                try:
                    result = fut.result()
                except Exception as exc:  # pragma: no cover
                    result = {
                        "status": "failed",
                        "returncode": -1,
                        "elapsed_s": 0.0,
                        "run_id": None,
                        "service_up": "False",
                        "step_count": None,
                        "fallback_used": None,
                        "error": str(exc),
                    }
                rows[idx].update(result)

                if queue:
                    nidx, nitem = queue.pop(0)
                    submit(nidx, nitem)

                print(_render_table(rows))

    ok_rows = [r for r in rows if r.get("status") == "ok"]
    fixed = sum(1 for r in ok_rows if str(r.get("service_up", "")).lower() == "true")
    summary = {
        "total": len(rows),
        "ok": len(ok_rows),
        "fixed": fixed,
        "failed": sum(1 for r in rows if r.get("status") == "failed"),
        "elapsed_s": round(time.time() - started, 2),
        "fixed_rate_ok_pct": round((fixed / len(ok_rows) * 100.0), 2) if ok_rows else 0.0,
        "mode": "simulate" if args.simulate else "real",
        "remote_host": args.remote_host,
        "concurrency": int(args.concurrency),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": summary,
        "rows": rows,
        "training_data": str(data_path),
        "seed": int(args.seed),
        "workspace_root": args.workspace_root,
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("SUMMARY", json.dumps(summary, ensure_ascii=True))
    print("OUTPUT", output_path)


if __name__ == "__main__":
    main()
