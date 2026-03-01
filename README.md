# OpenHands SRE Demo

Demonstrates **OpenHands Cloud** integration with **GitHub** for autonomous incident remediation.

> **For full demo instructions, see [DEMO.md](DEMO.md)**

## What This Demo Shows

1. **GitHub Issue → Automatic Agent** - Create an issue with `openhands` label, agent picks it up
2. **Live Service Diagnosis** - Agent curls a real broken service via public URL
3. **PR with Documentation** - Agent creates PR with diagnosis, risk assessment, and fix
4. **Security Policy** - Agent follows rules in `AGENTS.md` based on risk level

## Quick Start

```bash
# 1. Setup the demo environment
./scripts/setup_demo.sh

# 2. Break service1
docker exec openhands-gepa-demo touch /tmp/service.lock

# 3. Create an issue (triggers OpenHands Cloud)
export DEMO_TARGET_URL=https://your-machine.tailnet.ts.net
uv run python scripts/create_demo_issue.py --scenario stale_lockfile

# 4. Watch OpenHands Cloud diagnose and create PR
# https://app.all-hands.dev

# 5. Execute the fix (simulates self-hosted)
./scripts/fix_demo.sh service1
```

## Demo Narrative

**Code bugs** → Cloud creates a PR, you merge it, CI/CD deploys. Done.

**Operational issues** → Need direct infrastructure access. Self-hosted OpenHands runs commands directly.

> "Cloud handles code fixes through PRs. Self-hosted goes further - it can actually run the commands to fix your infrastructure. That's what enterprises need."

## Repository Layout

```
openhands-sre/
├── .agents/skills/      # Incident runbooks (SKILL.md per scenario)
├── target_service/      # Docker service with breakable scenarios
├── scripts/
│   ├── setup_demo.sh    # Setup script
│   ├── create_demo_issue.py  # Create GitHub issues
│   └── fix_demo.sh      # Execute fixes (simulates self-hosted)
├── tests/               # Integration tests
├── AGENTS.md            # Security policy for OpenHands
├── DEMO.md              # Full demo instructions
└── README.md
```

## Scenarios

| Path | Scenario | Break | Fix |
|------|----------|-------|-----|
| `/service1` | Stale lockfile | `docker exec openhands-gepa-demo touch /tmp/service.lock` | `./scripts/fix_demo.sh service1` |
| `/service2` | Readiness probe | (broken by default) | `./scripts/fix_demo.sh service2` |
| `/service3` | Bad env config | (broken by default) | `./scripts/fix_demo.sh service3` |

## Security Policy

The `AGENTS.md` file controls agent behavior:

| Risk Level | Action |
|------------|--------|
| **LOW** | Auto-execute (health checks, reading files) |
| **MEDIUM** | Execute with reporting (removing temp files) |
| **HIGH** | Stop and request human approval |

## Requirements

- Docker
- GitHub repo connected to OpenHands Cloud
- Tailscale Funnel (for public URL exposure)

## Tests

```bash
uv run python -m unittest discover -s tests -p 'test_*.py' -v
```
