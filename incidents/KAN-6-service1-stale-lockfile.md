# Incident Report: KAN-6 — service1 HTTP 500 (Stale Lockfile)

**Date**: 2026-03-19  
**Issue**: KAN-6  
**Skill Used**: `stale-lockfile` (`.agents/skills/stale-lockfile/`)  
**Severity**: P2 — Service Unavailable (HTTP 500)  
**Resolution Time**: < 5 minutes

---

## Diagnosis

`diagnose_service1` output:

```json
{
  "service": "service1",
  "scenario": "stale_lockfile",
  "http_status": "500",
  "healthy": false,
  "lock_file_exists": true,
  "diagnosis": "Stale lockfile present - needs removal",
  "recommended_action": "fix_service1"
}
```

**Root Cause**: A stale lockfile at `/tmp/service.lock` was left behind (likely from a previous crash or unclean shutdown). The service checks for this lockfile on startup/request handling and returns HTTP 500 when it exists, to prevent concurrent runs. Since the previous process no longer holds the lock, it is safe to remove.

---

## Risk Assessment

| Action | Risk Level | Rationale |
|--------|------------|-----------|
| `diagnose_service1` | LOW | Read-only health check — no state changes |
| `fix_service1` → `rm -f /tmp/service.lock` | MEDIUM | Removes a temp lockfile only; no data loss; auto-approved per AGENTS.md |
| `get_all_service_status` | LOW | Read-only verification — no state changes |

---

## Remediation

`fix_service1` output:

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

The stale lockfile `/tmp/service.lock` was removed successfully (`rm_returncode: 0`).

---

## Verification

`get_all_service_status` output after fix:

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

✅ **service1 is now returning HTTP 200 and is healthy.**

---

## Prevention Recommendations

1. Implement a lockfile cleanup routine in the service's startup script that checks if the lock-holding PID is still alive before failing.
2. Add a liveness/readiness probe in the deployment manifest that removes stale lockfiles on pod restart.
3. Consider using advisory locking mechanisms (e.g., `flock`) that are automatically released by the OS when the process terminates.
