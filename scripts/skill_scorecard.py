from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def pct(x: int, total: int) -> float:
    return round((x / total) * 100.0, 2) if total else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Skill scorecard from structured trace logs")
    parser.add_argument("--trace-log", default="artifacts/runs/trace_log.jsonl")
    parser.add_argument("--limit", type=int, default=0, help="Limit to most recent N rows")
    args = parser.parse_args()

    path = Path(args.trace_log)
    rows = load_rows(path)
    if args.limit > 0:
        rows = rows[-args.limit :]

    if not rows:
        print(f"No rows found in {path}")
        return

    by_skill: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for r in rows:
        skill = r.get("skill_id") or "(none)"
        scenario = r.get("scenario") or "(unknown)"
        by_skill[skill].append(r)
        by_scenario[scenario].append(r)

    print("=== Skill Scorecard ===")
    print("skill_id | runs | success_rate | verified_rate | avg_steps")
    for skill_id, items in sorted(by_skill.items(), key=lambda kv: kv[0]):
        runs = len(items)
        success = sum(1 for i in items if bool(i.get("service_up", False)))
        verified = sum(1 for i in items if bool((i.get("verification") or {}).get("verified", False)))
        avg_steps = sum(int(i.get("step_count", 999)) for i in items) / runs
        print(f"{skill_id} | {runs} | {pct(success, runs)}% | {pct(verified, runs)}% | {avg_steps:.2f}")

    print("\n=== Scenario Scorecard ===")
    print("scenario | runs | success_rate | avg_steps")
    for scenario, items in sorted(by_scenario.items(), key=lambda kv: kv[0]):
        runs = len(items)
        success = sum(1 for i in items if bool(i.get("service_up", False)))
        avg_steps = sum(int(i.get("step_count", 999)) for i in items) / runs
        print(f"{scenario} | {runs} | {pct(success, runs)}% | {avg_steps:.2f}")


if __name__ == "__main__":
    main()
