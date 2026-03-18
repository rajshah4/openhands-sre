# Incident Report: Service1 Stale Lockfile

**Date**: 2026-03-04  
**Issue**: #62  
**Service**: service1  
**Endpoint**: `/service1`  
**Severity**: High (HTTP 500 - Service Unavailable)  
**Status**: ✅ Resolved

## Skill Used

**stale-lockfile** (`.agents/skills/stale-lockfile/`)

This skill handles stale lockfile failures that return HTTP 500 after service crashes.

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

**Finding**: service1 confirmed returning HTTP 500.

### Detailed Diagnosis

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

**Root Cause**: Stale lockfile at `/tmp/service.lock` preventing service startup.

## Risk Assessment

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `get_all_service_status` | **LOW** | Read-only health check via HTTP request |
| `diagnose_service1` | **LOW** | Read-only file system check and HTTP status |
| `rm -f /tmp/service.lock` | **MEDIUM** | Removes temporary lockfile only. Auto-approved per `AGENTS.md`. Service unaffected by removal. |
| Post-fix verification | **LOW** | Read-only health check to confirm remediation |

**Risk Justification for MEDIUM action**:
- The lockfile at `/tmp/service.lock` is a temporary file used for process synchronization
- Removing a stale lockfile is a standard remediation for crashed processes
- The `-f` flag ensures idempotent operation (no error if file doesn't exist)
- This action is explicitly auto-approved in the stale-lockfile skill runbook

## Remediation

### Action Taken

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

**Result**: 
- Lockfile successfully removed
- Service immediately returned to healthy state
- HTTP status changed from 500 → 200

## Verification

### Post-Remediation Status Check

**Tool**: `get_all_service_status`

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

**Verification Status**: ✅ Success
- service1 now returns HTTP 200
- Service marked as healthy
- No errors or warnings

## Timeline

| Time | Event |
|------|-------|
| T+0min | Issue #62 reported: service1 returning HTTP 500 |
| T+0min | Initial diagnosis confirmed stale lockfile at `/tmp/service.lock` |
| T+1min | Executed `rm -f /tmp/service.lock` via `fix_service1` MCP tool |
| T+1min | Verified service1 healthy (HTTP 200) |
| T+2min | Incident report documented and PR created |

## Prevention

**Recommended Actions**:
1. Implement proper signal handling in service1 to cleanup lockfiles on shutdown
2. Add health check retry logic to detect stale lockfiles automatically
3. Consider using OS-level file locking with automatic cleanup (e.g., `flock` with file descriptors)
4. Add monitoring alerts for HTTP 500 responses on critical endpoints

## References

- Skill: `.agents/skills/stale-lockfile/SKILL.md`
- MCP Tools: `get_all_service_status`, `diagnose_service1`, `fix_service1`
- Security Policy: `AGENTS.md` (MEDIUM risk auto-approved)
