# Incident Response: KAN-6 - Service1 HTTP 500 Error

## Skill Used
**stale-lockfile** (`.agents/skills/stale-lockfile/`)

This skill addresses stale lockfile failures that cause services to return HTTP 500 after crashes or improper shutdowns.

## Diagnosis

### Initial Service Status Check
Called `get_all_service_status` to identify failing services:

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

**Finding**: All three services were returning HTTP 500, but this ticket specifically addresses service1.

### Detailed Diagnosis for Service1
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

**Root Cause**: A stale lockfile at `/tmp/service.lock` was preventing service1 from starting properly, resulting in HTTP 500 responses.

## Risk Assessment

### Planned Action
- **Action**: `rm -f /tmp/service.lock`
- **Risk Level**: MEDIUM
- **Rationale**: This action removes a temporary lockfile. While it modifies filesystem state, the file is:
  - Located in `/tmp` (temporary directory)
  - A lockfile (designed to be removed when the process exits)
  - Not containing any business data
  - Safe to remove when stale (which was confirmed by the diagnosis)

Per AGENTS.md security policy, MEDIUM risk actions are auto-approved and should be executed with proper reporting.

### Actions Taken

| Action | Risk | Rationale |
|--------|------|-----------|
| `get_all_service_status` | LOW | Read-only health check of all services |
| `diagnose_service1` | LOW | Read-only check for lockfile existence |
| `rm -f /tmp/service.lock` | MEDIUM | Removes temporary lockfile only, service recovers automatically |
| `get_all_service_status` | LOW | Read-only verification of fix |

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

**Result**: The lockfile was successfully removed. Service1 immediately recovered and began returning HTTP 200.

## Verification

Called `get_all_service_status` to confirm service health:

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

**Verification Success**:
- ✅ Service1 now returns HTTP 200
- ✅ Service1 is marked as healthy
- ✅ The fix was successful and immediate
- ✅ No service restart was required

## Summary

The incident was caused by a stale lockfile (`/tmp/service.lock`) that prevented service1 from handling requests. The remediation followed the standard stale-lockfile skill workflow:

1. Identified the failing service (HTTP 500)
2. Diagnosed the root cause (stale lockfile exists)
3. Executed the fix (removed lockfile via MCP tool)
4. Verified recovery (HTTP 200 confirmed)

The fix was classified as MEDIUM risk and executed per AGENTS.md policy. Service1 is now fully operational.

## Notes

- Service2 and Service3 remain in a failed state (HTTP 500) - these are separate incidents requiring their own remediation
- No manual intervention or service restart was required
- The MCP tool `fix_service1` executed the fix remotely on the demo container
- Total resolution time: < 1 minute
