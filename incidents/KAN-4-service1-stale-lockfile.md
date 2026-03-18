# Incident Report: KAN-4 — Service1 HTTP 500 (Stale Lockfile)

**Date**: 2026-03-18  
**Skill Used**: `stale-lockfile` (`.agents/skills/stale-lockfile/`)  
**Severity**: P2 — Service returning HTTP 500  
**Status**: Resolved ✅

---

## Diagnosis

Service1 was returning HTTP 500. Diagnosis confirmed a stale lockfile at `/tmp/service.lock` left over from a previous crash, blocking the service from starting correctly.

**`diagnose_service1` output:**
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

---

## Risk Assessment

| Action | Risk Level | Rationale |
|--------|------------|-----------|
| `diagnose_service1` | LOW | Read-only health check — no state changes |
| `fix_service1` (`rm -f /tmp/service.lock`) | MEDIUM (auto-approved) | Removes only a temporary lockfile; the service is not affected during removal and recovers automatically |
| `get_all_service_status` | LOW | Read-only verification check |

---

## Remediation

Called `fix_service1` to remove the stale lockfile.

**`fix_service1` output:**
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

---

## Verification

**`get_all_service_status` output (post-fix):**
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

Service1 is now returning HTTP 200 and is healthy. ✅

---

## Root Cause

The service uses a lockfile (`/tmp/service.lock`) to prevent concurrent starts. When the process crashes or is killed uncleanly, the lockfile is not removed, causing subsequent start attempts to fail with HTTP 500.

## Prevention Recommendations

1. Add a startup script that removes stale lockfiles older than a configurable threshold before the service starts.
2. Implement a liveness probe that detects lockfile presence without a running PID and triggers automatic cleanup.
