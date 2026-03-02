---
name: readiness-probe-fail
description: Resolve readiness probe failures when startup appears successful but health checks fail.
triggers:
  - readiness_probe_fail
  - readiness
  - ready.flag
  - probe fail
  - service2
---

# Readiness Probe Recovery

**Applies to**: service2 (`/service2` endpoint)
**Risk Level**: LOW

## MCP Tools (Preferred)
If MCP tools are available, use them:
- `diagnose_service2` - Check if ready flag exists and service health
- `fix_service2` - Create the readiness flag

## Manual Execution
If MCP tools are not available, use these commands:

### Diagnostic Workflow
1. Verify failure: `curl -i $TARGET_URL/service2`
2. Check ready flag: `docker exec openhands-gepa-demo ls -la /tmp/ready.flag`

### Remediation Workflow (LOW Risk)
1. Create ready flag: `docker exec openhands-gepa-demo touch /tmp/ready.flag`
2. Verify fix: `curl -i $TARGET_URL/service2`

### Verification
1. `curl -i $TARGET_URL/service2` returns HTTP 200
2. Response contains `"status": "ok"`
3. Ready flag exists
