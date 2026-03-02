# OpenHands SRE Demo

Demonstrates **OpenHands Cloud** integration with **GitHub** for autonomous incident remediation.

> **For full demo instructions, see [DEMO.md](DEMO.md)**

## Real-World Incident Scenarios

The scenarios in this demo are based on [ITBench](https://github.com/itbench-hub/ITBench), a public benchmark for IT automation from IBM Research. These aren't toy examples. They represent real incident patterns that SRE teams face in production.

## What This Demo Shows

1. **GitHub Issue → Automatic Agent** — Create an issue with `openhands` label, agent picks it up
2. **MCP-Based Remediation** — Agent calls remote MCP tools to diagnose and fix live services
3. **Verified Fix** — Agent confirms the service returns HTTP 200 before documenting
4. **PR with Documentation** — Agent creates PR with diagnosis, risk assessment, and MCP tool outputs
5. **Security Policy** — Agent follows risk-level rules in `AGENTS.md` (LOW/MEDIUM auto-approved, HIGH requires human)

## OpenHands Features Highlighted

This demo showcases key OpenHands capabilities:

| Feature | How It's Used | Why It Matters |
|---------|---------------|----------------|
| **GitHub Integration** | Issues with `openhands` label auto-trigger agents | Zero-touch incident response |
| **MCP Tools** | Agent calls remote diagnose/fix tools via MCP server | Live infrastructure remediation from Cloud |
| **Skills System** | `.agents/skills/` contains runbooks with MCP tool sequences | Auditable, version-controlled remediation |
| **Security Policies** | `AGENTS.md` defines LOW/MEDIUM/HIGH risk rules | Governance at scale |
| **Branch Protection** | Agent creates PRs, can't push to main | Human stays in control |

### Skills: More Than Just Documentation

Skills in `.agents/skills/` can include:
- **Markdown runbooks** (`SKILL.md`) - Human-readable, auditable steps
- **Executable code** (`diagnose.py`, `remediate.py`) - Reusable, testable automation
- **Python modules** (`skill.py`) - Import and run programmatically

```
.agents/skills/stale-lockfile/
├── SKILL.md        # Runbook the agent follows
├── diagnose.py     # Executable diagnosis script
├── remediate.py    # Executable remediation script
└── skill.py        # Python module interface
```

### Security: Risk-Based Execution

The agent classifies every action by risk level:

| Risk | Examples | Agent Behavior |
|------|----------|----------------|
| **LOW** | `curl`, `cat`, health checks | Execute immediately |
| **MEDIUM** | `rm -f /tmp/file`, restart service | Execute with justification |
| **HIGH** | `rm -rf`, config changes | **STOP** and request approval |

This is defined in `AGENTS.md` - fully customizable per repository.

## Quick Start

```bash
# 1. Setup the demo environment
./scripts/setup_demo.sh

# 2. Start the MCP server (bridges Cloud to local Docker)
uv run python mcp_server/server.py

# 3. Expose via Tailscale Funnel
tailscale funnel --set-path / 15000     # demo service
tailscale funnel --set-path /mcp 8080   # MCP server

# 4. Configure OpenHands Cloud with your MCP URL:
#    https://your-machine.tailnet.ts.net/mcp

# 5. Break a service and create an issue
docker exec openhands-gepa-demo touch /tmp/service.lock
export DEMO_TARGET_URL=https://your-machine.tailnet.ts.net
uv run python scripts/create_demo_issue.py --scenario stale_lockfile

# 6. Watch OpenHands Cloud fix it live via MCP tools
#    https://app.all-hands.dev
```

### Verify MCP Pipeline

```bash
# Test agent runs diagnose → fix → verify for all broken services
uv run python scripts/test_mcp_agent.py
uv run python scripts/test_mcp_agent.py --url https://your-machine.tailnet.ts.net/mcp
```

## Repository Layout

```
openhands-sre/
├── .agents/skills/           # Incident runbooks with MCP tool sequences
│   ├── stale-lockfile/       #   service1: rm lockfile
│   ├── readiness-probe-fail/ #   service2: create ready flag
│   ├── bad-env-config/       #   service3: env var fix
│   └── port-mismatch/        #   port binding issues
├── mcp_server/
│   └── server.py             # MCP server (streamable HTTP + SSE)
├── target_service/           # Docker service with breakable scenarios
├── scripts/
│   ├── setup_demo.sh         # Setup Docker + Tailscale
│   ├── create_demo_issue.py  # Create GitHub issues
│   ├── test_mcp_agent.py     # Test MCP pipeline end-to-end
│   └── fix_demo.sh           # Manual fix fallback
├── tests/                    # Integration tests
├── AGENTS.md                 # Security policy + MCP tool instructions
├── DEMO.md                   # Full demo guide
└── README.md
```

## Scenarios

| Path | Scenario | Break | MCP Fix | Manual Fix |
|------|----------|-------|---------|------------|
| `/service1` | Stale lockfile | `docker exec openhands-gepa-demo touch /tmp/service.lock` | `fix_service1` | `./scripts/fix_demo.sh service1` |
| `/service2` | Readiness probe | (broken by default) | `fix_service2` | `./scripts/fix_demo.sh service2` |
| `/service3` | Bad env config | (broken by default) | `fix_service3` (instructions) | `./scripts/fix_demo.sh service3` |

## Security Policy

The `AGENTS.md` file controls agent behavior:

| Risk Level | Action |
|------------|--------|
| **LOW** | Auto-execute (health checks, reading files) |
| **MEDIUM** | Execute with reporting (removing temp files) |
| **HIGH** | Stop and request human approval |

## Requirements

- Docker
- [GitHub CLI (`gh`)](https://cli.github.com/) - installed and authenticated
- GitHub repo connected to OpenHands Cloud
- Tailscale Funnel (for public URL exposure)

## Tests

```bash
uv run python -m unittest discover -s tests -p 'test_*.py' -v
```

## Acknowledgments

- Incident scenarios based on [ITBench](https://github.com/itbench-hub/ITBench) from IBM Research
- Built with [OpenHands](https://github.com/All-Hands-AI/OpenHands) - the open platform for AI software developers
