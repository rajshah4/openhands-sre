# Incident Report: Service1 HTTP 500 - Stale Lockfile

**Incident ID**: #38  
**Service**: service1 (health-api)  
**Endpoint**: `/service1`  
**Date**: 2026-03-02  
**Status**: Resolved  

## Skill Used

`stale-lockfile` - Diagnose and remediate stale lockfile failures that return HTTP 500 after crashes.

## Symptoms

- Health endpoint returning HTTP 500 status code
- Error message: "stale lockfile present at /tmp/service.lock"
- Service was healthy before last deployment

## Diagnosis

### MCP Tool: `diagnose_service1`

The diagnosis confirmed:
- **Lock file exists**: `/tmp/service.lock` was present
- **HTTP status**: 500 (Internal Server Error)
- **Root cause**: Stale lockfile from previous process crash blocking service startup

The lockfile mechanism is designed to prevent multiple instances from running simultaneously. However, when a process crashes without cleaning up, the lockfile remains ("stale"), blocking subsequent startups.

## Risk Assessment

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `diagnose_service1` | LOW | Read-only health check and file inspection |
| `rm -f /tmp/service.lock` | MEDIUM | Removes only temporary lockfile, service unaffected |
| `get_all_service_status` | LOW | Read-only health check |

**Overall Risk**: MEDIUM - Auto-approved per repository security policy in AGENTS.md

## Remediation

### MCP Tool: `fix_service1`

Executed the following fix:
```bash
docker exec openhands-gepa-demo rm -f /tmp/service.lock
```

**Action taken**: Removed the stale lockfile at `/tmp/service.lock`

### Actions Taken Summary

| Action | Risk | Rationale |
|--------|------|-----------|
| `diagnose_service1` | LOW | Read-only diagnosis to confirm issue |
| `fix_service1` (rm -f /tmp/service.lock) | MEDIUM | Removes temp lockfile only, standard remediation |
| `get_all_service_status` | LOW | Read-only verification of fix |

## Verification

### MCP Tool: `get_all_service_status`

Post-fix verification confirmed:
- **HTTP status**: 200 OK
- **Response**: `{"status": "ok", "scenario": "stale_lockfile"}`
- **Service health**: Restored

## Root Cause Analysis

The lockfile at `/tmp/service.lock` was left behind after an unclean process termination (crash, kill -9, or container restart). The service's startup logic checks for this file and refuses to start if it exists, as a safety mechanism against running multiple instances.

## Prevention Recommendations

1. **Graceful shutdown handling**: Ensure the service removes the lockfile in signal handlers (SIGTERM, SIGINT)
2. **Lockfile cleanup on startup**: Consider checking if the lockfile's owning PID is still running before refusing startup
3. **Container health checks**: Add liveness probes that can detect and alert on this condition earlier

## References

- Skill: `.agents/skills/stale-lockfile/SKILL.md`
- MCP Tools: `diagnose_service1`, `fix_service1`, `get_all_service_status`
- Security Policy: `AGENTS.md`
