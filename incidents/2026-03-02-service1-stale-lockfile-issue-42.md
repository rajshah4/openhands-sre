# Incident Report: Service1 Stale Lockfile (Issue #42)

**Date**: 2026-03-02  
**Service**: service1 (health-api)  
**Endpoint**: `/service1`  
**Issue**: [#42](https://github.com/rajshah4/openhands-sre/issues/42)  

## Skill Used

`stale-lockfile` — Diagnose and remediate stale lockfile failures that return HTTP 500 after crashes.

## Incident Summary

Service1 was returning HTTP 500 Internal Server Error due to a stale lockfile present at `/tmp/service.lock`. The lockfile was left behind from a previous process crash, preventing the service from responding to health checks.

## Diagnosis

### Symptoms
- Health endpoint `/service1` returning HTTP 500 status code
- Error message: "stale lockfile present at /tmp/service.lock"
- Service was healthy before last deployment

### Root Cause
The file `/tmp/service.lock` existed in the container but the owning process was no longer running. This is a common issue when:
1. A previous service instance crashed without cleanup
2. The container was forcefully stopped
3. A deployment failed mid-process

### Diagnostic Steps (LOW Risk)
```bash
# Check service health (LOW risk - read-only)
curl -i $TARGET_URL/service1

# Verify lockfile exists (LOW risk - read-only)
docker exec openhands-gepa-demo ls -la /tmp/service.lock
```

## Risk Assessment

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `diagnose_service1` MCP tool | LOW | Read-only health check and file inspection |
| `fix_service1` MCP tool (rm -f /tmp/service.lock) | MEDIUM | Removes only temp lockfile, service unaffected, reversible |
| `get_all_service_status` MCP tool | LOW | Read-only health verification |

**Overall Risk Level**: MEDIUM (auto-approved per AGENTS.md security policy)

## Remediation

### MCP Tool Workflow (Preferred)
When MCP tools are available, execute the following sequence:

1. **Diagnose**: Call `diagnose_service1` to confirm lockfile issue
2. **Fix**: Call `fix_service1` to remove the stale lockfile
3. **Verify**: Call `get_all_service_status` to confirm HTTP 200

### Manual Remediation (Fallback)
If MCP tools are unavailable:

```bash
# Remove stale lockfile (MEDIUM risk)
docker exec openhands-gepa-demo rm -f /tmp/service.lock
```

### Actions Taken

| Action | Risk | Rationale |
|--------|------|-----------|
| `diagnose_service1` | LOW | Read-only check to confirm stale lockfile |
| `fix_service1` (rm -f /tmp/service.lock) | MEDIUM | Removes temp file only, auto-approved per policy |
| `get_all_service_status` | LOW | Read-only health verification |

## Verification

After remediation:
- `curl -i $TARGET_URL/service1` returns HTTP 200
- Response body contains `"status": "ok"`
- Lockfile `/tmp/service.lock` no longer exists

## Prevention

To prevent future occurrences:
1. Ensure graceful shutdown handlers clean up lockfiles
2. Add lockfile staleness check on service startup
3. Consider using advisory locks instead of file-based locks
4. Implement lockfile timeout/expiration mechanism

## References

- Skill: `.agents/skills/stale-lockfile/SKILL.md`
- MCP Server: `mcp_server/server.py` (`fix_service1` function)
- Target Service: `target_service/app.py` (lockfile check logic)
