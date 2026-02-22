# OpenHands SRE Skills Demo

This repository demonstrates a **skills-first SRE agent** built with the OpenHands SDK.

Core idea:
- OpenHands is the execution runtime (terminal + file editing in sandboxed workspaces).
- Skills are loaded with OpenHands native APIs (`load_project_skills` + `AgentContext`) from `.agents/skills/`.
- Source of truth for incident runbooks is `.agents/skills/*/SKILL.md`.
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

## Why OpenHands

OpenHands provides production-grade agent infrastructure out of the box. The following features are built into the SDK:

### SDK Features

| Capability | Description |
|------------|-------------|
| Sandboxed execution | Isolated Docker workspaces via `RemoteWorkspace` API |
| Security risk classification | Per-action LOW/MEDIUM/HIGH labels with policy enforcement |
| Confirmation gates | Built-in approval workflows for risky actions |
| Multi-LLM routing | `RouterLLM` supports 100+ providers with cost/capability routing |
| Secret auto-masking | `SecretRegistry` detects and masks credentials automatically |
| Stuck detection | Automatic detection of loops and redundant tool calls |
| Sub-agent delegation | Spawn child agents as native tools |
| Pause/resume | State persistence for long-running or interrupted sessions |
| Context condensation | `LLMSummarizingCondenser` reduces token costs |
| Built-in benchmarks | 15 integrated benchmarks (SWE-Bench, WebArena, GAIA, etc.) |
| VNC/VSCode workspace | Real-time GUI observation and intervention |
| MCP integration | First-class support for Model Context Protocol tools |
| Event-sourced replay | Deterministic replay from immutable event logs |
| Skills from markdown | Native `load_project_skills()` API |

Source: [OpenHands SDK Paper (arXiv:2511.03690)](https://arxiv.org/abs/2511.03690)

### OpenHands Differentiators Used in This Demo

| Feature | How It's Used Here |
|---------|-------------------|
| **Security risk classification** | Every action labeled LOW/MEDIUM/HIGH, enforced via `--max-security-risk` |
| **Confirmation gates** | `--require-confirmation-for-risk MEDIUM` blocks risky actions |
| **Skills system** | `.agents/skills/*/SKILL.md` loaded via `load_project_skills()` + `AgentContext` |
| **Sandboxed execution** | `--remote-host` for isolated agent-server workspace |
| **Event streaming** | Real-time action/observation logging to trace file |
| **Verification gate** | Independent HTTP probes, not agent self-report |
| **Executable skills** | `diagnose.py` + `remediate.py` alongside markdown runbooks |

### OpenHands Features Available for Extension

| Feature | Description | Potential Use |
|---------|-------------|---------------|
| **Multi-LLM routing** | Route by cost/capability via `RouterLLM` | Use cheap model for diagnostics, expensive for complex reasoning |
| **Secret masking** | `SecretRegistry` auto-detects credentials | Prevent API keys in logs/LLM context |
| **Stuck detection** | Automatic loop/redundancy detection | Break infinite diagnostic loops |
| **Sub-agent delegation** | Spawn specialist child agents | Delegate network debugging to NetworkAgent |
| **Pause/resume** | Persist state mid-execution | Human review between diagnosis and remediation |
| **Context condensation** | `LLMSummarizingCondenser` | 2x cost reduction on long incidents |
| **VNC/VSCode access** | Real-time workspace observation | Watch agent work, intervene live |
| **MCP integration** | External tool servers | Add Kubernetes, cloud provider tools |

## Repository Layout

```text
openhands-gepa-sre/
├── .agents/skills/      # Skill library (one SKILL.md per incident class)
├── target_service/      # Scenario-driven broken Flask app in Docker
├── openhands_driver/    # OpenHands SDK wrapper + skill router + env preflight
├── training_data/       # Scenario examples (legacy optimizer lane)
├── run_demo.py          # Skills-first demo runner
├── optimize.py          # Optional GEPA-style / iterative optimization lane
├── scripts/             # Import + benchmark + run helpers
├── tests/               # Smoke + integration tests
├── pyproject.toml       # uv project/dependency definition
└── uv.lock
```

## Incident Scenarios

`target_service` supports:
- `stale_lockfile`
- `readiness_probe_fail`
- `port_mismatch`

Matching skills are in:
- `.agents/skills/stale-lockfile/SKILL.md`
- `.agents/skills/readiness-probe-fail/SKILL.md`
- `.agents/skills/port-mismatch/SKILL.md`

`bad_env_config` remains in the repository as an archived stress/regression scenario,
but it is no longer part of the active demo/default scenario set.

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

Atlas/Arc dataset hook:
- `run_demo.py` and `optimize.py` accept `--training-data <path>` so you can supply an external scenario JSON file
  with the same schema as `training_data/scenarios.json`.
- `scripts/import_itbench_sre.py` can import ITBench SRE incidents directly from
  `itbench-hub/ITBench` into that schema.

Import ITBench SRE scenarios:

```bash
uv run python scripts/import_itbench_sre.py \
  --source https://github.com/itbench-hub/ITBench.git \
  --source-subdir scenarios/sre \
  --output training_data/atlas_sre_scenarios.json
```

Example optimizer lane (optional):

```bash
uv run python run_demo.py \
  --mode optimized \
  --strategy-source optimizer \
  --optimizer gepa \
  --training-data training_data/atlas_sre_scenarios.json \
  --scenario stale_lockfile \
  --simulate
```

Low-cost sampled baseline (dry-run proxy):

```bash
uv run python scripts/benchmark_itbench_sample.py \
  --training-data training_data/atlas_sre_scenarios.json \
  --sample-size 20 \
  --mode optimized \
  --output artifacts/runs/itbench_sample_optimized.json
```

Cost-controlled real-call sampled baseline:

```bash
uv run python scripts/benchmark_itbench_real.py \
  --training-data training_data/atlas_sre_scenarios.json \
  --sample-size 10 \
  --run-timeout-s 90 \
  --subprocess-timeout-s 190 \
  --output artifacts/runs/itbench_real_sample.json
```

Production-style fan-out (multi-incident, concurrent workers):

```bash
uv run python scripts/fanout_itbench.py \
  --training-data training_data/atlas_sre_scenarios.json \
  --sample-size 12 \
  --concurrency 3 \
  --run-timeout-s 90 \
  --subprocess-timeout-s 190 \
  --output artifacts/runs/itbench_fanout.json
```

Local agent-server mode (real sandbox isolation, no cloud dependency):

```bash
# Terminal 1
docker run -p 3000:3000 ghcr.io/openhands/agent-server:latest

# Terminal 2
uv run python run_demo.py \
  --mode optimized \
  --strategy-source skills \
  --scenario stale_lockfile \
  --remote-host http://localhost:3000 \
  --remote-working-dir /workspace/inc-001
```

Low-cost fan-out smoke (no real model calls):

```bash
uv run python scripts/fanout_itbench.py \
  --training-data training_data/atlas_sre_scenarios.json \
  --sample-size 12 \
  --concurrency 4 \
  --simulate \
  --output artifacts/runs/itbench_fanout_sim.json
```

Multi-incident isolation demo (each incident gets its own remote workspace):

```bash
uv run python scripts/fanout_isolated.py \
  --incidents 4 \
  --concurrency 2 \
  --remote-host http://localhost:3000 \
  --output artifacts/runs/fanout_isolated.json
```

## Real Calls + Observability

`.env` is auto-loaded.

Expected keys:
- `OPENAI_API_KEY` (required for real runs)
- `LMNR_PROJECT_API_KEY` and/or `LAMINI_API_KEY` (optional)

Real mode fails fast if required keys are missing.

Laminar observability:
- Laminar tracing is supported when `LMNR_PROJECT_API_KEY` is set.
- Runs still write local structured traces to `artifacts/runs/trace_log.jsonl` for offline analysis.

## OpenHands Tooling

Real tool execution depends on `openhands-tools` (Terminal/FileEditor), installed via `uv sync`.

## Security Controls

Primary controls in real runs:
- action risk classification with `--max-security-risk`
- confirmation gates with `--require-confirmation-for-risk`
- auto-approval toggle with `--auto-confirm`
- human-in-the-loop override with `--interactive` in `scripts/start_demo.py`

## Production Verification Gate

Real runs now include a stability verifier gate after agent execution:
- requires N consecutive HTTP 200 probes
- bounded by max attempts and probe interval
- `service_up` is derived from verifier truth in real mode

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

Security-gates demo (safe simulation):

```bash
uv run python scripts/start_demo.py --demo-security-gates
```

This demonstrates:
- blocking a `HIGH` risk action when `max_security_risk=MEDIUM`
- confirmation-required behavior for `MEDIUM+` risk
- auto-approve behavior with `--auto-confirm`

## Live Intervention Mode

Use `--interactive` to pause before execution and approve, reject, or edit a proposed remediation command.

```bash
uv run python scripts/start_demo.py \
  --mode optimized \
  --scenario stale_lockfile \
  --interactive \
  --allow-local-workspace
```

Example flow:

```text
Agent proposes: docker exec openhands-gepa-demo rm -f /tmp/service.lock

[y]es / [n]o / [e]dit > e
Modified command: docker exec openhands-gepa-demo ls -la /tmp/service.lock
Executing modified command...
```

This keeps a human in the loop while preserving the same run/trace pipeline.

## Executable Skills (Not Just Markdown)

Some skills now include executable helpers alongside `SKILL.md`:

- `.agents/skills/stale-lockfile/diagnose.py`
- `.agents/skills/stale-lockfile/remediate.py`
- `.agents/skills/readiness-probe-fail/diagnose.py`
- `.agents/skills/readiness-probe-fail/remediate.py`

These support a hybrid model where an agent can either:
- follow runbook steps from markdown
- call reusable remediation/diagnostic logic directly

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

## Streamlined Surface

This repo now keeps a smaller active surface focused on:
- `run_demo.py` for incident runs
- `scripts/start_demo.py` for local target bring-up + execution
- `scripts/import_itbench_sre.py` for pulling ITBench scenarios
- `scripts/benchmark_itbench_sample.py` for low-cost dry-run baselines
- `scripts/benchmark_itbench_real.py` for cost-controlled real-call samples
- `scripts/fanout_itbench.py` for concurrent multi-incident execution
- `scripts/fanout_isolated.py` for per-incident remote workspace isolation

Removed from active surface:
- web demo interface (`web_demo/`) has been removed
- older demo/scorecard fanout scripts were retired in favor of ITBench-focused flows

## Production Feature Checklist

- Skills-first incident handling via OpenHands runtime
- Real remote execution via `--remote-host` (agent-server)
- Fan-out concurrency for multiple incidents
- Per-incident isolation via separate remote workspaces
- Security gates with risk thresholding and confirmation policy
- Live intervention mode (`--interactive`) for approve/reject/edit
- Stable post-run verifier gate for real calls
- Laminar tracing + local JSONL trace logging
- Optional optimizer lane retained as experimental, not primary

## Recommended Extensions Now

Highest-value next features for this demo:
- `stuck detection` to break diagnostic loops automatically
- `secret masking` to reduce credential leakage risk in logs/context
- `pause/resume` to support operator handoff during incidents
- `context condensation` to control token cost in long runs

Optional observer feature:
- `VNC/VSCode` is useful for live demos and training, but redundant for core benchmarking when you already have terminal logs + Laminar traces.
- Keep it opt-in (not default) to avoid extra operational complexity.

Observer mode example:

```bash
uv run python scripts/start_demo.py \
  --mode optimized \
  --scenario stale_lockfile \
  --remote-host http://localhost:3000 \
  --remote-working-dir /workspace/inc-001 \
  --vnc
```

`--vnc` enables observer-mode messaging and prints the remote session context for live monitoring.

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

Quick trace summary:

```bash
jq -r '.scenario + \"\\t\" + (.service_up|tostring)' artifacts/runs/trace_log.jsonl \
  | awk -F '\\t' '{k=$1; t[k]++; if($2==\"true\") s[k]++} END {for (k in t) printf \"%s\\truns=%d\\tsuccess=%.2f%%\\n\", k, t[k], (100*s[k]/t[k]) }'
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
uv run python -m unittest discover -s tests -p 'test_*.py' -v
```

## Roadmap: Additional OpenHands Features to Integrate

The following OpenHands capabilities could strengthen this demo further:

### High Priority

| Feature | Description | Implementation |
|---------|-------------|----------------|
| **Cost tracking** | Track tokens and USD per run | Add `input_tokens`, `output_tokens`, `cost_usd` to trace log |
| **Skill leaderboard** | Aggregate trace metrics per skill | Script to summarize success rate, avg steps, avg cost |
| **Side-by-side comparison** | Show with/without OpenHands features | `--compare` flag showing security, sandbox, verification |

### Medium Priority

| Feature | Description | Implementation |
|---------|-------------|----------------|
| **Multi-LLM routing** | Route diagnostics to cheap model, reasoning to expensive | Add `--router-llm` with cost-based routing |
| **Stuck detection** | Break infinite loops automatically | Add `--stuck-detection --max-repeated-actions N` |
| **Failure analysis** | Auto-analyze failed traces, suggest skill updates | Script to identify common failure patterns |
| **Dual-agent mode** | Haiku student + Sonnet teacher for cost reduction | Add `--dual-agent --student-model --teacher-model` |

### Lower Priority (Advanced)

| Feature | Description | Implementation |
|---------|-------------|----------------|
| **Pause/resume** | Save state mid-execution for human review | Add `--pause-after-diagnosis` and `--resume-from` |
| **Secret masking demo** | Show credential detection in action | Scenario with API key that gets auto-masked |
| **MCP integration** | Add external tool servers (K8s, cloud) | Add `--mcp-server` flag for tool extension |
| **Sub-agent delegation** | Spawn specialist agents for subtasks | Add NetworkDebugAgent, LogAnalysisAgent |
| **Context condensation** | Enable summarizer for long incidents | Add `--condense-context` with cost comparison |

### Production Hardening

| Feature | Description | Implementation |
|---------|-------------|----------------|
| **Retry with backoff** | Resilient execution for transient failures | Already partial; extend with configurable backoff |
| **Timeout budgets** | Per-step and total execution budgets | Add `--step-timeout-s` alongside `--run-timeout-s` |
| **Audit logging** | Immutable audit trail for compliance | Write to append-only log with signatures |
| **RBAC integration** | Role-based access for multi-user | Integrate with agent-server auth |

## References

- [OpenHands SDK Paper (arXiv:2511.03690)](https://arxiv.org/abs/2511.03690) - SDK architecture and differentiators
- [OpenHands Platform Paper (arXiv:2407.16741)](https://arxiv.org/abs/2407.16741) - Platform design and benchmarks
- [OpenHands Documentation](https://docs.openhands.dev) - Official docs
- [OpenHands GitHub](https://github.com/All-Hands-AI/OpenHands) - Source code (MIT licensed)
