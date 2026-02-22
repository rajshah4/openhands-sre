from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.benchmark_itbench_sample import map_itbench_to_demo_scenario


def _pick(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else None


def _build_balanced_sample(examples: list[dict[str, Any]], sample_size: int, seed: int) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "stale_lockfile": [],
        "readiness_probe_fail": [],
        "port_mismatch": [],
    }
    for ex in examples:
        mapped = map_itbench_to_demo_scenario(ex)
        ex2 = dict(ex)
        ex2["_mapped_scenario"] = mapped
        buckets[mapped].append(ex2)

    rnd = random.Random(seed)
    for rows in buckets.values():
        rnd.shuffle(rows)

    ordered: list[dict[str, Any]] = []
    idx = 0
    keys = ["stale_lockfile", "readiness_probe_fail", "port_mismatch"]
    while len(ordered) < sample_size:
        key = keys[idx % len(keys)]
        idx += 1
        if buckets[key]:
            ordered.append(buckets[key].pop(0))
        if not any(buckets.values()):
            break
    return ordered


def main() -> None:
    parser = argparse.ArgumentParser(description="Cost-controlled real-call ITBench sample benchmark")
    parser.add_argument("--training-data", default="training_data/atlas_sre_scenarios.json")
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--runtime-image", default="openhands-gepa-sre-target:latest")
    parser.add_argument("--base-port", type=int, default=15100)
    parser.add_argument("--container-prefix", default="openhands-gepa-itbench")
    parser.add_argument("--run-timeout-s", type=int, default=90, help="run_demo real-run timeout")
    parser.add_argument("--subprocess-timeout-s", type=int, default=190, help="hard timeout per incident process")
    parser.add_argument("--real-max-retries", type=int, default=0)
    parser.add_argument("--output", default="artifacts/runs/itbench_real_sample.json")
    args = parser.parse_args()

    data_path = Path(args.training_data)
    if not data_path.exists():
        raise FileNotFoundError(f"training data not found: {data_path}")
    examples = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(examples, list) or not examples:
        raise RuntimeError(f"invalid/empty training data: {data_path}")

    selected = _build_balanced_sample(examples, sample_size=max(1, args.sample_size), seed=args.seed)
    if not selected:
        raise RuntimeError("No scenarios selected from training data")

    rows: list[dict[str, Any]] = []
    for i, ex in enumerate(selected, 1):
        mapped = str(ex["_mapped_scenario"])
        source_id = str(ex.get("scenario_id", ""))
        container_name = f"{args.container_prefix}-{i}"
        port = args.base_port + i
        target_url = f"http://127.0.0.1:{port}"

        subprocess.run(["pkill", "-f", "run_demo.py --mode optimized --strategy-source skills"], check=False)
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
                args.runtime_image,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if start.returncode != 0:
            row = {
                "index": i,
                "source_scenario_id": source_id,
                "mapped_scenario": mapped,
                "status": "setup_failed",
                "error": (start.stderr or "").strip(),
            }
            rows.append(row)
            print("ROW", json.dumps(row, ensure_ascii=True))
            continue

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
            str(args.real_max_retries),
            "--real-run-timeout-s",
            str(args.run_timeout_s),
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
                timeout=max(30, args.subprocess_timeout_s),
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
        row = {
            "index": i,
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
        rows.append(row)
        print("ROW", json.dumps(row, ensure_ascii=True))
        subprocess.run(["docker", "rm", "-f", container_name], check=False, capture_output=True, text=True)

    ok_rows = [r for r in rows if r.get("status") == "ok"]
    up = sum(1 for r in ok_rows if str(r.get("service_up", "")).lower() == "true")
    summary = {
        "total": len(rows),
        "ok": len(ok_rows),
        "timeouts": sum(1 for r in rows if r.get("status") == "timeout"),
        "setup_failed": sum(1 for r in rows if r.get("status") == "setup_failed"),
        "service_up_true": up,
        "service_up_rate_ok_pct": round((up / len(ok_rows) * 100.0), 2) if ok_rows else 0.0,
        "completed_rate_pct": round((len(ok_rows) / len(rows) * 100.0), 2) if rows else 0.0,
        "sample_size_requested": int(args.sample_size),
        "sample_size_actual": len(rows),
    }

    payload = {
        "summary": summary,
        "rows": rows,
        "training_data": str(data_path),
        "seed": int(args.seed),
        "runtime_image": args.runtime_image,
        "run_timeout_s": int(args.run_timeout_s),
        "subprocess_timeout_s": int(args.subprocess_timeout_s),
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print("SUMMARY", json.dumps(summary, ensure_ascii=True))
    print("OUTPUT", output_path)


if __name__ == "__main__":
    main()
