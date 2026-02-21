# The Self-Optimizing SRE Agent

This repository demonstrates the synergy between:

- **Hands**: OpenHands SDK runtime that can inspect and fix a live broken service.
- **Brain**: GEPA-style or iterative optimization that improves the agent's troubleshooting strategy.

The core story:

- We simulate multiple deterministic SRE incidents in a Flask service.
- A **baseline** policy uses a generic prompt and takes more exploratory steps.
- An **optimized** policy uses a learned runbook hint and resolves incidents with fewer steps.

## Why OpenHands SDK (vs generic orchestration)

This demo intentionally leans into OpenHands SDK strengths:

- **Execution-native agent runtime**: tool calls are first-class events (Action/Observation), not ad hoc wrappers.
- **Built-in security semantics**: action events include risk labels (`LOW`, `MEDIUM`, `HIGH`) you can enforce in policy.
- **Lifecycle control**: explicit conversation lifecycle with `send_message`, `run`, `finish` and event stream.
- **Portable tool/runtime model**: same agent logic can run local or remote workspace targets.
- **Observability-friendly**: model calls and tool actions are traceable in one runtime.

## Repository Layout

```text
openhands-gepa-sre/
├── target_service/                 # Scenario-driven broken Flask app in Docker
├── openhands_driver/               # OpenHands SDK wrapper + env preflight helpers
├── training_data/                  # Multi-scenario training data for optimization
├── optimize.py                     # GEPA-style + iterative optimization entrypoint
├── run_demo.py                     # Baseline vs optimized runner + security policy flags
├── scripts/demo_sequence.py        # One-command narrated demo flow
├── scripts/approach_scorecard.py   # Baseline/GEPA/iterative comparison table
├── scripts/fanout_sre.py           # Parallel incident fan-out orchestrator
├── tests/                          # Smoke + integration tests
├── pyproject.toml                  # uv project/dependency definition
└── uv.lock                         # Locked dependency graph
```

## Incident Pack

`target_service` supports these scenarios via `SCENARIO=<id>`:

- `stale_lockfile`: `/tmp/service.lock` causes healthcheck `500`
- `bad_env_config`: missing `REQUIRED_API_KEY` causes `500`
- `readiness_probe_fail`: missing `/tmp/ready.flag` causes `500`
- `port_mismatch`: service binds to `5001`, probe expects `5000`

## Real Calls + Observability

`.env` is loaded automatically by `run_demo.py` and `scripts/demo_sequence.py`.

Expected keys:

- `OPENAI_API_KEY` (required for real runs)
- `LMNR_PROJECT_API_KEY` and/or `LAMINI_API_KEY` (optional observability integrations)

Real mode performs env preflight and fails fast if `OPENAI_API_KEY` is missing.

## OpenHands v1 Tooling Requirement

Real tool execution in this demo depends on `openhands-tools` (Terminal/FileEditor).

- Installed via project deps (`uv sync`)
- Loaded at runtime by the wrapper (`register_default_tools(...)`)

If this package is missing, the SDK agent can run with only minimal built-ins (think/finish) and will not execute terminal/file actions.

## Strict Real Mode vs Fallback

`run_demo.py` is strict by default in real mode.

- Default real mode (recommended for truthful demos): fails if SDK execution fails
- Optional fallback mode: allows simulation fallback and reports `fallback_used: True`

Examples:

```bash
# Strict real mode (default)
uv run python run_demo.py --mode optimized --scenario stale_lockfile

# Real mode with explicit fallback allowance
uv run python run_demo.py --mode optimized --scenario stale_lockfile --allow-fallback
```

## Security Policy Controls

`run_demo.py` exposes OpenHands-risk-based controls:

- `--max-security-risk {LOW|MEDIUM|HIGH}`: fail if any action exceeds threshold
- `--require-confirmation-for-risk {LOW|MEDIUM|HIGH}`: require confirmation for risky actions
- `--auto-confirm`: auto-approve when confirmation is required

Example:

```bash
uv run python run_demo.py \
  --mode optimized \
  --optimizer gepa \
  --scenario stale_lockfile \
  --max-security-risk MEDIUM \
  --require-confirmation-for-risk MEDIUM
```

## Optimization Modes

`optimize.py` supports:

- `--optimizer gepa` (search-style candidate selection)
- `--optimizer iterative` (iterative refinement baseline)

Examples:

```bash
uv run python optimize.py --optimizer gepa
uv run python optimize.py --optimizer iterative
```

## Quick Start

```bash
cd openhands-gepa-sre
uv sync
docker build -t openhands-gepa-sre-target:latest target_service
```

## One-Command Demo Sequence

Simulation mode:

```bash
uv run python scripts/demo_sequence.py
```

Real mode:

```bash
uv run python scripts/demo_sequence.py --real
```

## Approach Comparison

```bash
uv run python scripts/approach_scorecard.py --simulate
```

This prints side-by-side metrics for:

- baseline
- optimized-manual
- optimized-gepa
- optimized-iterative

## Fan-Out Orchestration Demo

Stage-friendly narrated run:

```bash
uv run python scripts/fanout_live_demo.py --simulate --mode optimized --optimizer gepa --incidents 12 --concurrency 4
```


Run many incidents in parallel (one-shot batch):

```bash
uv run python scripts/fanout_sre.py --simulate --mode optimized --optimizer gepa --incidents 24 --concurrency 6
```

Run continuous incident intake (simulates an always-on SRE queue):

```bash
uv run python scripts/fanout_sre.py --simulate --continuous --duration-s 30 --arrival-rate 3 --concurrency 6 --optimizer iterative
```

For real calls, drop `--simulate` and keep the same interface:

```bash
uv run python scripts/fanout_sre.py --mode optimized --optimizer gepa --incidents 12 --concurrency 4
```

The fan-out scorecard reports generated/completed incidents, fix rate, average steps, latency, throughput, and scenario mix.

## Key Commands

```bash
cd openhands-gepa-sre
uv sync
uv run python optimize.py --optimizer gepa
uv run python optimize.py --optimizer iterative
uv run python run_demo.py --mode baseline --scenario stale_lockfile --simulate
uv run python run_demo.py --mode optimized --optimizer gepa --scenario stale_lockfile --simulate
uv run python scripts/approach_scorecard.py --simulate
uv run python scripts/fanout_sre.py --simulate --incidents 24 --concurrency 6 --optimizer gepa
uv run python -m unittest discover -s tests -p 'test_*.py' -v
```

## Files to Highlight

- `target_service/app.py`: scenario-specific failure logic
- `target_service/start.sh`: deterministic incident setup
- `openhands_driver/agent_wrapper.py`: OpenHands SDK execution, tools, risk policy checks
- `openhands_driver/runtime_env.py`: `.env` loading + real-mode key preflight
- `optimize.py`: GEPA-style and iterative optimization loops
- `run_demo.py`: mode/optimizer/security controls
- `scripts/demo_sequence.py`: stage-friendly narrative runner
- `scripts/approach_scorecard.py`: comparative evaluation output
- `scripts/fanout_sre.py`: multi-incident fan-out orchestration

## Easiest Real Run

Use the wrapper script that builds the target container, maps it to a safe host port, runs the demo, then cleans up:

```bash
uv run python scripts/start_demo.py --mode optimized --optimizer gepa --scenario stale_lockfile
```

This avoids host `localhost:5000` conflicts by using `http://127.0.0.1:15000` and passing container context to the agent.

Useful options:

```bash
# keep container after run for inspection
uv run python scripts/start_demo.py --keep-container

# skip rebuild if image already exists
uv run python scripts/start_demo.py --skip-build

# run simulation path through same wrapper
uv run python scripts/start_demo.py --simulate
```

## Dashboard UI (Recommended for Multi-Agent Live Runs)

Use a single-screen dashboard instead of interleaved logs:

```bash
uv run python scripts/fanout_dashboard.py --simulate --incidents 12 --concurrency 4 --optimizer gepa
```

Add trace links with a template:

```bash
uv run python scripts/fanout_dashboard.py \
  --simulate \
  --incidents 12 \
  --concurrency 4 \
  --trace-url-template "https://your-trace-ui/runs/{run_id}/incidents/{incident_id}"
```

Template variables:

- `{run_id}`
- `{incident_id}`
- `{trace_key}` (formatted as `{run_id}:{incident_id}`)

## Web Demo UI

If terminal fan-out is hard to follow, use the web frontend:

```bash
uv run python web_demo/app.py
```

Then open:

- `http://127.0.0.1:8008`

Recommended first run in UI:

- `simulate=true`
- `incidents=24`
- `concurrency=4`
- `simulation latency ms=250`

For Laminar links, set Trace URL Template in the UI, for example:

```text
https://laminar.sh/project/bb014595-417a-42b1-be10-70f410cfc81c/traces?pastHours=24&pageNumber=0&traceId={trace_id}
```

Notes:

- In simulation mode there is no real `trace_id`; the UI falls back to `trace_key`.
- For real calls, turn `simulate=false` and ensure `OPENAI_API_KEY` is set.

## Remote Orchestrator + Worker Agents (Production-Style Topology)

Use this script when you want the architecture to mirror a production control plane:

- one orchestrator process
- multiple OpenHands worker agent-server containers
- each incident provisioned inside the assigned worker runtime (no Docker-in-Docker requirement)

```bash
uv run python scripts/fanout_orchestrated_remote.py \
  --mode optimized \
  --optimizer gepa \
  --incidents 6 \
  --concurrency 3
```

What it does:

- starts `N` OpenHands agent-server workers (`--concurrency`)
- assigns incidents by severity
- for each incident, orchestrator prepares a clean runtime in that worker container and starts a broken Flask service
- worker agent remediates via Terminal/FileEditor in its own sandbox
- orchestrator independently verifies health (`curl localhost:5000`) and reports pass/fail
- tears workers down automatically

Useful flags:

```bash
# fast local smoke check without Docker/LLM
uv run python scripts/fanout_orchestrated_remote.py --simulate --incidents 4 --concurrency 2

# keep workers alive for debugging
uv run python scripts/fanout_orchestrated_remote.py --keep-artifacts

# pin agent-server image/version
uv run python scripts/fanout_orchestrated_remote.py --agent-image ghcr.io/openhands/agent-server:1.11.5-python
```

## Extension: Capture Learning into Skills

This repo demonstrates GEPA improving an agent policy (`strategy_hint`).
To make that learning durable for production teams, use this lightweight extension pattern.

1. Persist GEPA output

- Write each optimization result to `artifacts/gepa/best_hint.json`.
- Include: `hint`, `score`, `optimizer`, `timestamp`, `scenario_breakdown`.

2. Log every remediation trajectory

- Append one JSON object per incident to `artifacts/runs/<run_id>.jsonl`.
- Include: `scenario_id`, `tool_actions`, `step_count`, `latency_s`, `service_up`, `trace_key`, `strategy_hint`.

3. Distill successful patterns into a skill

- Generate `skills/sre_incident_runbook/SKILL.md` from top successful trajectories.
- Keep it deterministic and operational, e.g.:
  - check lockfiles first
  - check readiness file
  - check required env vars
  - check bound ports
  - apply minimal fix
  - re-verify with curl

4. Load skill at runtime

- Add a `--skill-file` option and prepend skill content to the worker system prompt.
- Fallback order: `skill` -> `GEPA hint` -> `baseline hint`.

5. Run a closed loop

- Nightly or periodic job:
  - retrain GEPA on recent trajectories
  - update `best_hint.json`
  - refresh `SKILL.md`
  - run regression scenarios and publish scorecard

This keeps GEPA as the optimizer and skills as the durable memory interface for future runs.

## Generalization Beyond Flask

This repository uses Flask incidents so the demo is easy to run locally, but the architecture is domain-agnostic.

- OpenHands provides execution capability in real runtimes (inspect, edit, verify).
- GEPA improves agent policy from observed outcomes.
- The same self-optimizing pattern applies to many problem classes: CVE remediation, CI/CD break/fix, data pipeline recovery, cloud config drift, service reliability incidents, and operational runbook automation.

## How To Add New Scenarios or Problems

To extend this demo to a new failure mode or domain, follow this checklist.

1. Add a new scenario definition

- Update `training_data/scenarios.json` with a new incident type and description.

2. Add deterministic failure behavior

- For Flask-style scenarios, update `target_service/app.py` and `target_service/start.sh`.
- For other domains, replace this target with your own workload setup script/container.

3. Add incident text for the agent

- Add the new scenario to `SCENARIO_ERRORS` in `run_demo.py`.
- Ensure orchestrator scripts can sample/route it (`scripts/fanout_orchestrated_remote.py`, `scripts/fanout_sre.py`).

4. Define success verification

- Extend validation logic in `optimize.py` and orchestrator verification (status/health checks, test commands, or artifact checks).

5. Train/compare policy variants

- Run optimization (`gepa` or `iterative`) and compare with baseline on the new scenario mix.

6. Add tests

- Add simulation smoke coverage in `tests/test_demo.py` or `tests/test_fanout.py`.
- Add integration checks in `tests/test_integration.py` when Docker/runtime validation is needed.

Recommended rule: keep each new scenario deterministic with a clear fail signal and a single measurable success condition. This makes GEPA optimization stable and comparable across runs.
