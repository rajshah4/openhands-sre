# Incident Report: Service1 Stale Lockfile

**Date**: 2026-03-11  
**Issue**: [#74](https://github.com/rajshah4/openhands-sre/issues/74)  
**Service**: service1  
**Status**: ✅ RESOLVED

## Skill Used

`stale-lockfile` - Diagnose and remediate stale lockfile failures that return HTTP 500 after crashes.

## Summary

Service1 was returning HTTP 500 Internal Server Error due to a stale lockfile at `/tmp/service.lock`. The lockfile was left behind after a crash and prevented the service from starting properly.

## Diagnosis

### Initial Status Check

Called `get_all_service_status` to confirm service health:

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

**Result**: Service1 confirmed returning HTTP 500.

### Detailed Diagnosis

Called `diagnose_service1` to identify the root cause:

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

**Root Cause**: Stale lockfile at `/tmp/service.lock` was blocking service startup.

## Risk Assessment

| Action | Risk Level | Justification |
|--------|-----------|---------------|
| `get_all_service_status` | LOW | Read-only health check |
| `diagnose_service1` | LOW | Read-only diagnostic check |
| `fix_service1` | MEDIUM | Removes temporary file only, service unaffected by file deletion |
| `get_all_service_status` (verification) | LOW | Read-only health check |

**Decision**: MEDIUM risk action approved per AGENTS.md security policy. Action is auto-approved as it only removes a temporary lockfile.

## Remediation

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

**Action Taken**: Executed `rm -f /tmp/service.lock` to remove the stale lockfile.  
**Result**: Lockfile successfully removed (`rm_returncode: 0`), service immediately recovered.

## Verification

Called `get_all_service_status` to confirm service recovery:

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

**Verification**: ✅ Service1 now returns HTTP 200 and is healthy.

## Timeline

1. **Detection**: Issue #74 created reporting service1 HTTP 500
2. **Diagnosis**: MCP tool `diagnose_service1` confirmed stale lockfile at `/tmp/service.lock`
3. **Remediation**: MCP tool `fix_service1` removed lockfile
4. **Verification**: Service1 confirmed healthy with HTTP 200 response
5. **Documentation**: Incident report created

## Lessons Learned

- Stale lockfiles are a common failure mode after service crashes
- MCP tools enable rapid diagnosis and remediation without manual intervention
- Risk-based security policy (MEDIUM risk = auto-approved) allows autonomous fix
- The `stale-lockfile` skill in `.agents/skills/` provided clear runbook for resolution

## Related

- Skill: [`.agents/skills/stale-lockfile/`](../.agents/skills/stale-lockfile/)
- Issue: [#74](https://github.com/rajshah4/openhands-sre/issues/74)
