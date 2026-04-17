# Incident Report: Issue #136 - Service1 Stale Lockfile

**Date:** 2026-04-17  
**Service:** service1  
**Endpoint:** `/service1`  
**Status:** RESOLVED

## Skill Used

`stale-lockfile` - Runbook from `.agents/skills/stale-lockfile/SKILL.md`

## Diagnosis

Service1 was returning HTTP 500 Internal Server Error due to a stale lockfile at `/tmp/service.lock`. This occurs when the service crashes or is terminated unexpectedly without cleaning up its lock file, preventing subsequent startups from succeeding.

### Initial Status Check
```json
{
  "service1": {
    "path": "/service1",
    "http_code": "500",
    "healthy": false
  },
  "service2": {
    "path": "/service2",
    "http_code": "200",
    "healthy": true
  },
  "service3": {
    "path": "/service3",
    "http_code": "200",
    "healthy": true
  }
}
```

### Diagnostic Output
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

## Risk Assessment

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `get_all_service_status` | LOW | Read-only health check via HTTP |
| `diagnose_service1` | LOW | Read-only check for lockfile existence |
| `fix_service1` (remove lockfile) | MEDIUM | Modifies filesystem by removing temp file only. Service unaffected as lockfile is only used for startup coordination. |
| `get_all_service_status` (verification) | LOW | Read-only health check via HTTP |

**Risk Level:** MEDIUM (auto-approved per AGENTS.md security policy)

The remediation action involves removing a temporary lock file (`/tmp/service.lock`). This is classified as MEDIUM risk because:
- It modifies the filesystem
- However, it only affects a temporary file
- The action is reversible (service will recreate lock on next startup)
- No production data or configuration is affected
- The service itself is not modified

## Remediation

Executed MCP tool `fix_service1` to remove the stale lockfile.

### Action Taken
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

The lockfile was successfully removed with return code 0, and the service immediately became healthy.

## Verification

After remediation, verified all services are healthy:

```json
{
  "service1": {
    "path": "/service1",
    "http_code": "200",
    "healthy": true
  },
  "service2": {
    "path": "/service2",
    "http_code": "200",
    "healthy": true
  },
  "service3": {
    "path": "/service3",
    "http_code": "200",
    "healthy": true
  }
}
```

**Result:** ✅ Service1 now returns HTTP 200 with expected response. All services operational.

## Root Cause

The service crashed or was terminated during a previous deployment without properly cleaning up the lockfile at `/tmp/service.lock`. Subsequent startup attempts failed because the service detected the existing lockfile and refused to start, assuming another instance was already running.

## Prevention

Consider implementing one or more of the following improvements:
1. Add signal handlers to ensure lockfile cleanup on graceful shutdown
2. Implement stale lockfile detection with PID verification
3. Use systemd or container orchestration features for proper cleanup
4. Add startup script to remove stale lockfiles older than X minutes
