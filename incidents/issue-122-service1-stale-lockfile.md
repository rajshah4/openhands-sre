# Incident Report: Service1 Stale Lockfile (Issue #122)

**Date**: 2026-04-07
**Service**: service1
**Endpoint**: `/service1`
**Issue**: #122

## Skill Used
`stale-lockfile` (from `.agents/skills/stale-lockfile/SKILL.md`)

## Diagnosis

Service1 was returning HTTP 500 due to a stale lockfile remaining from a previous crash.

### Initial Status Check
```json
{
  "service1": {
    "path": "/service1",
    "http_code": "500",
    "healthy": false
  }
}
```

### Diagnostic Results
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

**Root Cause**: The lockfile `/tmp/service.lock` was not cleaned up after a previous service crash, causing the service to fail health checks.

## Risk Assessment

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `rm -f /tmp/service.lock` | MEDIUM | Removes temporary file only. Service-scoped action with no impact on other services. Auto-approved per AGENTS.md policy. |

**Risk Level**: MEDIUM (auto-approved — no human approval needed per AGENTS.md)

## Remediation

Used MCP tool `fix_service1` to remove the stale lockfile.

### Fix Execution
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

**Action Taken**: Removed stale lockfile at `/tmp/service.lock`
**Result**: ✅ Successfully removed (returncode: 0)

## Verification

Post-remediation status check confirms service1 is now healthy.

### Final Status Check
```json
{
  "service1": {
    "path": "/service1",
    "http_code": "200",
    "healthy": true
  }
}
```

**Verification Results**:
- ✅ Service1 now returns HTTP 200
- ✅ Health check status: healthy
- ✅ No errors reported

## Summary

Successfully resolved service1 HTTP 500 error by removing stale lockfile. Service is now operational and returning expected HTTP 200 responses.

**MCP Tools Used**:
1. `get_all_service_status` - Initial diagnosis
2. `diagnose_service1` - Confirmed lockfile presence
3. `fix_service1` - Removed stale lockfile
4. `get_all_service_status` - Verified fix

**Resolution Time**: < 1 minute
**Impact**: Service1 restored to healthy state
