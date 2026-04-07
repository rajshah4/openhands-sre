# Incident Report: Issue #124 - Service1 Stale Lockfile

**Date**: 2026-04-07  
**Service**: service1  
**Issue**: #124  
**Status**: ✅ Resolved

## Skill Used

**stale-lockfile** (`.agents/skills/stale-lockfile/SKILL.md`)

This incident matched the stale lockfile recovery pattern, which applies to service1 endpoint failures caused by leftover lockfiles from previous crashes.

## Diagnosis

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

### Service1 Diagnosis
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

**Root Cause**: Stale lockfile present at `/tmp/service.lock` from a previous crash, preventing service1 from starting properly.

**Symptoms**:
- Service1 endpoint returning HTTP 500 Internal Server Error
- Error message: "stale lockfile present at /tmp/service.lock"
- Service was healthy before last deployment

## Risk Assessment

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `get_all_service_status` | LOW | Read-only health check via HTTP |
| `diagnose_service1` | LOW | Read-only check for lockfile existence |
| `fix_service1` (rm -f /tmp/service.lock) | MEDIUM | Removes temp lockfile only; auto-approved per AGENTS.md |
| `get_all_service_status` (verification) | LOW | Read-only health check via HTTP |

**Overall Risk**: MEDIUM  
**Approval Status**: Auto-approved (per AGENTS.md security policy for stale lockfile removal)

## Remediation

### Action Taken
Executed `fix_service1` MCP tool to remove the stale lockfile.

### Execution Result
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

**Success Indicators**:
- ✅ Lockfile removed successfully (`rm_returncode: 0`)
- ✅ HTTP status changed from 500 → 200
- ✅ `fixed: true` confirmation

## Verification

### Post-Fix Status Check
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

**Verification Results**:
- ✅ Service1 now returns HTTP 200
- ✅ Service1 healthy status: `true`
- ✅ Expected response: `{"status": "ok"}`

## Resolution

**Incident Resolved**: Service1 is now operational and returning the expected HTTP 200 status.

**Time to Resolution**: < 1 minute (automated via MCP tools)

## Notes

- This incident was resolved using MCP (Model Context Protocol) tools that execute remotely on the infrastructure
- No code changes were required; the fix was purely operational (removing a stale lockfile)
- Service2 and Service3 were also showing HTTP 500 but were not part of this incident scope (Issue #124 specifically referenced service1)
