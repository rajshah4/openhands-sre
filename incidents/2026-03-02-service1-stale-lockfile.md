# Incident Report: Service1 HTTP 500 - Stale Lockfile

**Date**: 2026-03-02  
**Service**: service1 (health-api)  
**Endpoint**: `/service1`  
**Duration**: ~10 minutes  
**Severity**: Medium  
**Issue**: #44

## Summary

Service1 returned HTTP 500 due to a stale lockfile (`/tmp/service.lock`) left behind from a previous process crash.

## Skill Used

`stale-lockfile` - from `.agents/skills/stale-lockfile/SKILL.md`

## Diagnosis

Used MCP tool `diagnose_service1` to confirm the issue:

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

| Action | Risk Level | Rationale |
|--------|------------|-----------|
| `diagnose_service1` | LOW | Read-only check for lockfile |
| `fix_service1` | MEDIUM | Removes temp file `/tmp/service.lock` - auto-approved per AGENTS.md |
| `get_all_service_status` | LOW | Read-only health check |

## Remediation

### Actions Taken

| Action | Risk | Result |
|--------|------|--------|
| `get_all_service_status` | LOW | Confirmed service1 returning HTTP 500 |
| `diagnose_service1` | LOW | Confirmed stale lockfile at `/tmp/service.lock` |
| `fix_service1` | MEDIUM | Removed lockfile: `rm -f /tmp/service.lock` |
| `get_all_service_status` | LOW | Verified service1 now returns HTTP 200 |

### MCP Tool Output

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

Service1 now returns HTTP 200:

```bash
$ curl http://localhost:15000/service1
{"scenario":"stale_lockfile","status":"ok"}
```

## Root Cause

The lockfile `/tmp/service.lock` was left behind after a previous process crash or unclean shutdown. The service checks for this lockfile on startup and refuses to serve traffic if it exists (to prevent duplicate instances).

## Prevention

1. Ensure proper cleanup in shutdown handlers
2. Consider implementing stale lockfile detection based on process PID
3. Add monitoring alerts for HTTP 500 responses on health endpoints

## Timeline

| Time | Event |
|------|-------|
| 2026-03-02T12:07:12 | Alert: service1 returning HTTP 500 |
| 2026-03-02T18:07:XX | Diagnosis: Stale lockfile confirmed |
| 2026-03-02T18:07:XX | Remediation: Lockfile removed |
| 2026-03-02T18:07:XX | Verification: Service healthy (HTTP 200) |
