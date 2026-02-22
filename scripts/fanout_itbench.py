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

from openhands_driver import OpenHandsSRE
from run_demo import OPTIMIZED_HINT
from scripts.benchmark_itbench_sample import map_itbench_to_demo_scenario


def _pick(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else None


def _select_examples(examples: list[dict[str, Any]], sample_size: int, seed: int) -> list[dict[str, Any]]:
    rows = [dict(ex) for ex in examples]
    rnd = random.Random(seed)
    rnd.shuffle(rows)
    out: list[dict[str, Any]] = []
    for ex in rows:
        ex["_mapped_scenario"] = map_itbench_to_demo_scenario(ex)
        out.append(ex)
        if len(out) >= sample_size:
            break
    return out


def _run_real_incident(
    ex: dict[str, Any],
    index: int,
    runtime_image: str,
    base_port: int,
    container_prefix: str,
    run_timeout_s: int,
    subprocess_timeout_s: int,
    real_max_retries: int,
) -> dict[str, Any]:
    mapped = str(ex["_mapped_scenario"])
    source_id = str(ex.get("scenario_id", ""))
    container_name = f"{container_prefix}-{index}"
    port = base_port + index
    target_url = f"http://127.0.0.1:{port}"

    subprocess.run(["docker", "rm", "-f", container_name], check=False, capture_output=True, text=True)
    start = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "-e",
            f"SCENARIO={mapped}",
            "-p",
            f"{port}:5000",
            runtime_image,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if start.returncode != 0:
        return {
            "index": index,
            "source_scenario_id": source_id,
            "mapped_scenario": mapped,
            "status": "setup_failed",
            "error": (start.stderr or "").strip(),
        }

    time.sleep(2)
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
        mapped,
        "--target-url",
        target_url,
        "--target-container",
        container_name,
        "--allow-local-workspace",
        "--auto-confirm",
        "--real-max-retries",
        str(real_max_retries),
        "--real-run-timeout-s",
        str(run_timeout_s),
    ]

    t0 = time.time()
    status = "ok"
    returncode: int | str = 0
    output = ""
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=max(30, subprocess_timeout_s),
            check=False,
        )
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        returncode = proc.returncode
    except subprocess.TimeoutExpired as e:
        status = "timeout"
        returncode = "TIMEOUT"
        out = e.stdout.decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        output = f"{out}\n{err}"
        subprocess.run(["pkill", "-f", "run_demo.py --mode optimized --strategy-source skills"], check=False)

    elapsed = round(time.time() - t0, 1)
    subprocess.run(["docker", "rm", "-f", container_name], check=False, capture_output=True, text=True)
    return {
        "index": index,
        "source_scenario_id": source_id,
        "mapped_scenario": mapped,
        "status": status,
        "returncode": returncode,
        "elapsed_s": elapsed,
        "run_id": _pick(r"run_id:\s*(.+)", output),
        "service_up": _pick(r"service_up:\s*(.+)", output),
        "step_count": _pick(r"step_count:\s*(.+)", output),
        "fallback_used": _pick(r"fallback_used:\s*(.+)", output),
    }


def _run_simulated_incident(ex: dict[str, Any], index: int, runner: OpenHandsSRE) -> dict[str, Any]:
    mapped = str(ex["_mapped_scenario"])
    source_id = str(ex.get("scenario_id", ""))
    t0 = time.time()
    pred = runner.forward(
        strategy_hint=OPTIMIZED_HINT,
        error_report=str(ex.get("error_report", "")),
        scenario_id=mapped,
        dry_run=True,
        stream=False,
    )
    return {
        "index": index,
        "source_scenario_id": source_id,
        "mapped_scenario": mapped,
        "status": "ok",
        "returncode": 0,
        "elapsed_s": round(time.time() - t0, 2),
        "run_id": None,
        "service_up": str(bool(pred.get("service_up", False))),
        "step_count": str(int(pred.get("step_count", 999))),
        "fallback_used": str(bool(pred.get("fallback_used", False))),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal fan-out runner for ITBench-derived incidents")
    parser.add_argument("--training-data", default="training_data/atlas_sre_scenarios.json")
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--seed", type=int, default=21)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--runtime-image", default="openhands-gepa-sre-target:latest")
    parser.add_argument("--base-port", type=int, default=16000)
    parser.add_argument("--container-prefix", default="openhands-gepa-fanout")
    parser.add_argument("--run-timeout-s", type=int, default=90)
    parser.add_argument("--subprocess-timeout-s", type=int, default=190)
    parser.add_argument("--real-max-retries", type=int, default=0)
    parser.add_argument("--output", default="artifacts/runs/itbench_fanout.json")
    args = parser.parse_args()

    data_path = Path(args.training_data)
    if not data_path.exists():
        raise FileNotFoundError(f"training data not found: {data_path}")
    examples = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(examples, list) or not examples:
        raise RuntimeError(f"invalid/empty training data: {data_path}")

    selected = _select_examples(examples, sample_size=max(1, args.sample_size), seed=args.seed)
    started = time.time()
    rows: list[dict[str, Any]] = []

    sim_runner = OpenHandsSRE() if args.simulate else None
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        pending: dict[Future, int] = {}

        def submit(idx: int, ex: dict[str, Any]) -> None:
            if args.simulate:
                fut = pool.submit(_run_simulated_incident, ex, idx, sim_runner)  # type: ignore[arg-type]
            else:
                fut = pool.submit(
                    _run_real_incident,
                    ex,
                    idx,
                    args.runtime_image,
                    args.base_port,
                    args.container_prefix,
                    args.run_timeout_s,
                    args.subprocess_timeout_s,
                    args.real_max_retries,
                )
            pending[fut] = idx

        queue = list(enumerate(selected, start=1))
        while queue and len(pending) < max(1, args.concurrency):
            idx, ex = queue.pop(0)
            submit(idx, ex)

        while pending:
            done, _ = wait(pending.keys(), return_when=FIRST_COMPLETED)
            for fut in done:
                idx = pending.pop(fut)
                try:
                    row = fut.result()
                except Exception as exc:  # pragma: no cover
                    row = {
                        "index": idx,
                        "status": "failed",
                        "error": str(exc),
                        "service_up": "False",
                        "step_count": "999",
                    }
                rows.append(row)
                print("ROW", json.dumps(row, ensure_ascii=True))

                if queue:
                    nidx, nex = queue.pop(0)
                    submit(nidx, nex)

    rows.sort(key=lambda x: int(x.get("index", 0)))
    ok_rows = [r for r in rows if r.get("status") == "ok"]
    up = sum(1 for r in ok_rows if str(r.get("service_up", "")).lower() == "true")
    elapsed = round(time.time() - started, 2)
    summary = {
        "total": len(rows),
        "ok": len(ok_rows),
        "timeouts": sum(1 for r in rows if r.get("status") == "timeout"),
        "setup_failed": sum(1 for r in rows if r.get("status") == "setup_failed"),
        "other_failed": sum(1 for r in rows if r.get("status") == "failed"),
        "service_up_true": up,
        "service_up_rate_ok_pct": round((up / len(ok_rows) * 100.0), 2) if ok_rows else 0.0,
        "completed_rate_pct": round((len(ok_rows) / len(rows) * 100.0), 2) if rows else 0.0,
        "elapsed_s": elapsed,
        "throughput_incidents_per_s": round((len(rows) / elapsed), 3) if elapsed > 0 else 0.0,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "rows": rows,
                "training_data": str(data_path),
                "sample_size_requested": int(args.sample_size),
                "sample_size_actual": len(rows),
                "seed": int(args.seed),
                "concurrency": int(args.concurrency),
                "simulate": bool(args.simulate),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("SUMMARY", json.dumps(summary, ensure_ascii=True))
    print("OUTPUT", output_path)


if __name__ == "__main__":
    main()
