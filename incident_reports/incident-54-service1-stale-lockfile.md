# Incident Report: Service1 HTTP 500 - Stale Lockfile

**Incident ID**: #54  
**Date**: 2026-03-02  
**Service**: service1  
**Endpoint**: `/service1`  
**Severity**: Critical  
**Status**: Resolved  

## Skill Used
`stale-lockfile` - Diagnose and remediate stale lockfile failures that return HTTP 500 after crashes.

## Diagnosis

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

**Root Cause**: A stale lockfile at `/tmp/service.lock` was preventing service1 from starting properly, causing HTTP 500 errors.

## Risk Assessment

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `get_all_service_status` | LOW | Read-only health check |
| `diagnose_service1` | LOW | Read-only diagnosis |
| `fix_service1` (rm -f /tmp/service.lock) | MEDIUM | Removes temp lockfile only; auto-approved per AGENTS.md |

## Remediation

### Fix Applied
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

### Post-Fix Status Check
```json
{
  "service1": {
    "path": "/service1",
    "http_code": "200",
    "healthy": true
  }
}
```

## Timeline

1. **Detection**: Service1 endpoint returning HTTP 500
2. **Diagnosis**: Identified stale lockfile at `/tmp/service.lock`
3. **Remediation**: Removed stale lockfile using `fix_service1` MCP tool
4. **Verification**: Confirmed service1 returned to HTTP 200 healthy state

## Prevention Recommendations

1. Implement automatic lockfile cleanup on service crash/restart
2. Add lockfile age monitoring and automatic cleanup for files older than expected startup time
3. Consider using a lock management system that handles stale locks gracefully
