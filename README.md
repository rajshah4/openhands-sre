# OpenHands SRE Skills Demo

This repository demonstrates a **skills-first SRE agent** built with OpenHands SDK.

Core idea:
- OpenHands is the execution runtime (terminal + file editing in sandboxed workspaces).
- Skills are loaded with OpenHands native APIs (`load_project_skills` + `AgentContext`) from `.agents/skills/`.
- Skills are explicit, auditable runbooks per incident type.
- Optional optimizers (GEPA-style/iterative) are kept as experimental policy-tuning lanes, not the primary abstraction.


## Skill Autonomy + Trace Loop

Runtime behavior is intentionally hybrid:
- The agent can choose whether to apply a loaded skill first or do direct troubleshooting.
- Skills are guidance and structured memory, not a hard lock.
- We pass a preferred skill per incident, but OpenHands can still reason beyond it when needed.

Evaluation loop:
1. Capture traces for every run (actions, observations, outcome, latency, risk, cost).
2. Measure skill performance by scenario (success rate, steps, time, safety).
3. Refine existing skills or create new ones from failed/slow traces.
4. Re-run regression scenarios before promoting updated skills.

This keeps the system operationally transparent while continuously improving over time.

## Why Skills-First

For SRE workflows, skills are easier to operate than prompt-only optimization:
- explicit incident routing
- deterministic runbooks
- transparent auditing/debugging
- natural path to trace-driven improvement

## Repository Layout

```text
openhands-gepa-sre/
├── .agents/skills/                    # Skill library (one SKILL.md per incident class)
├── target_service/                # Scenario-driven broken Flask app in Docker
├── openhands_driver/              # OpenHands SDK wrapper + skill router + env preflight
├── training_data/                 # Scenario examples (legacy optimizer lane)
├── run_demo.py                    # Skills-first demo runner
├── optimize.py                    # Optional GEPA-style / iterative optimization lane
├── scripts/                       # Fan-out, dashboard, and guided demo scripts
├── tests/                         # Smoke + integration tests
├── pyproject.toml                 # uv project/dependency definition
└── uv.lock
```

## Incident Scenarios

`target_service` supports:
- `stale_lockfile`
- `bad_env_config`
- `readiness_probe_fail`
- `port_mismatch`

Matching skills are in:
- `.agents/skills/stale-lockfile/SKILL.md`
- `.agents/skills/bad-env-config/SKILL.md`
- `.agents/skills/readiness-probe-fail/SKILL.md`
- `.agents/skills/port-mismatch/SKILL.md`

## Quick Start

```bash
cd openhands-gepa-sre
uv sync
docker build -t openhands-gepa-sre-target:latest target_service
```

## Main Demo (Skills-First)

Simulation run:

```bash
uv run python run_demo.py \
  --mode optimized \
  --strategy-source skills \
  --scenario stale_lockfile \
  --simulate
```

Real run:

```bash
uv run python run_demo.py \
  --mode optimized \
  --strategy-source skills \
  --scenario stale_lockfile
```

Force a specific skill:

```bash
uv run python run_demo.py \
  --mode optimized \
  --strategy-source skills \
  --skill-id port-mismatch \
  --scenario port_mismatch \
  --simulate
```

## Strategy Sources

`run_demo.py` supports three strategy sources in optimized mode:

- `--strategy-source skills` (default): use skill router + selected SKILL.md context
- `--strategy-source manual`: use fixed optimized prompt hint
- `--strategy-source optimizer`: use optional optimizer lane (`--optimizer gepa|iterative|manual`)

Example optimizer lane (optional):

```bash
uv run python run_demo.py \
  --mode optimized \
  --strategy-source optimizer \
  --optimizer gepa \
  --scenario stale_lockfile \
  --simulate
```

## Real Calls + Observability

`.env` is auto-loaded.

Expected keys:
- `OPENAI_API_KEY` (required for real runs)
- `LMNR_PROJECT_API_KEY` and/or `LAMINI_API_KEY` (optional)

Real mode fails fast if required keys are missing.

## OpenHands Tooling

Real tool execution depends on `openhands-tools` (Terminal/FileEditor), installed via `uv sync`.

## Security Controls


## Production Verification Gate

Real runs now include a stability verifier gate after agent execution:
- requires N consecutive HTTP 200 probes
- bounded by max attempts and probe interval
- `service_up` is only true when both agent output and verifier pass

Relevant flags on `run_demo.py`:
- `--verify-consecutive-successes` (default: `2`)
- `--verify-max-attempts` (default: `6`)
- `--verify-interval-s` (default: `1.5`)

Example:

```bash
uv run python run_demo.py \
  --mode optimized \
  --strategy-source skills \
  --scenario stale_lockfile \
  --verify-consecutive-successes 3 \
  --verify-max-attempts 8
```


`run_demo.py` exposes:
- `--max-security-risk {LOW|MEDIUM|HIGH}`
- `--require-confirmation-for-risk {LOW|MEDIUM|HIGH}`
- `--auto-confirm`

## Easy Real Run Wrapper

```bash
uv run python scripts/start_demo.py --mode optimized --scenario stale_lockfile --allow-local-workspace
```

Useful flags:

```bash
uv run python scripts/start_demo.py --keep-container
uv run python scripts/start_demo.py --skip-build
uv run python scripts/start_demo.py --simulate
```

## Fan-Out Demos

Terminal fan-out:

```bash
uv run python scripts/fanout_live_demo.py --simulate --mode optimized --optimizer gepa --incidents 12 --concurrency 4
```

Continuous intake:

```bash
uv run python scripts/fanout_sre.py --simulate --continuous --duration-s 30 --arrival-rate 3 --concurrency 6 --optimizer iterative
```

Dashboard:

```bash
uv run python scripts/fanout_dashboard.py --simulate --incidents 12 --concurrency 4 --optimizer gepa
```

Web UI:

```bash
uv run python web_demo/app.py
```

Then open `http://127.0.0.1:8008`.

## Remote Orchestrator + Worker Agents

Production-style topology (orchestrator + multiple remote worker agent-servers):

```bash
uv run python scripts/fanout_orchestrated_remote.py \
  --mode optimized \
  --optimizer gepa \
  --incidents 6 \
  --concurrency 3
```

Fast local smoke path:

```bash
uv run python scripts/fanout_orchestrated_remote.py --simulate --incidents 4 --concurrency 2
```

## Optional Optimizer Lane (GEPA/Iterative)

`optimize.py` remains available for experimentation:

```bash
uv run python optimize.py --optimizer gepa
uv run python optimize.py --optimizer iterative
```

Positioning:
- skills are the production-facing abstraction
- optimizers are optional policy-tuning tools once you have robust trace datasets and stable metrics

## How to Add New Scenarios

1. Add a skill: `.agents/skills/<new_scenario>/SKILL.md`
2. Add target failure behavior in `target_service/`
3. Add incident text in `run_demo.py` (`SCENARIO_ERRORS`)
4. Add scenario training example in `training_data/scenarios.json` (optional lane)
5. Add tests in `tests/`


## Structured Trace Logging

Each run is logged as JSONL for offline evaluation and skill improvement.

Default path:
- `artifacts/runs/trace_log.jsonl`

Override/disable:
- `--trace-log <path>`
- `--disable-trace-log`
- `--run-id <id>`

Rows include run metadata, scenario, skill, steps, risks, and verifier output.

Build scorecards from traces:

```bash
uv run python scripts/skill_scorecard.py --trace-log artifacts/runs/trace_log.jsonl
```

## How to Evolve Toward Continual Learning

Recommended progression:
1. Capture every run trace (actions, outcomes, risk, latency, cost)
2. Track skill success/failure per scenario
3. Propose skill updates from failed traces
4. Run regression scenarios before publishing skill changes
5. Use optimizer/fine-tuning only after enough quality data exists

## Tests

```bash
uv run python -m unittest tests/test_demo.py tests/test_fanout.py tests/test_web_demo.py -v
```
