from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from openhands_driver import OpenHandsSRE, format_skill_catalog, list_skill_ids, select_skill
from openhands_driver.runtime_env import ensure_real_call_requirements, load_project_env, runtime_env_status
from openhands_driver.trace_store import append_jsonl, utc_now_iso
from optimize import get_best_hint, load_examples


SCENARIO_ERRORS = {
    "stale_lockfile": "Service at localhost:5000 returns HTTP 500 after a previous crash.",
    "readiness_probe_fail": "Service startup passes but readiness probe stays unhealthy due to missing ready flag.",
    "port_mismatch": "Service probe on :5000 fails; process may be listening on a different port.",
}

BASELINE_HINT = "Fix the bug."
OPTIMIZED_HINT = (
    "Follow an incident-first runbook: check /tmp/service.lock and /tmp/ready.flag, "
    "check active listening ports with ss -lntp, apply the minimal corrective action, and re-verify with curl localhost:5000."
)


class StrategySelection(argparse.Namespace):
    strategy_source: str
    strategy_hint: str
    optimizer_score: float | None
    skill_id: str | None
    skill_path: str | None


def choose_optimizer_hint(
    optimizer: str,
    runtime_image: str,
    training_data: str | None = None,
) -> tuple[str, float | None]:
    if optimizer == "manual":
        return OPTIMIZED_HINT, None

    examples = load_examples(training_data)
    runner = OpenHandsSRE(runtime_image=runtime_image)
    hint, score, _history = get_best_hint(
        optimizer=optimizer,
        runner=runner,
        examples=examples,
    )
    return hint, score


def choose_strategy(
    *,
    mode: str,
    strategy_source: str,
    optimizer: str,
    runtime_image: str,
    training_data: str | None,
    scenario_id: str,
    error_report: str,
    skills_root: str,
    skill_id: str | None,
) -> StrategySelection:
    selected = StrategySelection()
    selected.optimizer_score = None
    selected.skill_id = None
    selected.skill_path = None

    if mode == "baseline":
        selected.strategy_source = "baseline"
        selected.strategy_hint = BASELINE_HINT
        return selected

    if strategy_source == "manual":
        selected.strategy_source = "manual"
        selected.strategy_hint = OPTIMIZED_HINT
        return selected

    if strategy_source == "optimizer":
        selected.strategy_source = f"optimizer:{optimizer}"
        selected.strategy_hint, selected.optimizer_score = choose_optimizer_hint(
            optimizer,
            runtime_image,
            training_data,
        )
        return selected

    if skill_id:
        skill_path = Path(skills_root) / skill_id / "SKILL.md"
        if not skill_path.exists():
            available = format_skill_catalog(list_skill_ids(skills_root))
            raise FileNotFoundError(f"Unknown skill_id={skill_id}. Available skills: {available}")
        selected.strategy_source = "skills"
        selected.strategy_hint = f"Follow the {skill_id} skill runbook and verify with curl after each fix."
        selected.skill_id = skill_id
        selected.skill_path = str(skill_path)
        return selected

    skill = select_skill(scenario_id=scenario_id, error_report=error_report, skills_root=skills_root)
    selected.strategy_source = "skills"
    selected.strategy_hint = skill.strategy_hint
    selected.skill_id = skill.skill_id
    selected.skill_path = str(skill.skill_path)
    return selected


def _probe_http_code(url: str) -> str:
    proc = subprocess.run(
        ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", url],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return "000"
    return (proc.stdout or "000").strip()


def _probe_http_response(url: str) -> dict[str, Any]:
    proc = subprocess.run(
        ["curl", "-sS", "-i", url],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "http_code": "000",
            "headers": {},
            "body": "",
            "error": (proc.stderr or proc.stdout or "").strip(),
        }

    raw = proc.stdout or ""
    header_text = ""
    body = raw
    if "\r\n\r\n" in raw:
        header_text, body = raw.split("\r\n\r\n", 1)
    elif "\n\n" in raw:
        header_text, body = raw.split("\n\n", 1)

    status_line = ""
    headers: dict[str, str] = {}
    if header_text:
        header_lines = [line.strip() for line in header_text.splitlines() if line.strip()]
        if header_lines:
            status_line = header_lines[0]
        for line in header_lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()

    code_match = re.search(r"HTTP/\d(?:\.\d)?\s+(\d{3})\b", status_line)
    code = code_match.group(1) if code_match else _probe_http_code(url)
    return {
        "http_code": code,
        "headers": headers,
        "body": body.strip(),
        "error": "",
    }


def inspect_target_container(name: str) -> dict[str, Any]:
    proc = subprocess.run(
        ["docker", "inspect", "--format", "{{.Config.Image}}|{{.State.Running}}", name],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return {"exists": False, "running": False, "image": None, "error": (proc.stderr or "").strip()}
    out = (proc.stdout or "").strip()
    image, running = (out.split("|", 1) + [""])[:2]
    return {
        "exists": True,
        "running": running.strip().lower() == "true",
        "image": image.strip() or None,
        "error": "",
    }


def verify_stable_endpoint(
    *,
    url: str,
    expected_scenario: str,
    consecutive_successes: int,
    max_attempts: int,
    interval_s: float,
) -> dict[str, Any]:
    successes = 0
    attempts: list[str] = []
    observations: list[dict[str, Any]] = []
    last_failure = ""

    for _ in range(max_attempts):
        observation = _probe_http_response(url)
        code = str(observation.get("http_code", "000"))
        attempts.append(code)
        observations.append({"http_code": code, "content_type": observation.get("headers", {}).get("content-type", "")})
        reason = ""

        if code != "200":
            reason = f"http code {code}"
        else:
            content_type = str(observation.get("headers", {}).get("content-type", "")).lower()
            if "application/json" not in content_type:
                reason = f"unexpected content-type {content_type or '(missing)'}"
            else:
                body = str(observation.get("body", ""))
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    reason = "invalid JSON body"
                else:
                    if payload.get("status") != "ok":
                        reason = f"unexpected status field {payload.get('status')!r}"
                    elif payload.get("scenario") != expected_scenario:
                        reason = (
                            f"unexpected scenario field {payload.get('scenario')!r}; "
                            f"expected {expected_scenario!r}"
                        )

        if not reason:
            successes += 1
            if successes >= consecutive_successes:
                return {
                    "verified": True,
                    "attempts": attempts,
                    "consecutive_target": consecutive_successes,
                    "last_failure": "",
                    "observations": observations,
                }
        else:
            successes = 0
            last_failure = reason
        time.sleep(max(0.1, interval_s))

    return {
        "verified": False,
        "attempts": attempts,
        "consecutive_target": consecutive_successes,
        "last_failure": last_failure,
        "observations": observations,
    }


def build_trace_record(
    *,
    run_id: str,
    args: argparse.Namespace,
    strategy: StrategySelection,
    result: dict[str, Any],
    verification: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "timestamp": utc_now_iso(),
        "run_id": run_id,
        "mode": args.mode,
        "scenario": args.scenario,
        "strategy_source": strategy.strategy_source,
        "skill_id": strategy.skill_id,
        "optimizer": args.optimizer,
        "simulate": bool(args.simulate),
        "target_url": args.target_url,
        "target_container": args.target_container,
        "service_up": bool(result.get("service_up", False)),
        "step_count": int(result.get("step_count", 999)),
        "fallback_used": bool(result.get("fallback_used", False)),
        "max_security_risk_seen": str(result.get("max_security_risk_seen", "UNKNOWN")),
        "tool_actions": list(result.get("tool_actions", [])),
        "security_risks": list(result.get("security_risks", [])),
        "verification": verification,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Skill-Driven SRE Agent demo")
    parser.add_argument("--mode", choices=["baseline", "optimized"], required=True)
    parser.add_argument(
        "--strategy-source",
        choices=["auto", "skills", "optimizer", "manual"],
        default="auto",
        help="How optimized mode picks the troubleshooting strategy (auto keeps backward compatibility)",
    )
    parser.add_argument(
        "--optimizer",
        choices=["manual", "gepa", "iterative"],
        default="manual",
        help="Optimizer to use when --strategy-source=optimizer",
    )
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIO_ERRORS.keys()),
        default="stale_lockfile",
        help="Incident scenario to simulate in simulation mode or include in task context",
    )
    parser.add_argument("--skills-root", default=".agents/skills")
    parser.add_argument("--skill-id", default=None, help="Force a specific skill id (under --skills-root)")
    parser.add_argument("--runtime-image", default="openhands-gepa-sre-target:latest")
    parser.add_argument("--training-data", default=None, help="Optional scenario training JSON for optimizer lane")
    parser.add_argument("--target-url", default="http://127.0.0.1:15000")
    parser.add_argument("--target-container", default=None, help="Optional docker container name where service runs")
    parser.add_argument("--remote-host", default=os.getenv("OPENHANDS_REMOTE_HOST"))
    parser.add_argument("--remote-working-dir", default="/workspace")
    parser.add_argument("--remote-api-key", default=os.getenv("OPENHANDS_REMOTE_API_KEY"))
    parser.add_argument("--allow-local-workspace", action="store_true")
    parser.add_argument("--real-max-retries", type=int, default=2)
    parser.add_argument("--real-run-timeout-s", type=int, default=180)
    parser.add_argument("--simulate", action="store_true", help="Force simulation execution")
    parser.add_argument("--mock", dest="simulate", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--model", default=None)
    parser.add_argument("--env-file", default=None, help="Optional path to .env file")
    parser.add_argument("--run-id", default=None, help="Optional run id for trace grouping")
    parser.add_argument("--trace-log", default="artifacts/runs/trace_log.jsonl")
    parser.add_argument("--disable-trace-log", action="store_true")
    parser.add_argument("--verify-consecutive-successes", type=int, default=2)
    parser.add_argument("--verify-max-attempts", type=int, default=6)
    parser.add_argument("--verify-interval-s", type=float, default=1.5)
    parser.add_argument(
        "--disable-container-identity-check",
        action="store_true",
        help="Disable post-run validation that target container is still running with expected image",
    )
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Allow fallback to simulated output if real OpenHands execution fails",
    )
    parser.add_argument(
        "--max-security-risk",
        choices=["LOW", "MEDIUM", "HIGH"],
        default="HIGH",
        help="Fail if any OpenHands action exceeds this risk level",
    )
    parser.add_argument(
        "--require-confirmation-for-risk",
        choices=["LOW", "MEDIUM", "HIGH"],
        default=None,
        help="Require confirmation when an action reaches this risk level",
    )
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="Auto-approve risky actions when confirmation is required",
    )
    args = parser.parse_args()

    run_id = args.run_id or f"run-{int(time.time())}"

    env_path = load_project_env(args.env_file)
    status = runtime_env_status()

    if args.simulate:
        print(f"[env] loaded from: {env_path}")
        print(
            "[env] openai_api_key=%s lmnr_project_api_key=%s lamini_api_key=%s"
            % (
                status["openai_api_key"],
                status["lmnr_project_api_key"],
                status["lamini_api_key"],
            )
        )
    else:
        ensure_real_call_requirements()
        print(f"[env] loaded from: {env_path}")
        print(
            "[env] real mode preflight passed: openai_api_key=%s lmnr_project_api_key=%s lamini_api_key=%s"
            % (
                status["openai_api_key"],
                status["lmnr_project_api_key"],
                status["lamini_api_key"],
            )
        )
        if not args.allow_fallback:
            print("[real] strict mode enabled (no simulation fallback)")
        print(
            "[real] remote_host=%s allow_local_workspace=%s"
            % (args.remote_host, args.allow_local_workspace)
        )

    effective_strategy_source = args.strategy_source
    if args.mode == "optimized" and args.strategy_source == "auto":
        if args.skill_id:
            effective_strategy_source = "skills"
        elif args.optimizer != "manual":
            effective_strategy_source = "optimizer"
        else:
            effective_strategy_source = "skills"

    strategy = choose_strategy(
        mode=args.mode,
        strategy_source=effective_strategy_source,
        optimizer=args.optimizer,
        runtime_image=args.runtime_image,
        training_data=args.training_data,
        scenario_id=args.scenario,
        error_report=SCENARIO_ERRORS[args.scenario],
        skills_root=args.skills_root,
        skill_id=args.skill_id,
    )

    if strategy.optimizer_score is not None:
        print(f"[optimizer] method={args.optimizer} score={round(strategy.optimizer_score, 3)}")

    if strategy.skill_id:
        print(f"[skill] selected={strategy.skill_id} path={strategy.skill_path}")

    runner = OpenHandsSRE(
        runtime_image=args.runtime_image,
        model=args.model,
        use_mock_if_sdk_missing=args.allow_fallback,
        remote_host=args.remote_host,
        remote_working_dir=args.remote_working_dir,
        remote_api_key=args.remote_api_key,
        allow_local_workspace=args.allow_local_workspace,
        real_max_retries=args.real_max_retries,
        real_run_timeout_s=args.real_run_timeout_s,
    )

    result = runner.forward(
        strategy_hint=strategy.strategy_hint,
        preferred_skill=strategy.skill_id,
        error_report=SCENARIO_ERRORS[args.scenario],
        scenario_id=args.scenario,
        stream=not args.simulate,
        dry_run=args.simulate,
        max_security_risk=args.max_security_risk,
        require_confirmation_for_risk=args.require_confirmation_for_risk,
        auto_confirm=args.auto_confirm,
        target_url=args.target_url,
        target_container=args.target_container,
    )

    verification: dict[str, Any] | None = None
    if not args.simulate:
        verification = verify_stable_endpoint(
            url=args.target_url,
            expected_scenario=args.scenario,
            consecutive_successes=max(1, args.verify_consecutive_successes),
            max_attempts=max(1, args.verify_max_attempts),
            interval_s=max(0.1, args.verify_interval_s),
        )

        container_identity: dict[str, Any] | None = None
        if args.target_container and not args.disable_container_identity_check:
            inspected = inspect_target_container(args.target_container)
            expected_image = args.runtime_image
            image_matches = bool(inspected.get("exists")) and inspected.get("image") == expected_image
            container_identity = {
                "verified": bool(inspected.get("exists"))
                and bool(inspected.get("running"))
                and image_matches,
                "container": args.target_container,
                "expected_image": expected_image,
                "actual_image": inspected.get("image"),
                "running": bool(inspected.get("running")),
                "exists": bool(inspected.get("exists")),
                "error": inspected.get("error", ""),
            }
            verification["container_identity"] = container_identity
            verification["verified"] = bool(verification["verified"]) and bool(container_identity["verified"])

        # In real mode, service_up is derived from verifier truth only.
        result["service_up"] = bool(verification["verified"])

    if not args.disable_trace_log:
        row = build_trace_record(
            run_id=run_id,
            args=args,
            strategy=strategy,
            result=result,
            verification=verification,
        )
        trace_path = append_jsonl(args.trace_log, row)
        print(f"[trace] appended -> {trace_path}")

    print("\n=== Demo Result ===")
    print("run_id:", run_id)
    print("mode:", args.mode)
    print("strategy_source:", strategy.strategy_source)
    print("optimizer:", args.optimizer)
    print("scenario:", args.scenario)
    print("target_url:", args.target_url)
    print("target_container:", args.target_container)
    print("remote_host:", args.remote_host)
    print("allow_local_workspace:", args.allow_local_workspace)
    print("skill_id:", strategy.skill_id)
    print("skill_path:", strategy.skill_path)
    print("strategy_hint:", strategy.strategy_hint)
    print("service_up:", result.get("service_up"))
    print("step_count:", result.get("step_count"))
    if verification is not None:
        print("verification:", verification)
    print("fallback_used:", result.get("fallback_used", False))
    if result.get("fallback_reason"):
        print("fallback_reason:", result.get("fallback_reason"))
    print("tool_actions:", result.get("tool_actions", []))
    print("security_risks:", result.get("security_risks", []))
    print("max_security_risk_seen:", result.get("max_security_risk_seen"))
    print("confirmation_required:", result.get("confirmation_required"))
    print("raw_output:")
    print(result.get("raw_output", ""))
    print("events:")
    print(json.dumps(result.get("events", []), indent=2))


if __name__ == "__main__":
    main()
