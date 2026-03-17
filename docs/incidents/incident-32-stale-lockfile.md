# Incident Response: Service1 HTTP 500 - Stale Lockfile

**Incident ID**: #32  
**Service**: service1 (health-api)  
**Endpoint**: `/service1`  
**Status**: RESOLVED  
**Skill Used**: `stale-lockfile`

## Incident Summary

Service1 was returning HTTP 500 Internal Server Error due to a stale lockfile at `/tmp/service.lock` that persisted after a previous process crash.

## Symptoms

- Health endpoint returning 500 status code
- Error message: "stale lockfile present at /tmp/service.lock"
- Service was healthy before last deployment

## Root Cause

The service creates a lockfile at `/tmp/service.lock` on startup to prevent multiple instances. If the service crashes without cleanup, this lockfile persists and blocks subsequent startups, causing HTTP 500 errors.

## Diagnosis

Used `diagnose_service1` MCP tool (LOW risk - read-only) to confirm:
- Lockfile exists at `/tmp/service.lock`
- No owning process running
- HTTP status: 500

Manual verification command:
```bash
docker exec openhands-gepa-demo ls -la /tmp/service.lock
```

## Remediation

### Actions Taken

| Action | Risk Level | Rationale |
|--------|------------|-----------|
| `diagnose_service1` | LOW | Read-only diagnostic check |
| `fix_service1` | MEDIUM | Removes temp lockfile at `/tmp/service.lock` |
| `curl /service1` | LOW | Read-only verification |

### Fix Applied

Used `fix_service1` MCP tool to remove the stale lockfile:
```bash
rm -f /tmp/service.lock
```

**Risk Level**: MEDIUM - Removes a temporary file only; no data loss risk.

## Verification

1. Service returns HTTP 200 after fix
2. Response contains `"status": "ok"`
3. Lockfile is absent

```bash
curl -i https://TARGET_URL/service1
# Expected: HTTP 200 with {"status": "ok", "scenario": "stale_lockfile"}
```

## Prevention

- Implement proper signal handlers for graceful shutdown
- Use lockfile with PID check to detect stale locks automatically
- Add startup script to clean stale locks if owning process is not running

## References

- Skill: `.agents/skills/stale-lockfile/SKILL.md`
- MCP Tools: `diagnose_service1`, `fix_service1`
