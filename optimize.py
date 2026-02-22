from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from openhands_driver import OpenHandsSRE


TRAINING_DATA = Path(__file__).parent / "training_data" / "scenarios.json"

try:
    import dspy  # type: ignore
except Exception:  # pragma: no cover - optional dependency behavior
    dspy = None


if dspy is not None:
    class SRESignature(dspy.Signature):  # type: ignore[misc]
        """Turn an incident report into a troubleshooting plan."""

        error_report = dspy.InputField()
        plan = dspy.OutputField()


    class SREProgram(dspy.Module):  # type: ignore[misc]
        def __init__(self, strategy_hint: str, runner: OpenHandsSRE, scenario_id: str) -> None:
            super().__init__()
            self.strategy_hint = strategy_hint
            self.runner = runner
            self.scenario_id = scenario_id

        def forward(self, error_report: str) -> Any:
            prediction = self.runner.forward(
                strategy_hint=self.strategy_hint,
                error_report=error_report,
                dry_run=True,
                scenario_id=self.scenario_id,
            )
            return dspy.Prediction(plan=prediction.get("raw_output", ""), meta=prediction)


def validate_fix(example: dict[str, Any], prediction: dict[str, Any], trace: Any = None) -> float:
    """Score fix quality.

    0.0: service still down
    0.5: service up, but > 15 steps
    1.0: service up and <= 3 steps
    """
    container_name = prediction.get("container_name")
    service_up = bool(prediction.get("service_up", False))

    if container_name:
        cmd = [
            "docker",
            "exec",
            container_name,
            "sh",
            "-lc",
            "curl -s -o /dev/null -w '%{http_code}' localhost:5000",
        ]
        try:
            status_code = subprocess.check_output(cmd, text=True, timeout=8).strip()
            service_up = status_code == "200"
        except Exception:
            service_up = False

    if not service_up:
        return 0.0

    steps = int(prediction.get("step_count", 999))
    if steps > 15:
        return 0.5
    if steps <= 3:
        return 1.0
    return 0.75


def load_examples(training_data: str | Path | None = None) -> list[dict[str, Any]]:
    path = Path(training_data) if training_data else TRAINING_DATA
    return json.loads(path.read_text(encoding="utf-8"))


def load_gepa_optimizer() -> Any:
    try:
        import dspy  # type: ignore

        if hasattr(dspy, "GeneticParetoOptim"):
            return dspy.GeneticParetoOptim
        if hasattr(dspy, "teleprompt") and hasattr(dspy.teleprompt, "GeneticParetoOptim"):
            return dspy.teleprompt.GeneticParetoOptim
    except Exception:
        return None
    return None


def candidate_hints() -> list[str]:
    return [
        "Fix the bug.",
        "Check application code and restart the service.",
        (
            "Use quick triage first: verify /tmp lockfiles, readiness artifacts, "
            "and listening ports; apply the minimal fix and re-verify with curl localhost:5000."
        ),
        (
            "Follow this runbook: (1) curl localhost:5000, (2) inspect /tmp/service.lock and /tmp/ready.flag, "
            "(3) verify bound ports with ss -lntp, (4) fix the identified issue and retest."
        ),
    ]


def _evaluate_hint(module: OpenHandsSRE, examples: list[dict[str, Any]], hint: str) -> tuple[float, list[dict[str, Any]]]:
    scored: list[dict[str, Any]] = []
    scores: list[float] = []
    for ex in examples:
        pred = module.forward(
            strategy_hint=hint,
            error_report=ex["error_report"],
            dry_run=True,
            scenario_id=ex["scenario_id"],
        )
        score = validate_fix(ex, pred)
        scores.append(score)
        scored.append(
            {
                "scenario_id": ex["scenario_id"],
                "score": score,
                "step_count": pred.get("step_count", -1),
                "service_up": pred.get("service_up", False),
            }
        )
    return sum(scores) / len(scores), scored


def mock_gepa_optimize(module: OpenHandsSRE, examples: list[dict[str, Any]]) -> tuple[str, float]:
    best_hint = ""
    best_score = -1.0

    for hint in candidate_hints():
        mean_score, _ = _evaluate_hint(module, examples, hint)
        if mean_score > best_score:
            best_hint = hint
            best_score = mean_score

    return best_hint, best_score


def iterative_refinement_optimize(
    module: OpenHandsSRE,
    examples: list[dict[str, Any]],
    rounds: int = 3,
) -> tuple[str, float, list[dict[str, Any]]]:
    """Simple iterative strategy refinement baseline.

    This is intentionally straightforward so it serves as a transparent baseline
    against GEPA-style search.
    """
    hint = "Fix the bug."
    history: list[dict[str, Any]] = []

    scenario_patches = {
        "stale_lockfile": "check /tmp/service.lock and remove stale lockfiles early",
        "readiness_probe_fail": "check /tmp/ready.flag readiness artifacts",
        "port_mismatch": "inspect listening ports and verify 5000 vs 5001",
    }

    best_hint = hint
    best_score, best_scored = _evaluate_hint(module, examples, hint)
    history.append({"round": 0, "hint": hint, "score": best_score, "scored": best_scored})

    for i in range(1, rounds + 1):
        _, scored = _evaluate_hint(module, examples, hint)
        deficits = [s for s in scored if s["score"] < 1.0]
        if not deficits:
            break

        missing = []
        for d in deficits:
            patch = scenario_patches.get(d["scenario_id"])
            if patch and patch not in missing and patch not in hint:
                missing.append(patch)

        if missing:
            hint = (
                f"{hint} Then follow this refinement: "
                + "; ".join(missing)
                + "; always verify with curl localhost:5000."
            )

        score, scored_new = _evaluate_hint(module, examples, hint)
        history.append({"round": i, "hint": hint, "score": score, "scored": scored_new})
        if score > best_score:
            best_score = score
            best_hint = hint

    return best_hint, best_score, history


def get_best_hint(
    optimizer: str,
    runner: OpenHandsSRE,
    examples: list[dict[str, Any]],
    iterative_rounds: int = 3,
) -> tuple[str, float, list[dict[str, Any]] | None]:
    if optimizer == "iterative":
        hint, score, history = iterative_refinement_optimize(runner, examples, rounds=iterative_rounds)
        return hint, score, history

    # default: gepa-style candidate selection
    hint, score = mock_gepa_optimize(runner, examples)
    return hint, score, None


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize SRE strategy hints with GEPA-style loop")
    parser.add_argument("--runtime-image", default="openhands-gepa-sre-target:latest")
    parser.add_argument("--optimizer", choices=["gepa", "iterative"], default="gepa")
    parser.add_argument("--iterative-rounds", type=int, default=3)
    parser.add_argument("--training-data", default=str(TRAINING_DATA))
    parser.add_argument("--use-real-runner", action="store_true", help="Use real OpenHands SDK execution")
    args = parser.parse_args()

    examples = load_examples(args.training_data)
    runner = OpenHandsSRE(runtime_image=args.runtime_image)

    # We keep GEPA detection for compatibility, but the runtime in this demo stays simulation-fast.
    _ = load_gepa_optimizer()

    best_hint, best_score, history = get_best_hint(
        optimizer=args.optimizer,
        runner=runner,
        examples=examples,
        iterative_rounds=args.iterative_rounds,
    )

    prefix = "sim-gepa" if args.optimizer == "gepa" else "sim-iterative"
    print(f"[{prefix}] scenarios:", ", ".join(ex["scenario_id"] for ex in examples))
    print(f"[{prefix}] best_hint:", best_hint)
    print(f"[{prefix}] best_score:", round(best_score, 3))

    if history:
        for h in history:
            print(f"[{prefix}] round={h['round']} score={round(h['score'], 3)}")


if __name__ == "__main__":
    main()
