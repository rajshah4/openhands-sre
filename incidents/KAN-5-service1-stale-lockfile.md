# Incident Report: KAN-5 — Service1 Stale Lockfile

**Date**: 2026-03-18  
**Skill Used**: `stale-lockfile` (`.agents/skills/stale-lockfile/`)  
**Severity**: Medium  
**Status**: Resolved ✅

---

## Diagnosis

Service1 (`/service1`) was returning HTTP 500. Diagnosis confirmed a stale lockfile
at `/tmp/service.lock` left behind from a previous crash. The application's health
check in `target_service/app.py` returns 500 whenever this file is present.

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

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `diagnose_service1` | LOW | Read-only — checks lockfile presence and HTTP status |
| `fix_service1` (`rm -f /tmp/service.lock`) | MEDIUM | Removes temp file only; scoped to service1; auto-approved per AGENTS.md |
| `get_all_service_status` (verification) | LOW | Read-only health check |

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
  "service1": { "path": "/service1", "http_code": "200", "healthy": true },
  "service2": { "path": "/service2", "http_code": "500", "healthy": false },
  "service3": { "path": "/service3", "http_code": "500", "healthy": false }
}
```

Service1 is fully healthy, returning HTTP 200. ✅
