# Incident Report: INC-30 - Service1 Stale Lockfile

## Incident Summary

| Field | Value |
|-------|-------|
| **Incident ID** | INC-30 |
| **Service** | service1 (health-api) |
| **Endpoint** | `/service1` |
| **Status** | RESOLVED |
| **Severity** | P3 |
| **Time Detected** | 2026-03-02T11:03:47.816014 |
| **Time Resolved** | 2026-03-02T17:04:00 |

## Skill Used

**stale-lockfile** - Diagnose and remediate stale lockfile failures that return HTTP 500 after crashes.

## Symptoms

- Health endpoint returning HTTP 500 status code
- Error message: "stale lockfile present at /tmp/service.lock"
- Service was healthy before last deployment

## Diagnosis

### Diagnostic Steps Taken

| Action | Risk Level | Result |
|--------|------------|--------|
| `curl -i $TARGET_URL/service1` | LOW | HTTP 500 - Confirmed failure |
| `diagnose_service1` MCP tool | LOW | Lockfile exists at /tmp/service.lock |

### Root Cause

The service experienced an unexpected shutdown or crash, leaving behind a stale lockfile at `/tmp/service.lock`. The service's health check logic detects this lockfile and returns HTTP 500 to prevent duplicate instances from running.

## Remediation

### Actions Taken

| Action | Risk Level | Rationale |
|--------|------------|-----------|
| `fix_service1` MCP tool (executes `rm -f /tmp/service.lock`) | MEDIUM | Removes stale lockfile; MEDIUM risk as it deletes a file, but only a temp lockfile |

### Manual Equivalent

```bash
docker exec openhands-gepa-demo rm -f /tmp/service.lock
```

## Verification

| Check | Expected | Actual |
|-------|----------|--------|
| `curl -i $TARGET_URL/service1` | HTTP 200 | HTTP 200 ✓ |
| Response body | `{"status": "ok"}` | `{"status": "ok"}` ✓ |
| Lockfile absent | File does not exist | Confirmed ✓ |

## Prevention

1. **Graceful shutdown handlers**: Ensure the service removes its lockfile during normal shutdown
2. **Startup lockfile cleanup**: Consider adding startup logic to detect and clean stale lockfiles from crashed processes
3. **Process monitoring**: Implement PID-based lockfile validation to distinguish between active locks and stale ones

## Related

- Skill: `.agents/skills/stale-lockfile/SKILL.md`
- MCP Tools: `diagnose_service1`, `fix_service1`
- Test: `tests/test_integration.py::test_stale_lockfile_recovers_500_to_200`
