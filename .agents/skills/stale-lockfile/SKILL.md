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

## Overview

A stale lockfile occurs when a service crashes or is killed without properly releasing its lock. The lockfile at `/tmp/service.lock` prevents the service from starting, causing HTTP 500 errors. This is a common issue after:
- Container restarts or crashes
- OOM kills
- Deployments that don't clean up properly

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

## Python API

You can also use the Python functions directly:

```python
from diagnose import diagnose
from remediate import remediate

# Diagnose the issue
result = diagnose(
    target_url="http://127.0.0.1:15000/service1",
    target_container="openhands-gepa-demo",
    lock_path="/tmp/service.lock"
)

if result["is_stale_lockfile_candidate"]:
    # Fix the issue
    fix_result = remediate(
        target_url="http://127.0.0.1:15000/service1",
        target_container="openhands-gepa-demo",
        lock_path="/tmp/service.lock"
    )
    print(f"Fixed: {fix_result['fixed']}")
```

## Troubleshooting

### Issue: HTTP 500 persists after removing lockfile
- Check if the service process is actually running: `docker exec openhands-gepa-demo ps aux | grep python`
- Verify the lockfile was actually removed: `docker exec openhands-gepa-demo ls -la /tmp/service.lock`
- Check for other error conditions in logs: `docker logs openhands-gepa-demo`

### Issue: Lockfile keeps reappearing
- The service may be crashing in a loop
- Check container logs for startup errors
- Verify service dependencies are available

### Issue: Cannot connect to container
- Ensure the container is running: `docker ps | grep openhands-gepa-demo`
- Check container health: `docker inspect openhands-gepa-demo`

## Security Considerations

| Action | Risk Level | Rationale |
|--------|------------|-----------|
| `curl -i $TARGET_URL/service1` | LOW | Read-only health check |
| `docker exec ... ls -la /tmp/service.lock` | LOW | Read-only file check |
| `docker exec ... rm -f /tmp/service.lock` | MEDIUM | Removes temp file only, service unaffected |

The lockfile is located in `/tmp/` and is specifically designed to be removable when stale. Removing it does not affect service state or data - it only allows the service to proceed with its health check.
