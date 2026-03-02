# Incident Report: Service1 HTTP 500 - Stale Lockfile

**Date**: 2026-03-02  
**Issue**: #60  
**Severity**: Medium  
**Status**: Resolved  

## Skill Used

`stale-lockfile` - Diagnose and remediate stale lockfile failures that return HTTP 500 after crashes.

## Summary

Service1 was returning HTTP 500 errors due to a stale lockfile (`/tmp/service.lock`) that was left behind from a previous crash or deployment.

## Diagnosis

### Initial Service Status

```json
{
  "service1": {
    "path": "/service1",
    "http_code": "500",
    "healthy": false
  }
}
```

### Root Cause Analysis

```json
{
  "service": "service1",
  "scenario": "stale_lockfile",
  "http_status": "500",
  "healthy": false,
  "lock_file_exists": true,
  "diagnosis": "Stale lockfile present - needs removal",
  "recommended_action": "fix_service1"
}
```

The lockfile at `/tmp/service.lock` was preventing the service from starting properly. This is a common failure mode when a service crashes without properly cleaning up its lockfile.

## Risk Assessment

| Action | Risk Level | Rationale |
|--------|------------|-----------|
| `get_all_service_status` | LOW | Read-only health check |
| `diagnose_service1` | LOW | Read-only diagnostic check |
| `fix_service1` (rm -f /tmp/service.lock) | MEDIUM | Removes temp lockfile only, service unaffected if running |

## Remediation

### Action Taken

Executed `fix_service1` MCP tool to remove the stale lockfile:

```json
{
  "service": "service1",
  "action": "rm -f /tmp/service.lock",
  "risk_level": "MEDIUM",
  "pre_http_status": "500",
  "post_http_status": "200",
  "fixed": true,
  "rm_returncode": 0,
  "rm_error": null
}
```

## Verification

### Post-Fix Service Status

```json
{
  "service1": {
    "path": "/service1",
    "http_code": "200",
    "healthy": true
  }
}
```

Service1 is now returning HTTP 200 and is healthy.

## Prevention

To prevent this issue in the future:

1. Implement proper signal handling in the service to clean up lockfiles on shutdown
2. Use lockfile timeout mechanisms that automatically expire stale locks
3. Consider using advisory file locking instead of presence-based locking
4. Add startup scripts that clean up known stale lockfiles before service start

## Timeline

| Time | Event |
|------|-------|
| 2026-03-02 22:59 | Incident reported via GitHub Issue #60 |
| 2026-03-02 23:00 | Root cause identified: stale lockfile at /tmp/service.lock |
| 2026-03-02 23:00 | Remediation applied: lockfile removed |
| 2026-03-02 23:00 | Service restored to healthy state |
