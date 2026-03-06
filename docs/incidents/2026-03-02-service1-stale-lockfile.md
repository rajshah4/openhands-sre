# Incident Report: service1 HTTP 500 - Stale Lockfile

**Date**: 2026-03-02  
**Issue**: #36  
**Severity**: MEDIUM  
**Status**: RESOLVED  

## Skill Used

`stale-lockfile` - Diagnose and remediate stale lockfile failures that return HTTP 500 after crashes.

## Summary

Service1 (health-api) was returning HTTP 500 errors due to a stale lockfile at `/tmp/service.lock` from a previous crash or deployment.

## Symptoms

- Health endpoint `/service1` returning HTTP 500
- Error response: `{"reason":"stale lockfile present at /tmp/service.lock","status":"error"}`
- Service startup blocked by existing lockfile from a process that was no longer running

## Diagnosis

Verified the issue by checking the service endpoint:
```bash
curl -s http://127.0.0.1:5000/service1
# Response: {"reason":"stale lockfile present at /tmp/service.lock","status":"error"}
# HTTP Status: 500
```

Confirmed lockfile presence:
```bash
ls -la /tmp/service.lock
# -rw-r--r-- 1 openhands openhands 0 Mar  2 17:34 /tmp/service.lock
```

## Risk Assessment

| Action | Risk Level | Rationale |
|--------|------------|-----------|
| `curl -i http://service:5000/service1` | LOW | Read-only health check |
| `ls -la /tmp/service.lock` | LOW | Read-only file inspection |
| `rm -f /tmp/service.lock` | MEDIUM | Removes temp lockfile only, service unaffected if file is stale |

## Remediation

Executed fix by removing the stale lockfile:
```bash
rm -f /tmp/service.lock
```

**Risk Level**: MEDIUM - Removes a temporary file; auto-approved per AGENTS.md security policy.

## Verification

Post-fix verification confirmed service recovery:
```bash
curl -s http://127.0.0.1:5000/service1
# Response: {"scenario":"stale_lockfile","status":"ok"}
# HTTP Status: 200
```

## Root Cause

The lockfile `/tmp/service.lock` was left behind after a previous service crash or ungraceful shutdown. The service checks for this lockfile on startup and refuses to serve requests if it exists to prevent multiple instances running simultaneously.

## Lessons Learned

1. Lockfile cleanup should be part of deployment or restart procedures
2. Consider implementing stale lockfile detection based on process ownership
3. Monitor for recurring lockfile issues that might indicate underlying instability

## References

- Skill: `.agents/skills/stale-lockfile/SKILL.md`
- Service: `target_service/app.py`
