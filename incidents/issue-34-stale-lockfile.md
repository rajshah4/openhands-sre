# Incident Report: Service1 Stale Lockfile - Issue #34

**Incident ID**: ISSUE-34
**Date**: 2026-03-02
**Service**: service1 (health-api)
**Endpoint**: `/service1`
**Severity**: MEDIUM
**Status**: RESOLVED

## Skill Used
`stale-lockfile` - Diagnose and remediate stale lockfile failures that return HTTP 500 after crashes.

## Symptoms
- Health endpoint returning HTTP 500 status code
- Error message: "stale lockfile present at /tmp/service.lock"
- Service was healthy before last deployment

## Diagnosis

### Investigation Steps
1. **HTTP Status Check**: Confirmed service1 returning HTTP 500
2. **Lockfile Check**: Verified stale lockfile exists at `/tmp/service.lock`
3. **Process Verification**: Confirmed no active process owns the lockfile

### Root Cause
The service crashed during a previous operation, leaving behind a lockfile at `/tmp/service.lock`. On restart, the service detected this orphaned lockfile and refused to start, returning HTTP 500 to all health checks.

## Risk Assessment

| Action | Risk Level | Rationale |
|--------|------------|-----------|
| `diagnose_service1` / `curl -i /service1` | LOW | Read-only health check |
| `ls -la /tmp/service.lock` | LOW | Read-only file inspection |
| `rm -f /tmp/service.lock` | MEDIUM | Removes temp file only, service unaffected if file legitimately in use (but it wasn't) |
| `curl -i /service1` (verify) | LOW | Read-only health check |

## Remediation

### Actions Taken

**Step 1: Diagnosis**
```bash
# Using MCP tool or manual command
diagnose_service1
# OR: docker exec openhands-gepa-demo ls -la /tmp/service.lock
```
Result: Confirmed lockfile exists, service unhealthy

**Step 2: Fix (MEDIUM Risk)**
```bash
# Using MCP tool or manual command
fix_service1
# OR: docker exec openhands-gepa-demo rm -f /tmp/service.lock
```
Result: Lockfile removed successfully

**Step 3: Verification**
```bash
# Using MCP tool or manual command
get_all_service_status
# OR: curl -i $TARGET_URL/service1
```
Result: Service now returns HTTP 200 with `"status": "ok"`

## Verification
- ✅ HTTP 200 response from `/service1`
- ✅ Response contains `"status": "ok"`
- ✅ Lockfile `/tmp/service.lock` no longer exists

## Timeline
| Time | Event |
|------|-------|
| 2026-03-02T11:27:33 | Incident detected - HTTP 500 on /service1 |
| 2026-03-02T17:28:00 | Diagnosis started |
| 2026-03-02T17:28:30 | Root cause identified: stale lockfile |
| 2026-03-02T17:29:00 | Remediation applied: lockfile removed |
| 2026-03-02T17:29:30 | Service restored to healthy state |

## Lessons Learned
1. The service should implement lockfile cleanup on startup if the owning process is not running
2. Consider adding a timeout mechanism to automatically remove stale lockfiles
3. Health checks should provide more detailed diagnostics to accelerate troubleshooting

## References
- Skill: `.agents/skills/stale-lockfile/SKILL.md`
- MCP Server: `mcp_server/server.py` (diagnose_service1, fix_service1)
- Target Service: `target_service/app.py` (stale_lockfile scenario)
