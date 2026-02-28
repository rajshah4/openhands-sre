# OpenHands SRE Demo Guide

This guide covers all demo scenarios for showcasing OpenHands Cloud + GitHub integration with security policy enforcement.

## Quick Reference

| Demo | Command | Shows |
|------|---------|-------|
| LOW Risk | `uv run python scripts/create_demo_issue.py --scenario readiness_probe_fail` | Auto-fix, minimal reporting |
| MEDIUM Risk | `uv run python scripts/create_demo_issue.py --scenario stale_lockfile` | Fix with risk justifications |
| HIGH Risk | `uv run python scripts/create_demo_issue.py --scenario corrupted_data_store` | STOP, request human approval |
| Security Gates | `uv run python scripts/start_demo.py --demo-security-gates` | Policy enforcement simulation |
| Local Remediation | `uv run python scripts/start_demo.py --mode optimized --scenario stale_lockfile --allow-local-workspace` | Live Docker fix |

---

## Part 0: Live Service Demo (Visual Before/After)

The target service shows **pretty HTML status pages** in the browser:
- **Broken**: Red page with ❌ icon and error details
- **Fixed**: Green page with ✅ icon and success message

### Tailscale Funnel URL

The local Docker container is exposed to the internet via Tailscale:

**https://macbook-pro.tail21d104.ts.net/**

### Quick Visual Demo

```bash
# 1. Run setup script
./scripts/setup_demo.sh

# 2. Break service1 (stale lockfile)
docker exec openhands-gepa-demo touch /tmp/service.lock

# 3. Open browser - see RED error page
open https://macbook-pro.tail21d104.ts.net/service1

# 4. Fix it
docker exec openhands-gepa-demo rm -f /tmp/service.lock

# 5. Refresh browser - see GREEN success page
```

### Quick Setup

Run the setup script to build and start everything:

```bash
./scripts/setup_demo.sh
```

This will:
- Build the Docker image
- Start the container on port 15000
- Check Tailscale status
- Print all the URLs and commands you need

### Multi-Scenario Mode (Recommended)

Run **without** the SCENARIO env var to get all scenarios at different paths:

```bash
docker run -d -p 15000:5000 --name openhands-gepa-demo openhands-gepa-sre-target:latest
```

| Path | Scenario | Break Command | Fix Command |
|------|----------|---------------|-------------|
| `/` | Index page | - | - |
| `/service1` | stale_lockfile | `docker exec openhands-gepa-demo touch /tmp/service.lock` | `docker exec openhands-gepa-demo rm -f /tmp/service.lock` |
| `/service2` | readiness_probe_fail | (broken by default) | `docker exec openhands-gepa-demo touch /tmp/ready.flag` |
| `/service3` | bad_env_config | (broken by default) | Restart with `-e REQUIRED_API_KEY=xxx` |

### Single-Scenario Mode (Legacy)

Run with SCENARIO env var to get one scenario at `/`:

| Scenario | Start Command | Fix Command |
|----------|---------------|-------------|
| `stale_lockfile` | `-e SCENARIO=stale_lockfile` | `docker exec openhands-gepa-demo rm -f /tmp/service.lock` |
| `readiness_probe_fail` | `-e SCENARIO=readiness_probe_fail` | `docker exec openhands-gepa-demo touch /tmp/ready.flag` |

### Tailscale Setup (One-Time)

```bash
# Start Tailscale and enable Funnel
tailscale up
tailscale funnel 15000
```

**Note**: Your Mac must be on for the Tailscale Funnel to work.

---

## Part 1: OpenHands Cloud + GitHub Integration

### The Outer Loop Story

```
GitHub Issue --> OpenHands Cloud --> Agent Runs --> PR Created
     ^                                                   |
     |_________________ Human Reviews __________________|
```

### Setup Requirements

1. Repository connected to OpenHands Cloud
2. `openhands` label created in GitHub repo
3. OpenHands Cloud has access to the repository
4. Tailscale Funnel running (for live service demo)
5. Branch protection on `main` (agent must create PRs, can't push directly)

### How to Demo

1. **Start broken service** (browser shows red error page):
   ```bash
   docker rm -f openhands-gepa-demo
   docker run -d -p 15000:5000 -e SCENARIO=stale_lockfile --name openhands-gepa-demo openhands-gepa-sre-target:latest
   ```

2. **Create an issue** (choose one method):

   **Option A: Use the script**
   ```bash
   uv run python scripts/create_demo_issue.py --scenario stale_lockfile
   ```

   **Option B: Create manually in GitHub**
   - Go to https://github.com/rajshah4/openhands-sre/issues/new
   - Title: `Service health check failing at /lockfile endpoint`
   - Body:
     ```
     The health check at https://macbook-pro.tail21d104.ts.net/lockfile is returning HTTP 500.
     
     Please diagnose and fix following the security policy in AGENTS.md.
     ```
   - **Add the `openhands` label** ← This triggers OpenHands Cloud

3. **Watch OpenHands Cloud**:
   - Go to https://app.all-hands.dev
   - See the conversation start automatically
   - Agent curls the Tailscale URL and sees the error

4. **Check GitHub**:
   - Issue gets a comment from `@openhands-ai`
   - PR is created with fix + tests
   - PR links back to the issue

5. **Manually verify the fix** (since Cloud can't docker exec):
   ```bash
   docker exec openhands-gepa-demo rm -f /tmp/service.lock
   ```
   Refresh browser - green success page!

### Demo Narrative

> "Watch this: I create a GitHub issue describing an incident. OpenHands Cloud picks it up automatically - no human triggers it. The agent reads our runbooks, diagnoses the problem via the public URL, documents the fix, and opens a PR. Notice it can't push directly to main - branch protection requires a PR, so humans stay in control. In a self-hosted deployment, it would execute the fix directly."

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

### Demo Scenario: HIGH Risk

**Command**:
```bash
uv run python scripts/create_demo_issue.py --scenario corrupted_data_store
```

**What happens**:
- Agent recognizes `rm -rf` would be needed (HIGH risk)
- Agent **STOPS** - does not execute destructive commands
- Creates a skill with human approval template
- PR includes approval workflow

**What to show**:
- Agent did NOT execute `rm -rf`
- Created structured approval request
- Human must approve before remediation

**Demo Narrative**:
> "This is the critical difference. The agent recognizes this would require `rm -rf` - a HIGH risk action. Instead of executing it, the agent STOPS and creates an approval request. No destructive action without human consent."

---

## Part 3: Security Gates Simulation (Local)

### Command

```bash
uv run python scripts/start_demo.py --demo-security-gates
```

### What It Shows

Three policy configurations tested against two actions:

| Action | Risk | max_security_risk=MEDIUM | require_confirmation=MEDIUM | auto_confirm=True |
|--------|------|--------------------------|-----------------------------|--------------------|
| `rm -rf /tmp/*` | HIGH | BLOCKED | BLOCKED | ALLOWED |
| `rm -f /tmp/service.lock` | LOW | ALLOWED | ALLOWED | ALLOWED |

### Demo Narrative

> "Every action the agent takes is security-classified. Enterprise admins can set policies:
> - Block dangerous actions entirely
> - Require human approval for risky operations  
> - Auto-approve for trusted workflows
> 
> This is what an Agent Control Plane gives you - governance at scale."

---

## Part 4: Scale Demo (Multiple Issues)

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

## Part 5: Local Live Remediation

### Setup

```bash
# Build the target service
docker build -t openhands-gepa-sre-target:latest target_service
```

### Run

```bash
uv run python scripts/start_demo.py \
  --mode optimized \
  --scenario stale_lockfile \
  --allow-local-workspace
```

### What It Shows

- Real Docker container with broken service
- Agent actually fixes it
- HTTP 500 becomes HTTP 200

### When to Use

- When you need to prove the agent can fix real things
- When Cloud/GitHub integration is not available
- For deep-dive technical audience

---

## Observability

### Local Traces

Every run logs structured traces:

```bash
cat artifacts/runs/trace_log.jsonl | tail -1 | jq '{security_risks, max_security_risk_seen}'
```

### Laminar Integration

Set `LMNR_PROJECT_API_KEY` in environment or OpenHands Cloud secrets.

**Note**: OpenHands Cloud may have network restrictions on port 8443 to `api.lmnr.ai`. For full observability, use local demos.

---

## Full Demo Script (5 Minutes)

### Opening (30 sec)
> "Let me show you the Agent Control Plane for SRE."

### Part 1: Outer Loop (2 min)
```bash
uv run python scripts/create_demo_issue.py --scenario stale_lockfile
```
> "GitHub issue to OpenHands Cloud to PR. Fully autonomous."

Show: Issue comment, Cloud conversation, PR created

### Part 2: Security Policy (2 min)
```bash
uv run python scripts/create_demo_issue.py --scenario corrupted_data_store
```
> "But what about dangerous actions?"

Show: Agent STOPPED, approval request created

### Part 3: Scale Story (30 sec)
> "This same setup handles 100s of incidents per month. Same skills. Same policies. Same audit trail."

### Closing
> "Questions?"

---

## Troubleshooting

### Issue not picked up by Cloud
- Check `openhands` label is on the issue
- Verify Cloud has access to the repo
- Check Cloud dashboard for any errors

### Security policy not followed
- Verify `AGENTS.md` is committed and pushed
- Agent reads it at conversation start

### Laminar traces not appearing
- Check `LMNR_PROJECT_API_KEY` is set correctly
- OpenHands Cloud may block port 8443 (use local demo instead)
