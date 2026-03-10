# Incident Report: Service1 Stale Lockfile

**Date**: 2026-03-06  
**Issue**: #68  
**Service**: service1  
**Endpoint**: `/service1`  
**Severity**: High (HTTP 500)  
**Status**: ✅ RESOLVED

## Skill Used
`stale-lockfile` (`.agents/skills/stale-lockfile/SKILL.md`)

## Summary
Service1 was returning HTTP 500 due to a stale lockfile at `/tmp/service.lock` left behind from a previous crash or deployment. The lockfile prevented the service from starting properly.

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

**Finding**: Service1 confirmed unhealthy with HTTP 500 status.

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

**Root Cause**: Stale lockfile `/tmp/service.lock` exists and is blocking service startup.

## Risk Assessment

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `curl -i http://service:5000` | LOW | Read-only health check to verify service status |
| `diagnose_service1` (MCP tool) | LOW | Read-only diagnostic that checks file existence |
| `rm -f /tmp/service.lock` | MEDIUM | Removes temp file only, service unaffected. Auto-approved per AGENTS.md security policy |
| `get_all_service_status` (verification) | LOW | Read-only health check to confirm fix |

**Classification**: MEDIUM risk remediation (auto-approved)
- Only removes a temporary lockfile in `/tmp/`
- Does not modify service code or configuration
- Does not affect other services
- Reversible (service will recreate if needed)

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

**Result**: Lockfile successfully removed. Service returned to healthy state immediately.

## Verification

### Post-Fix Status Check
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

**Success Criteria Met**:
- ✅ Service1 now returns HTTP 200
- ✅ Service1 marked as healthy
- ✅ `fix_service1` returned `"fixed": true` and `"post_http_status": "200"`
- ✅ No errors during lockfile removal (`rm_returncode: 0`)

## Timeline
1. **Detection**: Issue #68 created - service1 returning HTTP 500
2. **Diagnosis**: Confirmed stale lockfile via `diagnose_service1` MCP tool
3. **Remediation**: Executed `fix_service1` MCP tool to remove `/tmp/service.lock`
4. **Verification**: Confirmed HTTP 200 response via `get_all_service_status`
5. **Documentation**: Created incident report and PR

## Prevention
This type of incident can be prevented by:
1. Implementing proper signal handlers in the service to clean up lockfiles on shutdown
2. Using advisory file locks (flock) instead of existence-based locking
3. Adding lockfile cleanup to container startup scripts
4. Implementing lockfile staleness detection with PID validation

## Related Documentation
- Runbook: `.agents/skills/stale-lockfile/SKILL.md`
- Security Policy: `AGENTS.md`
- Similar Scenarios: See ITBench stale lockfile patterns
