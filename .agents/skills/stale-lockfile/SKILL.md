---
name: stale-lockfile
description: Diagnose and remediate stale lockfile failures that return HTTP 500 after crashes.
triggers:
  - stale_lockfile
  - stale lock
  - lockfile
  - service.lock
  - service1
---

# Stale Lockfile Recovery

**Applies to**: service1 (`/service1` endpoint)
**Risk Level**: MEDIUM

## MCP Tools (Preferred)
If MCP tools are available, use them:
- `diagnose_service1` - Check if lockfile exists and service health
- `fix_service1` - Remove the stale lockfile

## Manual Execution
If MCP tools are not available, use these commands:

### Diagnostic Workflow
1. Verify failure: `curl -i $TARGET_URL/service1`
2. Check lockfile: `docker exec openhands-gepa-demo ls -la /tmp/service.lock`
3. Check lock owner if available: `docker exec openhands-gepa-demo fuser /tmp/service.lock`

### Remediation Workflow (MEDIUM Risk)
1. Remove stale lock: `docker exec openhands-gepa-demo rm -f /tmp/service.lock`
2. Verify fix: `curl -i $TARGET_URL/service1`

### Verification
1. `curl -i $TARGET_URL/service1` returns HTTP 200
2. Response contains `"status": "ok"`
3. Lock file is absent
