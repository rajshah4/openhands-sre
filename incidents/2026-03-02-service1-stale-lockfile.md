# Incident Report: service1 HTTP 500 - Stale Lockfile

**Date**: 2026-03-02  
**Service**: service1 (health-api)  
**Severity**: Medium  
**Duration**: Resolved within minutes  
**Resolved By**: OpenHands SRE Agent  

## Summary

Service1 was returning HTTP 500 errors due to a stale lockfile at `/tmp/service.lock` that remained from a previous crash. The lockfile prevented the service from passing health checks.

## Skill Used

`stale-lockfile` - from `.agents/skills/stale-lockfile/SKILL.md`

## Diagnosis

### Symptoms Observed
- Health endpoint `/service1` returning HTTP 500
- Error message: "stale lockfile present at /tmp/service.lock"
- Service process was running but blocked by the stale lock

### Verification Commands
```bash
# Check service health
curl -i http://localhost:12000/service1
# Response: HTTP 500 {"status":"error","reason":"stale lockfile present at /tmp/service.lock"}

# Verify lockfile exists
docker exec openhands-gepa-demo ls -la /tmp/service.lock
# Output: -rw-r--r-- 1 root root 0 Mar  2 16:47 /tmp/service.lock
```

## Risk Assessment

| Action | Risk Level | Rationale |
|--------|------------|-----------|
| `curl -i http://localhost:12000/service1` | LOW | Read-only health check |
| `docker exec ... ls -la /tmp/service.lock` | LOW | Read-only file inspection |
| `docker exec ... rm -f /tmp/service.lock` | MEDIUM | Removes temp file only, service state unaffected |

## Remediation

### Actions Taken

```bash
# Pre-check: Confirm lockfile exists
docker exec openhands-gepa-demo ls -la /tmp/service.lock

# Remove stale lockfile (MEDIUM risk)
docker exec openhands-gepa-demo rm -f /tmp/service.lock

# Post-check: Verify lockfile removed
docker exec openhands-gepa-demo ls -la /tmp/service.lock 2>&1 || echo "Lockfile removed"
```

## Verification

```bash
# Verify service is healthy
curl -i http://localhost:12000/service1
# Response: HTTP 200 {"status":"ok","scenario":"stale_lockfile"}
```

### Results
- HTTP status changed from 500 to 200
- Service health check now passing
- No service restart required

## Root Cause

A previous service crash or deployment left behind a stale lockfile at `/tmp/service.lock`. The service startup logic checks for this lockfile and fails if it exists, as a safety mechanism to prevent multiple instances. However, when the process that created the lock terminates unexpectedly, the lockfile remains orphaned.

## Prevention

1. Consider implementing lockfile cleanup on service startup with process validation
2. Use advisory locks or process ID validation instead of simple file presence checks
3. Implement automatic stale lock detection and cleanup

## References

- Skill: `.agents/skills/stale-lockfile/SKILL.md`
- Issue: #26
- Test: `tests/test_integration.py::TargetServiceIntegrationTests::test_stale_lockfile_recovers_500_to_200`
