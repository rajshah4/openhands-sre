from __future__ import annotations

import argparse
from dataclasses import dataclass
from statistics import mean
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openhands_driver import OpenHandsSRE
from optimize import get_best_hint, load_examples, validate_fix
from run_demo import BASELINE_HINT, OPTIMIZED_HINT


@dataclass
class EvalSummary:
    name: str
    success_rate: float
    avg_steps: float
    avg_score: float
    max_risk_seen: str


def evaluate_strategy(
    name: str,
    hint: str,
    runner: OpenHandsSRE,
    examples: list[dict],
    simulate: bool,
    max_security_risk: str,
) -> EvalSummary:
    successes = []
    steps = []
    scores = []
    risks = []

    for ex in examples:
        pred = runner.forward(
            strategy_hint=hint,
            error_report=ex["error_report"],
            scenario_id=ex["scenario_id"],
            dry_run=simulate,
            stream=not simulate,
            max_security_risk=max_security_risk,
        )
        successes.append(bool(pred.get("service_up", False)))
        steps.append(int(pred.get("step_count", 999)))
        scores.append(validate_fix(ex, pred))
        risks.append(str(pred.get("max_security_risk_seen", "UNKNOWN")))

    rank = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
    max_risk = max(risks, key=lambda r: rank.get(r, 0)) if risks else "UNKNOWN"

    return EvalSummary(
        name=name,
        success_rate=mean(1.0 if s else 0.0 for s in successes),
        avg_steps=mean(steps),
        avg_score=mean(scores),
        max_risk_seen=max_risk,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare optimization approaches for the SRE demo")
    parser.add_argument("--runtime-image", default="openhands-gepa-sre-target:latest")
    parser.add_argument("--simulate", action="store_true", help="Use deterministic simulation execution")
    parser.add_argument("--mock", dest="simulate", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--max-security-risk", choices=["LOW", "MEDIUM", "HIGH"], default="HIGH")
    args = parser.parse_args()

    examples = load_examples()
    runner = OpenHandsSRE(runtime_image=args.runtime_image)

    gepa_hint, gepa_score, _ = get_best_hint("gepa", runner, examples)
    iterative_hint, iterative_score, _ = get_best_hint("iterative", runner, examples)

    print("[optimizer] gepa_score=", round(gepa_score, 3))
    print("[optimizer] iterative_score=", round(iterative_score, 3))

    approaches = [
        ("baseline", BASELINE_HINT),
        ("optimized-manual", OPTIMIZED_HINT),
        ("optimized-gepa", gepa_hint),
        ("optimized-iterative", iterative_hint),
    ]

    summaries = [
        evaluate_strategy(name, hint, runner, examples, simulate=args.simulate, max_security_risk=args.max_security_risk)
        for name, hint in approaches
    ]

    print("\n=== Approach Scorecard ===")
    print("name | success_rate | avg_steps | avg_score | max_risk")
    for s in summaries:
        print(
            f"{s.name} | {s.success_rate:.2f} | {s.avg_steps:.2f} | {s.avg_score:.3f} | {s.max_risk_seen}"
        )


if __name__ == "__main__":
    main()
