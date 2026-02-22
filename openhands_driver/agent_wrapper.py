from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import time
from typing import Any


RISK_ORDER = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}


def _risk_value(level: str) -> int:
    return RISK_ORDER.get((level or "UNKNOWN").upper(), 0)


def _is_transient_remote_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    transient_markers = [
        "remote conversation not found",
        "runtime may have been deleted",
        "server disconnected without sending a response",
        "remoteprotocolerror",
        "connection reset",
        "temporarily unavailable",
    ]
    return any(m in msg for m in transient_markers)


@dataclass
class OpenHandsResult:
    strategy_hint: str
    raw_output: str
    service_up: bool
    step_count: int
    events: list[str]
    scenario_id: str
    tool_actions: list[str]
    security_risks: list[str]
    max_security_risk_seen: str
    confirmation_required: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OpenHandsSRE:
    """Bridge object that behaves like a DSPy module-friendly runner."""

    def __init__(
        self,
        runtime_image: str = "openhands-gepa-sre-target:latest",
        model: str | None = None,
        use_mock_if_sdk_missing: bool = True,
        remote_host: str | None = None,
        remote_working_dir: str = "/workspace",
        remote_api_key: str | None = None,
        allow_local_workspace: bool = False,
        real_max_retries: int = 2,
        real_run_timeout_s: int = 180,
    ) -> None:
        self.runtime_image = runtime_image
        self.model = model
        self.use_mock_if_sdk_missing = use_mock_if_sdk_missing
        self.remote_host = remote_host or os.getenv("OPENHANDS_REMOTE_HOST")
        self.remote_working_dir = remote_working_dir
        self.remote_api_key = remote_api_key or os.getenv("OPENHANDS_REMOTE_API_KEY")
        self.allow_local_workspace = allow_local_workspace
        self.real_max_retries = max(0, real_max_retries)
        self.real_run_timeout_s = max(30, real_run_timeout_s)

    def _build_system_message(
        self,
        strategy_hint: str,
        target_url: str,
        target_container: str | None = None,
        preferred_skill: str | None = None,
    ) -> str:
        base = (
            "You are an SRE incident-response agent. "
            "Use Terminal and FileEditor tools to diagnose and recover service health quickly. "
            "You must execute real commands, not just provide a plan. "
            f"Goal: recover the Flask service at {target_url} and make it return HTTP 200. "
            "Always verify with curl after making a change. "
            f"Runbook hint: {strategy_hint}"
        )
        if target_container:
            base += (
                f" Target container is '{target_container}'. If you must restart/recreate it, "
                "preserve the same container name and image discovered via docker inspect. "
                "Do not switch to unrelated images/services."
            )
        if not preferred_skill:
            return base
        return f"{base} Preferred skill to apply first: {preferred_skill}."

    def _scenario_from_error(self, error_report: str) -> str:
        report = error_report.lower()
        if "stale_lockfile" in report or "lockfile" in report:
            return "stale_lockfile"
        if "bad_env_config" in report or "required_api_key" in report or "missing env" in report:
            return "bad_env_config"
        if "readiness_probe_fail" in report or "ready.flag" in report or "readiness" in report:
            return "readiness_probe_fail"
        if "port_mismatch" in report or "wrong port" in report or "5001" in report:
            return "port_mismatch"
        return "stale_lockfile"

    def _is_optimized_for_scenario(self, strategy_hint: str, scenario_id: str) -> bool:
        hint = strategy_hint.lower()
        if scenario_id == "stale_lockfile":
            return (("lockfile" in hint or "service.lock" in hint) and "/tmp" in hint)
        if scenario_id == "bad_env_config":
            return "required_api_key" in hint or ("env" in hint and "config" in hint)
        if scenario_id == "readiness_probe_fail":
            return "ready.flag" in hint or "readiness" in hint
        if scenario_id == "port_mismatch":
            return "port" in hint and ("5000" in hint or "5001" in hint)
        return False

    def _mock_plan(self, scenario_id: str, optimized: bool, target_url: str) -> tuple[list[str], bool]:
        baseline_events = {
            "stale_lockfile": [
                f"curl -i {target_url}",
                "cat /app/app.py",
                "pip list",
                "ls -la /tmp",
                "rm -f /tmp/service.lock",
                f"curl -i {target_url}",
            ],
            "bad_env_config": [
                f"curl -i {target_url}",
                "cat /app/app.py",
                "printenv | sort",
                "export REQUIRED_API_KEY=demo-key",
                f"curl -i {target_url}",
            ],
            "readiness_probe_fail": [
                f"curl -i {target_url}",
                "cat /app/app.py",
                "ls -la /tmp",
                "touch /tmp/ready.flag",
                f"curl -i {target_url}",
            ],
            "port_mismatch": [
                f"curl -i {target_url}",
                "ss -lntp",
                "curl -i localhost:5001",
                "socat TCP-LISTEN:5000,fork TCP:127.0.0.1:5001",
                f"curl -i {target_url}",
            ],
        }
        optimized_events = {
            "stale_lockfile": [
                "ls -la /tmp | grep service.lock",
                "rm -f /tmp/service.lock",
                f"curl -i {target_url}",
            ],
            "bad_env_config": [
                "printenv | grep REQUIRED_API_KEY",
                "export REQUIRED_API_KEY=demo-key",
                f"curl -i {target_url}",
            ],
            "readiness_probe_fail": [
                "ls -la /tmp | grep ready.flag",
                "touch /tmp/ready.flag",
                f"curl -i {target_url}",
            ],
            "port_mismatch": [
                "ss -lntp | grep 5001",
                "socat TCP-LISTEN:5000,fork TCP:127.0.0.1:5001",
                f"curl -i {target_url}",
            ],
        }
        events = optimized_events[scenario_id] if optimized else baseline_events[scenario_id]
        return events, True

    def _mock_run(self, strategy_hint: str, error_report: str, target_url: str) -> OpenHandsResult:
        scenario_id = self._scenario_from_error(error_report)
        optimized = self._is_optimized_for_scenario(strategy_hint, scenario_id)
        events, service_up = self._mock_plan(scenario_id, optimized, target_url)

        quality = "optimized" if optimized else "baseline"
        raw = f"Simulation run ({quality}): diagnosed {scenario_id} and restored service."

        return OpenHandsResult(
            strategy_hint=strategy_hint,
            raw_output=raw,
            service_up=service_up,
            step_count=len(events),
            events=events,
            scenario_id=scenario_id,
            tool_actions=["terminal" for _ in events],
            security_risks=["LOW" for _ in events],
            max_security_risk_seen="LOW",
            confirmation_required=False,
        )

    def _extract_text(self, result: Any) -> str:
        if result is None:
            return ""
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            return json.dumps(result, ensure_ascii=True)
        for attr in (
            "output",
            "final_output",
            "text",
            "message",
            "summary",
            "action",
            "observation",
            "tool_name",
        ):
            if hasattr(result, attr):
                value = getattr(result, attr)
                if isinstance(value, str):
                    return value
        return repr(result)

    def _build_workspace(self) -> Any:
        if self.remote_host:
            from openhands.sdk import RemoteWorkspace  # type: ignore

            return RemoteWorkspace(
                host=self.remote_host,
                working_dir=self.remote_working_dir,
                api_key=self.remote_api_key,
            )
        if self.allow_local_workspace:
            return str(Path.cwd())
        raise RuntimeError(
            "Real mode requires remote sandbox workspace. Set OPENHANDS_REMOTE_HOST (or pass remote_host) "
            "or explicitly set allow_local_workspace=True if you accept host command execution risk."
        )

    def _run_real_once(
        self,
        strategy_hint: str,
        error_report: str,
        stream: bool = True,
        scenario_id: str = "stale_lockfile",
        max_security_risk: str = "HIGH",
        require_confirmation_for_risk: str | None = None,
        auto_confirm: bool = False,
        target_url: str = "http://127.0.0.1:15000",
        target_container: str | None = None,
        trace_key: str | None = None,
        preferred_skill: str | None = None,
    ) -> OpenHandsResult:
        from openhands.sdk import Agent, AgentContext, Conversation, LLM, Tool, load_project_skills  # type: ignore
        from openhands.tools import FileEditorTool, TerminalTool, register_default_tools  # type: ignore

        register_default_tools(enable_browser=False)

        workspace = self._build_workspace()

        skills = load_project_skills(Path.cwd())
        if preferred_skill:
            preferred = next((sk for sk in skills if sk.name == preferred_skill), None)
            if preferred is not None:
                ordered = [preferred] + [sk for sk in skills if sk.name != preferred_skill]
                skills = ordered
        agent_context = AgentContext(skills=skills)

        system_message = self._build_system_message(
            strategy_hint,
            target_url,
            target_container=target_container,
            preferred_skill=preferred_skill,
        )
        target_context = (
            f"Target service endpoint: {target_url}. "
            if not target_container
            else (
                f"Target service endpoint: {target_url}. "
                f"Service is running inside docker container '{target_container}'. "
                "Use docker commands (e.g., docker exec) to inspect/fix inside that container. "
            )
        )
        task = (
            f"{system_message}\n\n"
            f"{target_context}"
            "Diagnose why the app is failing and fix it. "
            "Ensure it returns HTTP 200. "
            f"Done criteria: external curl to {target_url} must return JSON containing status='ok' "
            f"and scenario='{scenario_id}'. "
            "You must use terminal commands to inspect state, apply a fix, and verify with curl. "
            "If you do not execute tools, the task is incomplete. "
            f"Scenario: {scenario_id}. "
            f"Incident context: {error_report}"
            + ("" if trace_key is None else f" Trace key: {trace_key}.")
        )

        model_name = self.model or os.getenv("OPENHANDS_MODEL", "gpt-4.1-mini")
        llm = LLM(model=model_name, api_key=os.getenv("OPENAI_API_KEY"))
        tools = [Tool(name=TerminalTool.name), Tool(name=FileEditorTool.name)]

        agent = Agent(
            llm=llm,
            tools=tools,
            include_default_tools=["FinishTool", "ThinkTool"],
            system_prompt_kwargs={"cli_mode": True},
            agent_context=agent_context,
        )

        events: list[str] = []

        def on_event(event: Any) -> None:
            text = self._extract_text(event)
            if text:
                events.append(text)
                if stream:
                    print(text)

        conv = Conversation(agent=agent, workspace=workspace, callbacks=[on_event])
        try:
            conv.send_message(task)
            try:
                conv.run(timeout=self.real_run_timeout_s)
            except TypeError:
                conv.run()

            action_events = [e for e in conv.state.events if type(e).__name__ == "ActionEvent"]
            tool_actions = [getattr(e, "tool_name", "") for e in action_events if getattr(e, "tool_name", "")]
            terminal_or_file_actions = [t for t in tool_actions if t in {"terminal", "file_editor"}]
            if not terminal_or_file_actions:
                raise RuntimeError("Real run completed without terminal/file_editor tool actions.")

            security_risks = [
                str(getattr(e, "security_risk", "UNKNOWN")).split(".")[-1] for e in action_events
            ]
            max_risk_seen = "UNKNOWN"
            if security_risks:
                max_risk_seen = max(security_risks, key=_risk_value)

            if _risk_value(max_risk_seen) > _risk_value(max_security_risk):
                raise RuntimeError(
                    f"Security policy violation: max risk seen {max_risk_seen} exceeds allowed {max_security_risk}."
                )

            confirmation_required = False
            if require_confirmation_for_risk is not None:
                threshold = require_confirmation_for_risk.upper()
                confirmation_required = any(_risk_value(r) >= _risk_value(threshold) for r in security_risks)
                if confirmation_required and not auto_confirm:
                    raise RuntimeError(
                        f"Confirmation required for risk >= {threshold}, but auto_confirm is disabled."
                    )

            final_message = ""
            for e in reversed(conv.state.events):
                obs = getattr(e, "observation", None)
                if obs is None:
                    continue
                dump = obs.model_dump() if hasattr(obs, "model_dump") else {}
                content = dump.get("content", [])
                for item in content:
                    text = item.get("text") if isinstance(item, dict) else None
                    if text:
                        final_message = text
                        break
                if final_message:
                    break

            raw = final_message or "\n".join(events[-6:])
            step_count = len(terminal_or_file_actions)
            # Real-mode health is evaluated externally by run_demo verifier.
            service_up = False

        finally:
            try:
                conv.close()
            except Exception:
                pass

        return OpenHandsResult(
            strategy_hint=strategy_hint,
            raw_output=raw,
            service_up=service_up,
            step_count=max(1, step_count),
            events=events,
            scenario_id=scenario_id,
            tool_actions=terminal_or_file_actions,
            security_risks=security_risks,
            max_security_risk_seen=max_risk_seen,
            confirmation_required=confirmation_required,
        )

    def _run_real(
        self,
        strategy_hint: str,
        error_report: str,
        stream: bool = True,
        scenario_id: str = "stale_lockfile",
        max_security_risk: str = "HIGH",
        require_confirmation_for_risk: str | None = None,
        auto_confirm: bool = False,
        target_url: str = "http://127.0.0.1:15000",
        target_container: str | None = None,
        trace_key: str | None = None,
        preferred_skill: str | None = None,
    ) -> OpenHandsResult:
        attempt = 0
        last_exc: Exception | None = None
        max_attempts = self.real_max_retries + 1

        while attempt < max_attempts:
            attempt += 1
            try:
                return self._run_real_once(
                    strategy_hint=strategy_hint,
                    error_report=error_report,
                    stream=stream,
                    scenario_id=scenario_id,
                    max_security_risk=max_security_risk,
                    require_confirmation_for_risk=require_confirmation_for_risk,
                    auto_confirm=auto_confirm,
                    target_url=target_url,
                    target_container=target_container,
                    trace_key=trace_key,
                    preferred_skill=preferred_skill,
                )
            except Exception as exc:
                last_exc = exc
                if attempt >= max_attempts or not _is_transient_remote_error(exc):
                    raise
                time.sleep(min(3.0 * attempt, 10.0))

        assert last_exc is not None
        raise last_exc

    def forward(
        self,
        strategy_hint: str,
        error_report: str = "Service fails at localhost:5000 with HTTP 500.",
        stream: bool = False,
        dry_run: bool = False,
        scenario_id: str | None = None,
        max_security_risk: str = "HIGH",
        require_confirmation_for_risk: str | None = None,
        auto_confirm: bool = False,
        target_url: str = "http://127.0.0.1:15000",
        target_container: str | None = None,
        trace_key: str | None = None,
        preferred_skill: str | None = None,
    ) -> dict[str, Any]:
        resolved_scenario = scenario_id or self._scenario_from_error(error_report)
        if dry_run:
            dry_result = self._mock_run(strategy_hint, f"{resolved_scenario}: {error_report}", target_url).to_dict()
            dry_result["fallback_used"] = False
            return dry_result

        try:
            result = self._run_real(
                strategy_hint=strategy_hint,
                error_report=error_report,
                stream=stream,
                scenario_id=resolved_scenario,
                max_security_risk=max_security_risk,
                require_confirmation_for_risk=require_confirmation_for_risk,
                auto_confirm=auto_confirm,
                target_url=target_url,
                target_container=target_container,
                trace_key=trace_key,
                preferred_skill=preferred_skill,
            ).to_dict()
            result["fallback_used"] = False
            return result
        except Exception as exc:
            if not self.use_mock_if_sdk_missing:
                raise
            fallback = self._mock_run(strategy_hint, f"{resolved_scenario}: {error_report}", target_url).to_dict()
            fallback["fallback_used"] = True
            fallback["fallback_reason"] = str(exc)
            return fallback
