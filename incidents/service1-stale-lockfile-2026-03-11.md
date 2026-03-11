# Incident Report: service1 Stale Lockfile

**Date**: 2026-03-11  
**Issue**: #70  
**Service**: service1  
**Endpoint**: `/service1`  
**Severity**: High (HTTP 500)  
**Status**: ✅ Resolved

## Skill Used

**stale-lockfile** - From `.agents/skills/stale-lockfile/SKILL.md`

This skill handles stale lockfile recovery for service1 when `/tmp/service.lock` prevents normal operation after a crash.

## Diagnosis

### Initial Status Check

**Tool**: `get_all_service_status`

```json
{
  "service1": {
    "path": "/service1",
    "http_code": "500",
    "healthy": false
  },
  "service2": {
    "path": "/service2",
    "http_code": "500",
    "healthy": false
  },
  "service3": {
    "path": "/service3",
    "http_code": "500",
    "healthy": false
  }
}
```

**Finding**: service1 confirmed returning HTTP 500

### Root Cause Analysis

**Tool**: `diagnose_service1`

```json
{
  "service": "service1",
  "scenario": "stale_lockfile",
  "http_status": "500",
  "healthy": false,
  "lock_file_exists": true,
  "diagnosis": "Stale lockfile present - needs removal",
  "recommended_action": "fix_service1",
  "next_step": "IMPORTANT: Call the fix_service1 tool NOW to remove the lockfile. This is MEDIUM risk and auto-approved per AGENTS.md."
}
```

**Root Cause**: Stale lockfile at `/tmp/service.lock` preventing service startup. This typically occurs after a service crash where the lockfile wasn't properly cleaned up.

## Risk Assessment

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `get_all_service_status` | LOW | Read-only health check via HTTP |
| `diagnose_service1` | LOW | Read-only check for lockfile existence |
| `rm -f /tmp/service.lock` | MEDIUM | Removes temporary lockfile; service-specific, reversible |
| `get_all_service_status` (verification) | LOW | Read-only health check via HTTP |

**MEDIUM Risk Rationale**: Removing `/tmp/service.lock` is classified as MEDIUM because:
- It modifies state (file deletion)
- Impact is limited to a temporary file
- Service remains unaffected if lockfile is incorrectly removed
- Action is easily reversible (service recreates lock when needed)
- Per `AGENTS.md` security policy, MEDIUM risk actions are auto-approved for SRE remediation

## Remediation

**Tool**: `fix_service1`

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

**Action Taken**: Successfully removed stale lockfile `/tmp/service.lock` using MCP tool `fix_service1`

**Result**: 
- ✅ Lockfile removed (`rm_returncode: 0`)
- ✅ No errors during removal
- ✅ HTTP status changed from 500 → 200
- ✅ Service is now healthy

## Verification

**Tool**: `get_all_service_status` (post-fix)

```json
{
  "service1": {
    "path": "/service1",
    "http_code": "200",
    "healthy": true
  },
  "service2": {
    "path": "/service2",
    "http_code": "500",
    "healthy": false
  },
  "service3": {
    "path": "/service3",
    "http_code": "500",
    "healthy": false
  }
}
```

**Confirmation**: service1 now returns HTTP 200 and is marked healthy ✅

## Summary

Successfully resolved service1 HTTP 500 error caused by stale lockfile. The MCP-based remediation workflow:

1. ✅ Confirmed service failure (HTTP 500)
2. ✅ Diagnosed root cause (lockfile exists)
3. ✅ Applied fix (removed `/tmp/service.lock`)
4. ✅ Verified resolution (HTTP 200)

**Time to Resolution**: < 1 minute (automated via MCP tools)

## Prevention

This incident type is handled by the `stale-lockfile` skill in `.agents/skills/stale-lockfile/`. Future occurrences will be automatically remediated following the same MCP tool sequence:
- `get_all_service_status` → `diagnose_service1` → `fix_service1` → `get_all_service_status`

## References

- Issue: #70
- Skill: `.agents/skills/stale-lockfile/SKILL.md`
- MCP Tools: `shttp_a534aee1_get_all_service_status`, `shttp_a534aee1_diagnose_service1`, `shttp_a534aee1_fix_service1`
- Security Policy: `AGENTS.md` (MEDIUM risk auto-approved)
