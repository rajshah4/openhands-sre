# OpenHands SRE Demo Guide

This guide covers all demo scenarios for showcasing OpenHands Cloud + GitHub integration with MCP-based incident remediation and security policy enforcement.

## Quick Reference

| Demo | Command | Shows |
|------|---------|-------|
| MEDIUM Risk | `uv run python scripts/create_demo_issue.py --scenario stale_lockfile` | Agent calls MCP tools to fix live service |
| LOW Risk | `uv run python scripts/create_demo_issue.py --scenario readiness_probe_fail` | Auto-fix, minimal reporting |
| HIGH Risk | `uv run python scripts/create_demo_issue.py --scenario corrupted_data_store` | STOP, request human approval (no execution) |
| Test Agent | `uv run python scripts/test_mcp_agent.py` | Verify MCP pipeline works end-to-end |
| Manual Fix | `./scripts/fix_demo.sh service1` | Manual fallback (no MCP needed) |

---

## Architecture

```
GitHub Issue ──→ OpenHands Cloud ──→ MCP Server ──→ Docker Container
  (openhands        (reads skills,       (port 8080,        (openhands-gepa-demo,
   label)           calls MCP tools)     Tailscale Funnel)    port 15000)
```

The MCP server runs on your machine and exposes diagnose/fix tools over the network.
OpenHands Cloud calls these tools remotely to fix live services — no shell access needed.

---

## Setup

### 1. Start the Demo Environment

```bash
./scripts/setup_demo.sh
```

This builds the Docker image, starts the container on port 15000, and checks Tailscale.

### 2. Start the MCP Server

```bash
uv run python mcp_server/server.py
```

The MCP server runs on port 8080 and exposes 7 tools (diagnose/fix for 3 services + status check). It supports both **streamable HTTP** (`/mcp`) and **SSE** (`/sse`) transports.

### 3. Expose via Tailscale Funnel

```bash
# Expose both the demo service and MCP server
tailscale funnel --set-path / 15000    # Demo service at /
tailscale funnel --set-path /mcp 8080  # MCP server at /mcp

# Verify
tailscale funnel status
```

Your URLs:
- **Demo service**: `https://your-machine.tailnet.ts.net/service1`
- **MCP server**: `https://your-machine.tailnet.ts.net/mcp`

### 4. Configure OpenHands Cloud

1. Go to [app.all-hands.dev](https://app.all-hands.dev) → **Settings → MCP**
2. Add your MCP URL: `https://your-machine.tailnet.ts.net/mcp`
3. Cloud will connect using streamable HTTP transport (auto-appends `/sse` for SSE fallback)

### 5. Verify MCP Works

```bash
# Quick test — calls diagnose/fix/verify for all broken services
uv run python scripts/test_mcp_agent.py

# Test through Tailscale (same path Cloud uses)
uv run python scripts/test_mcp_agent.py --url https://your-machine.tailnet.ts.net/mcp
```

---

## Services & Scenarios

| Path | Scenario | Break Command | MCP Fix | Manual Fix |
|------|----------|---------------|---------|------------|
| `/service1` | Stale lockfile | `docker exec openhands-gepa-demo touch /tmp/service.lock` | `fix_service1` | `./scripts/fix_demo.sh service1` |
| `/service2` | Readiness probe | (broken by default) | `fix_service2` | `./scripts/fix_demo.sh service2` |
| `/service3` | Bad env config | (broken by default) | `fix_service3` (instructions only) | `./scripts/fix_demo.sh service3` |

### MCP Tools

| Tool | What it does (remotely) | Risk |
|------|------------------------|------|
| `get_all_service_status` | HTTP health check of all 3 services | LOW |
| `diagnose_service1` | Check if `/tmp/service.lock` exists | LOW |
| `diagnose_service2` | Check if `/tmp/ready.flag` exists | LOW |
| `diagnose_service3` | Check if `REQUIRED_API_KEY` is set | LOW |
| `fix_service1` | Remove `/tmp/service.lock` | MEDIUM (auto-approved) |
| `fix_service2` | Create `/tmp/ready.flag` | LOW |
| `fix_service3` | Return restart instructions | MEDIUM |

---

## Part 1: Live Remediation via MCP (Primary Demo)

### The Full Loop

```
GitHub Issue ──→ OpenHands Cloud ──→ MCP: diagnose ──→ MCP: fix ──→ MCP: verify ──→ PR Created
  (openhands        (reads skills,        (confirms       (executes      (confirms      (documents
   label)           calls tools)          root cause)      fix remotely)  HTTP 200)      incident)
```

### Prerequisites

1. Repository connected to OpenHands Cloud
2. `openhands` label created in GitHub repo
3. MCP server running and exposed via Tailscale Funnel (see Setup above)
4. MCP URL configured in OpenHands Cloud settings
5. Branch protection on `main` (agent creates PRs, can't push directly)

### How to Demo

1. **Break service1** (browser shows red error page):
   ```bash
   docker exec openhands-gepa-demo touch /tmp/service.lock
   open https://your-machine.tailnet.ts.net/service1  # RED ❌ page
   ```

2. **Create an incident issue**:
   ```bash
   export DEMO_TARGET_URL=https://your-machine.tailnet.ts.net
   uv run python scripts/create_demo_issue.py --scenario stale_lockfile
   ```

3. **Watch OpenHands Cloud** at [app.all-hands.dev](https://app.all-hands.dev):
   - Agent picks up the issue automatically
   - Reads the `stale-lockfile` skill from `.agents/skills/`
   - Calls `get_all_service_status` → confirms service1 HTTP 500
   - Calls `diagnose_service1` → confirms stale lockfile
   - **Calls `fix_service1`** → removes lockfile remotely via MCP
   - Calls `get_all_service_status` → confirms service1 HTTP 200
   - Creates PR documenting the incident

4. **Refresh browser** — see GREEN ✅ page! The service is fixed.

5. **Check GitHub** — PR created with full incident report, risk assessment, and MCP tool outputs.

### Demo Narrative

**Opening:**
> "Let me show you autonomous incident remediation. I'll break a service, create a GitHub issue, and watch OpenHands fix it — no human in the loop."

**During the demo:**
> "The agent reads our runbook skills, connects to our MCP server via Tailscale, and calls the fix tool remotely. The MCP server runs on my machine and has Docker access to the container. The agent never touches Docker directly — it just calls API-like tools."

**After the fix:**
> "Service is green. The agent diagnosed the issue, fixed it live, verified the fix, and documented everything in a PR. Same skills, same policies, at enterprise scale."

---

## Part 2: Security Policy Enforcement

### The Three Risk Levels

| Level | Example Actions | Agent Behavior |
|-------|-----------------|----------------|
| **LOW** | `curl`, `ls`, `cat`, health checks | Execute immediately |
| **MEDIUM** | `rm -f /tmp/file`, `touch`, restart service | Execute with risk table |
| **HIGH** | `rm -rf`, config changes, data deletion | **STOP and request approval** |

### Demo Scenario: LOW Risk

**Command**:
```bash
uv run python scripts/create_demo_issue.py --scenario readiness_probe_fail
```

**What happens**:
- Agent creates `/tmp/ready.flag` (LOW risk)
- Response is straightforward
- PR created with tests

**What to show**:
- Simple risk table in response
- Fast resolution

### Demo Scenario: MEDIUM Risk

**Command**:
```bash
uv run python scripts/create_demo_issue.py --scenario stale_lockfile
```

**What happens**:
- Agent removes `/tmp/service.lock` (MEDIUM risk)
- Response includes detailed risk table with justifications
- PR created with tests

**What to show**:
- Risk table in the GitHub comment:
  ```
  | Action | Risk | Rationale |
  |--------|------|-----------|
  | rm -f /tmp/service.lock | MEDIUM | Removes temp lockfile only |
  ```

**Demo Narrative**:
> "Notice how the agent reports the security risk level for each action. For MEDIUM risk, it explains why the action is safe - removing a temp file, not production data."

### Demo Scenario: HIGH Risk (Human-Only)

**Command**:
```bash
uv run python scripts/create_demo_issue.py --scenario corrupted_data_store
```

**What happens**:
- Agent recognizes `rm -rf` would be needed (HIGH risk)
- Agent **STOPS** - does not execute destructive commands
- Agent requests human approval with a clear checklist
- No automated remediation is performed

**What to show**:
- Agent did NOT execute `rm -rf`
- Human approval is required before any remediation
- This is a governance demo (policy enforcement), not automation

**Demo Narrative**:
> "This is the critical difference. The agent recognizes this would require `rm -rf` - a HIGH risk action. Instead of executing it, the agent STOPS and asks for human approval. No destructive action without human consent."

---

## Part 3: Scale Demo (Multiple Issues)

### Create Multiple Issues

```bash
uv run python scripts/create_demo_issue.py --scenario stale_lockfile
uv run python scripts/create_demo_issue.py --scenario readiness_probe_fail
uv run python scripts/create_demo_issue.py --scenario stale_lockfile
```

### What to Show

- OpenHands Cloud handles multiple conversations in parallel
- Each issue gets its own agent run
- All create PRs independently

### Demo Narrative

> "In production, this handles hundreds of incidents. Same skills. Same policies. Same audit trail. That's the Agent Control Plane."

---

## Full Demo Script (5 Minutes)

### Opening (30 sec)
> "Let me show you the Agent Control Plane for SRE."

### Part 1: Live Fix via MCP (2.5 min)
```bash
docker exec openhands-gepa-demo touch /tmp/service.lock
export DEMO_TARGET_URL=https://your-machine.tailnet.ts.net
uv run python scripts/create_demo_issue.py --scenario stale_lockfile
```
> "I just broke the service. Now I create a GitHub issue. Watch: OpenHands picks it up, reads the runbook skill, calls the MCP fix tool, and the service goes green — all autonomous."

Show: Issue → Cloud conversation → MCP tool calls → service goes green → PR created

### Part 2: Human Approval for High Risk (2 min)
```bash
uv run python scripts/create_demo_issue.py --scenario corrupted_data_store
```
> "Now a HIGH risk incident. The agent identifies the risk and stops for human approval. No destructive actions are executed."

Show: Agent STOPPED, approval request, explicit human-only remediation

### Closing (30 sec)
> "Same skills, same policies, same audit trail — at enterprise scale. Questions?"

---

## Troubleshooting

### Issue not picked up by Cloud
- Check `openhands` label is on the issue
- Verify Cloud has access to the repo at [app.all-hands.dev](https://app.all-hands.dev)

### Agent diagnoses but doesn't fix
- Verify skills in `.agents/skills/` say "Call the fix tool NOW" (not "if available")
- Verify `AGENTS.md` MCP section explains tools execute remotely
- Check MCP server is running: `curl http://127.0.0.1:8080/`

### MCP tools not connecting
- Verify MCP server is running: `uv run python mcp_server/server.py`
- Verify Tailscale Funnel: `tailscale funnel status`
- Test MCP end-to-end: `uv run python scripts/test_mcp_agent.py --url https://your-machine.tailnet.ts.net/mcp`
- Check MCP server logs: `tail -f /tmp/mcp_server.log`

### Security policy not followed
- Verify `AGENTS.md` is committed and pushed
- Agent reads it at conversation start
