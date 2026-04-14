# Incident Report: Service1 Stale Lockfile

**Date**: 2026-04-14  
**Issue**: #129  
**Service**: service1  
**Endpoint**: `/service1`

## Skill Used

`stale-lockfile` - Stale lockfile recovery from `.agents/skills/stale-lockfile/`

## Diagnosis

Initial health check revealed service1 was returning HTTP 500 Internal Server Error.

**Step 1: Initial Status Check**
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

**Step 2: Diagnosis**
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

The diagnosis confirmed the root cause: a stale lockfile at `/tmp/service.lock` was preventing the service from starting properly after a previous crash.

## Risk Assessment

**Risk Level**: MEDIUM (auto-approved per AGENTS.md security policy)

| Action | Risk | Rationale |
|--------|------|-----------|
| `get_all_service_status` | LOW | Read-only health check via HTTP |
| `diagnose_service1` | LOW | Read-only check for lockfile existence |
| `rm -f /tmp/service.lock` | MEDIUM | Removes temp file only, service code unaffected |
| `get_all_service_status` | LOW | Read-only verification check |

The removal of `/tmp/service.lock` is classified as MEDIUM risk because:
- It modifies system state by removing a file
- However, it's a temporary file with no impact on application code
- The action is reversible (service would recreate lockfile if it crashed again)
- Only affects service1, not other services

## Remediation

**Action Taken**: Removed stale lockfile using MCP tool `fix_service1`

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

The fix was executed successfully:
- Command: `rm -f /tmp/service.lock`
- Return code: 0 (success)
- No errors encountered
- Immediate transition from HTTP 500 to HTTP 200

## Verification

**Post-Fix Status Check**
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

**Verification Steps:**
1. ✅ Service1 now returns HTTP 200
2. ✅ Service1 health check shows `"healthy": true`
3. ✅ Service1 returns expected JSON response: `{"status": "ok"}`
4. ✅ Other services (service2, service3) remain healthy and unaffected

## Resolution

The incident was successfully resolved by removing the stale lockfile. Service1 is now operational and returning the expected HTTP 200 response with `"status": "ok"`.

**Root Cause**: Stale lockfile left behind after a previous service crash  
**Fix**: Removed `/tmp/service.lock`  
**Impact**: No data loss, no impact on other services  
**Prevention**: This is an expected operational scenario; the service correctly detects and reports the lockfile issue for SRE remediation
