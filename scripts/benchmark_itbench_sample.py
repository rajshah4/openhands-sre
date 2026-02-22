from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openhands_driver import OpenHandsSRE
from run_demo import BASELINE_HINT, OPTIMIZED_HINT


def map_itbench_to_demo_scenario(example: dict[str, Any]) -> str:
    text = " ".join(
        [
            str(example.get("scenario_id", "")),
            str(example.get("error_report", "")),
            " ".join(str(x) for x in example.get("expected_first_checks", [])),
        ]
    ).lower()

    if "readiness" in text or "containersnotready" in text or "probe" in text:
        return "readiness_probe_fail"
    if any(k in text for k in ["port", "network", "dns", "gateway", "service", "traffic", "latency"]):
        return "port_mismatch"
    return "stale_lockfile"


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    fixed = sum(1 for r in results if r["service_up"])
    avg_steps = sum(r["step_count"] for r in results) / max(1, total)
    by_scenario: dict[str, dict[str, float]] = {}
    for r in results:
        key = r["mapped_scenario"]
        slot = by_scenario.setdefault(key, {"count": 0.0, "fixed": 0.0, "steps": 0.0})
        slot["count"] += 1.0
        slot["fixed"] += 1.0 if r["service_up"] else 0.0
        slot["steps"] += float(r["step_count"])
    for slot in by_scenario.values():
        slot["success_rate"] = (slot["fixed"] / max(1.0, slot["count"])) * 100.0
        slot["avg_steps"] = slot["steps"] / max(1.0, slot["count"])
    return {
        "total": total,
        "fixed": fixed,
        "failed": total - fixed,
        "success_rate": (fixed / max(1, total)) * 100.0,
        "avg_steps": avg_steps,
        "by_scenario": by_scenario,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Low-cost ITBench sample baseline (dry-run proxy)")
    parser.add_argument("--training-data", default="training_data/atlas_sre_scenarios.json")
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--mode", choices=["baseline", "optimized"], default="optimized")
    parser.add_argument("--output", default=None, help="Optional JSON output path")
    args = parser.parse_args()

    data_path = Path(args.training_data)
    if not data_path.exists():
        raise FileNotFoundError(f"training data not found: {data_path}")

    examples = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(examples, list) or not examples:
        raise RuntimeError(f"invalid/empty training data: {data_path}")

    random.seed(args.seed)
    random.shuffle(examples)
    selected = examples[: max(1, min(args.sample_size, len(examples)))]

    hint = BASELINE_HINT if args.mode == "baseline" else OPTIMIZED_HINT
    runner = OpenHandsSRE()

    results: list[dict[str, Any]] = []
    for ex in selected:
        mapped = map_itbench_to_demo_scenario(ex)
        pred = runner.forward(
            strategy_hint=hint,
            error_report=str(ex.get("error_report", "")),
            scenario_id=mapped,
            dry_run=True,
            stream=False,
        )
        results.append(
            {
                "source_scenario_id": str(ex.get("scenario_id", "")),
                "mapped_scenario": mapped,
                "service_up": bool(pred.get("service_up", False)),
                "step_count": int(pred.get("step_count", 999)),
            }
        )

    score = summarize(results)
    print("mode:", args.mode)
    print("sample_size:", len(results))
    print("success_rate_pct:", round(score["success_rate"], 2))
    print("avg_steps:", round(score["avg_steps"], 2))
    print("by_scenario:")
    for key in sorted(score["by_scenario"].keys()):
        slot = score["by_scenario"][key]
        print(
            f"  - {key}: count={int(slot['count'])} "
            f"success_rate={slot['success_rate']:.2f}% avg_steps={slot['avg_steps']:.2f}"
        )

    if args.output:
        payload = {
            "mode": args.mode,
            "sample_size": len(results),
            "score": score,
            "results": results,
            "training_data": str(data_path),
            "seed": args.seed,
        }
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print("output:", out_path)


if __name__ == "__main__":
    main()
