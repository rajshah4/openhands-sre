from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openhands_driver.runtime_env import ensure_real_call_requirements, load_project_env, runtime_env_status


def run_python_step(title: str, args: list[str]) -> tuple[str, int]:
    print(f"\n{'=' * 80}")
    print(title)
    print(f"$ {' '.join([sys.executable, *args])}")

    proc = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    if proc.stdout:
        print(proc.stdout)
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)

    step_match = re.search(r"step_count:\s*(\d+)", proc.stdout)
    steps = int(step_match.group(1)) if step_match else -1
    return proc.stdout, steps


def maybe_simulation_flag(real: bool) -> list[str]:
    return [] if real else ["--simulate"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full SRE demo sequence")
    parser.add_argument("--real", action="store_true", help="Use real OpenHands run instead of simulation")
    parser.add_argument("--runtime-image", default="openhands-gepa-sre-target:latest")
    parser.add_argument("--model", default=None)
    parser.add_argument("--env-file", default=None, help="Optional path to .env file")
    args = parser.parse_args()

    env_path = load_project_env(args.env_file)
    status = runtime_env_status()

    print("Self-Optimizing SRE Agent Demo Sequence")
    print(f"mode: {'real' if args.real else 'simulation'}")
    print(f"[env] loaded from: {env_path}")

    if args.real:
        ensure_real_call_requirements()
        print(
            "[env] real mode preflight passed: openai_api_key=%s lmnr_project_api_key=%s lamini_api_key=%s"
            % (
                status["openai_api_key"],
                status["lmnr_project_api_key"],
                status["lamini_api_key"],
            )
        )

    model_args = ["--model", args.model] if args.model else []
    runtime_args = ["--runtime-image", args.runtime_image]
    env_args = ["--env-file", args.env_file] if args.env_file else []
    simulation_args = maybe_simulation_flag(args.real)

    _, baseline_lock_steps = run_python_step(
        "1) The Incident + Baseline Policy (stale_lockfile)",
        [
            "run_demo.py",
            "--mode",
            "baseline",
            "--scenario",
            "stale_lockfile",
            *runtime_args,
            *model_args,
            *env_args,
            *simulation_args,
        ],
    )

    run_python_step(
        "2) GEPA-style Optimization",
        ["optimize.py", "--optimizer", "gepa", *runtime_args],
    )

    run_python_step(
        "3) Iterative Refinement Optimization",
        ["optimize.py", "--optimizer", "iterative", *runtime_args],
    )

    _, baseline_readiness_steps = run_python_step(
        "4) Baseline Policy (readiness_probe_fail)",
        [
            "run_demo.py",
            "--mode",
            "baseline",
            "--scenario",
            "readiness_probe_fail",
            *runtime_args,
            *model_args,
            *env_args,
            *simulation_args,
        ],
    )

    _, optimized_readiness_steps = run_python_step(
        "5) Optimized Policy using GEPA hint",
        [
            "run_demo.py",
            "--mode",
            "optimized",
            "--optimizer",
            "gepa",
            "--scenario",
            "readiness_probe_fail",
            *runtime_args,
            *model_args,
            *env_args,
            *simulation_args,
        ],
    )

    run_python_step(
        "6) Generalization Check (bad_env_config, iterative hint)",
        [
            "run_demo.py",
            "--mode",
            "optimized",
            "--optimizer",
            "iterative",
            "--scenario",
            "bad_env_config",
            *runtime_args,
            *model_args,
            *env_args,
            *simulation_args,
        ],
    )

    run_python_step(
        "7) Approach Scorecard",
        [
            "scripts/approach_scorecard.py",
            *runtime_args,
            *([] if args.real else ["--simulate"]),
        ],
    )

    print(f"\n{'=' * 80}")
    print("Demo Summary")
    print(f"stale_lockfile baseline steps: {baseline_lock_steps}")
    print(f"readiness baseline steps: {baseline_readiness_steps}")
    print(f"readiness optimized steps: {optimized_readiness_steps}")
    if baseline_readiness_steps > 0 and optimized_readiness_steps > 0:
        delta = baseline_readiness_steps - optimized_readiness_steps
        print(f"step reduction on readiness scenario: {delta}")


if __name__ == "__main__":
    main()
