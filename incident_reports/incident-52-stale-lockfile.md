# Incident Report: Service1 HTTP 500 - Stale Lockfile

**Issue**: #52  
**Date**: 2026-03-02  
**Service**: service1 (health-api)  
**Endpoint**: `/service1`  
**Status**: ✅ Resolved  

## Skill Used

`stale-lockfile` - Located at `.agents/skills/stale-lockfile/SKILL.md`

## Symptoms

- Health endpoint returning HTTP 500 status code
- Error message: "stale lockfile present at /tmp/service.lock"

## Diagnosis

### Step 1: Initial Status Check (`get_all_service_status`)

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

**Finding**: Service1 confirmed returning HTTP 500.

### Step 2: Root Cause Analysis (`diagnose_service1`)

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

**Finding**: `lock_file_exists: true` - Stale lockfile at `/tmp/service.lock` confirmed as root cause.

## Risk Assessment

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `get_all_service_status` | LOW | Read-only health check |
| `diagnose_service1` | LOW | Read-only diagnostic check |
| `fix_service1` (rm -f /tmp/service.lock) | MEDIUM | Removes temp lockfile only; auto-approved per AGENTS.md |

## Remediation

### Step 3: Applied Fix (`fix_service1`)

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

**Result**: Lockfile successfully removed. Service immediately returned HTTP 200.

## Verification

### Step 4: Post-Fix Status Check (`get_all_service_status`)

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

**Verification**: Service1 now returning HTTP 200 and marked as healthy.

## Summary

| Metric | Before | After |
|--------|--------|-------|
| HTTP Status | 500 | 200 |
| Healthy | false | true |
| Lockfile Present | true | false |

## Prevention Recommendations

1. Implement proper lockfile cleanup on service shutdown
2. Add lockfile staleness detection (check PID validity)
3. Consider using advisory locks instead of file-based locks
