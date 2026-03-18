# Incident Report: KAN-3 — service1 HTTP 500 (Stale Lockfile)

**Date**: 2026-03-18  
**Skill Used**: `stale-lockfile` (`.agents/skills/stale-lockfile/`)  
**Reporter**: openhands

---

## Diagnosis

`service1` (`/service1`) was returning HTTP 500. Diagnosis confirmed that a stale
lockfile at `/tmp/service.lock` (left behind by a previous crash) was blocking
the service from responding successfully.

### Tool Outputs

**1. Initial status check (`get_all_service_status`)**
```json
{
  "service1": { "path": "/service1", "http_code": "500", "healthy": false },
  "service2": { "path": "/service2", "http_code": "500", "healthy": false },
  "service3": { "path": "/service3", "http_code": "500", "healthy": false }
}
```

**2. Root-cause diagnosis (`diagnose_service1`)**
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

**3. Remediation (`fix_service1`)**
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

**4. Verification (`get_all_service_status`)**
```json
{
  "service1": { "path": "/service1", "http_code": "200", "healthy": true },
  "service2": { "path": "/service2", "http_code": "500", "healthy": false },
  "service3": { "path": "/service3", "http_code": "500", "healthy": false }
}
```

---

## Risk Assessment

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `get_all_service_status` | LOW | Read-only health check |
| `diagnose_service1` | LOW | Read-only — checks file existence and HTTP status |
| `fix_service1` (`rm -f /tmp/service.lock`) | MEDIUM | Removes a temp lockfile only; no persistent data affected. Auto-approved per AGENTS.md. |
| Post-fix `get_all_service_status` | LOW | Read-only verification |

---

## Resolution

The stale lockfile `/tmp/service.lock` was removed. `service1` recovered
immediately and now returns HTTP 200.

**Root cause**: Previous service crash left `/tmp/service.lock` in place.
`app.py` checks for this file on every request to `/service1` and returns
HTTP 500 while it exists.

**Prevention recommendation**: Consider adding a startup hook to the service
that clears `/tmp/service.lock` before the process begins accepting traffic,
so a clean restart always self-heals.
