# Incident Report #50: service1 HTTP 500 - Stale Lockfile

## Skill Used
`stale-lockfile` - Diagnose and remediate stale lockfile failures that return HTTP 500 after crashes.

## Summary
- **Service**: service1 (health-api)
- **Endpoint**: `/service1`
- **Issue**: HTTP 500 Internal Server Error
- **Root Cause**: Stale lockfile present at `/tmp/service.lock`
- **Resolution Time**: 2026-03-02T20:08
- **Status**: ✅ Resolved

## Diagnosis

### Step 1: Initial Status Check
Called `get_all_service_status` to check current service health:

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

### Step 2: Root Cause Analysis
Called `diagnose_service1` to identify the issue:

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

**Finding**: Stale lockfile at `/tmp/service.lock` was blocking service startup.

## Risk Assessment

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `get_all_service_status` | LOW | Read-only health check |
| `diagnose_service1` | LOW | Read-only diagnostic check |
| `fix_service1` (rm -f /tmp/service.lock) | MEDIUM | Removes temp lockfile only, auto-approved per AGENTS.md |

## Remediation

### Step 3: Apply Fix
Called `fix_service1` to remove the stale lockfile:

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

**Result**: Lockfile removed successfully, service recovered.

## Verification

### Step 4: Post-Fix Status Check
Called `get_all_service_status` to verify the fix:

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

**Confirmed**: service1 is now returning HTTP 200 and is healthy.

## Actions Taken

| Action | Risk | Rationale |
|--------|------|-----------|
| `get_all_service_status` | LOW | Read-only health check |
| `diagnose_service1` | LOW | Read-only file existence check |
| `rm -f /tmp/service.lock` | MEDIUM | Removes temp file only, service unaffected |
| `get_all_service_status` (verify) | LOW | Read-only verification |

## Prevention Recommendations
1. Implement proper signal handling to clean up lockfiles on shutdown
2. Add lockfile staleness detection (e.g., check PID validity)
3. Configure automatic lockfile cleanup on container restart
