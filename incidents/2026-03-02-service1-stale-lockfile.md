# Incident Report: Service1 HTTP 500 - Stale Lockfile

**Date**: 2026-03-02  
**Time Detected**: 10:20:41 UTC  
**Service**: service1 (health-api)  
**Endpoint**: `/service1`  
**Severity**: Medium  
**Status**: Resolved  

## Summary

Service1 was returning HTTP 500 errors due to a stale lockfile at `/tmp/service.lock`. The lockfile was left behind after a previous service crash, preventing the health check from passing.

## Skill Used

`stale-lockfile` - Located at `.agents/skills/stale-lockfile/`

## Symptoms

- Health endpoint returning 500 status code
- Error message: "stale lockfile present at /tmp/service.lock"
- Service was healthy before last deployment

## Root Cause

The service crashed or was terminated without releasing its lockfile at `/tmp/service.lock`. When the service restarted, it detected the existing lockfile and assumed another instance was running, causing it to fail its health check with HTTP 500.

## Diagnosis

### Actions Taken

| Action | Risk | Rationale |
|--------|------|-----------|
| `curl -i $TARGET_URL/service1` | LOW | Read-only health check to verify failure |
| `docker exec openhands-gepa-demo ls -la /tmp/service.lock` | LOW | Read-only file check to confirm lockfile exists |

### Findings

1. HTTP endpoint returned 500 with error "stale lockfile present"
2. Lockfile `/tmp/service.lock` was present in the container
3. No active process owned the lockfile (stale)

## Remediation

### Actions Taken

| Action | Risk | Rationale |
|--------|------|-----------|
| `docker exec openhands-gepa-demo rm -f /tmp/service.lock` | MEDIUM | Removes temp lockfile only, service state unaffected |
| `curl -i $TARGET_URL/service1` | LOW | Verify fix was successful |

### Result

Service returned to healthy state (HTTP 200) after removing the stale lockfile.

## Verification

1. ✅ `curl -i $TARGET_URL/service1` returns HTTP 200
2. ✅ Response contains `"status": "ok"`
3. ✅ Lockfile `/tmp/service.lock` is no longer present

## Prevention

To prevent future occurrences:

1. Consider implementing a lockfile age check to auto-remove stale locks
2. Add proper signal handlers in the service to clean up lockfiles on shutdown
3. Use a lockfile that includes the process PID for better stale detection

## Timeline

| Time | Event |
|------|-------|
| 10:20:41 | Incident detected - HTTP 500 on /service1 |
| 10:21:00 | Diagnosis started - lockfile confirmed present |
| 10:21:30 | Remediation applied - lockfile removed |
| 10:21:45 | Verification complete - service healthy |

## References

- Skill runbook: `.agents/skills/stale-lockfile/SKILL.md`
- Related issue: #21
