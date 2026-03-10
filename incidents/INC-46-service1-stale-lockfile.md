# Incident Report: INC-46 - Service1 HTTP 500 (Stale Lockfile)

**Date**: 2026-03-02  
**Service**: service1 (health-api)  
**Endpoint**: `/service1`  
**Severity**: Medium  
**Status**: Resolved  

## Summary

Service1 was returning HTTP 500 errors due to a stale lockfile present at `/tmp/service.lock`. The lockfile remained from a previous process crash, preventing the service from starting properly.

## Skill Used

`stale-lockfile` - Diagnose and remediate stale lockfile failures that return HTTP 500 after crashes.

## Timeline

| Time | Event |
|------|-------|
| 2026-03-02T13:38:19 | Incident detected - service1 returning HTTP 500 |
| 2026-03-02T19:38:00 | OpenHands SRE agent engaged |
| 2026-03-02T19:38:00 | Diagnosis confirmed: stale lockfile at `/tmp/service.lock` |
| 2026-03-02T19:38:00 | Remediation executed: lockfile removed |
| 2026-03-02T19:38:00 | Verification complete: service1 returning HTTP 200 |

## Diagnosis

The health endpoint was returning HTTP 500 with error message:
```
stale lockfile present at /tmp/service.lock
```

Logs showed:
```
[ERROR] Service startup blocked by existing lockfile
[ERROR] /tmp/service.lock exists but owning process is not running
[ERROR] Health check failed: stale lockfile present
```

## Root Cause

The service crashed during a previous deployment, leaving behind a lockfile at `/tmp/service.lock`. When the service restarted, it detected the stale lockfile and failed to start, returning HTTP 500 errors.

## Risk Assessment

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `diagnose_service1` | LOW | Read-only diagnostic check |
| `fix_service1` (rm -f /tmp/service.lock) | MEDIUM | Removes temporary file only; auto-approved per AGENTS.md |
| `get_all_service_status` | LOW | Read-only health check |

## Remediation

### Actions Taken

1. **Called `diagnose_service1` MCP tool** (LOW risk)
   - Confirmed stale lockfile exists at `/tmp/service.lock`
   - HTTP status: 500

2. **Called `fix_service1` MCP tool** (MEDIUM risk - auto-approved)
   - Action: `rm -f /tmp/service.lock`
   - Lockfile successfully removed

3. **Called `get_all_service_status` MCP tool** (LOW risk)
   - Verified service1 now returns HTTP 200

## Verification

Post-remediation verification confirmed:
- Service1: HTTP 200 ✅
- Health endpoint returning `{"status": "ok"}`

## Prevention

To prevent similar incidents:

1. **Graceful shutdown handling**: Ensure the service cleans up lockfiles on termination signals (SIGTERM, SIGINT)
2. **Stale lock detection**: Implement PID checking to detect stale locks (lockfile exists but owning process is gone)
3. **Auto-recovery**: Consider implementing automatic stale lock cleanup on startup with appropriate safeguards

## References

- Issue: #46
- Skill: `.agents/skills/stale-lockfile/SKILL.md`
- Service: `target_service/app.py`
