# Incident Report: KAN-9 — service1 HTTP 500 (Stale Lockfile)

**Date**: 2026-04-01  
**Issue Key**: KAN-9  
**Severity**: P2 (service returning HTTP 500)  
**Skill Used**: `stale-lockfile` (`.agents/skills/stale-lockfile/`)

---

## Skill Used

`stale-lockfile` — Diagnose and remediate stale lockfile failures that return HTTP 500 after crashes.  
Runbook: `.agents/skills/stale-lockfile/SKILL.md`

---

## Diagnosis

`get_all_service_status` output:
```json
{
  "service1": { "path": "/service1", "http_code": "500", "healthy": false },
  "service2": { "path": "/service2", "http_code": "500", "healthy": false },
  "service3": { "path": "/service3", "http_code": "500", "healthy": false }
}
```

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

**Root cause**: A stale lock file (`/tmp/service.lock`) was left behind by a previous crash. The service checks for this file at startup and returns HTTP 500 when it exists.

---

## Risk Assessment

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `get_all_service_status` | LOW | Read-only health check |
| `diagnose_service1` | LOW | Read-only diagnostic check |
| `fix_service1` (`rm -f /tmp/service.lock`) | MEDIUM | Removes a temporary lock file only; no production data at risk; reversible |
| `get_all_service_status` (verification) | LOW | Read-only health check |

Per `AGENTS.md`, MEDIUM risk actions for stale-lockfile removal are **auto-approved**.

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

The stale lockfile `/tmp/service.lock` was removed via the `fix_service1` MCP tool.

---

## Verification

`get_all_service_status` after fix:
```json
{
  "service1": { "path": "/service1", "http_code": "200", "healthy": true },
  "service2": { "path": "/service2", "http_code": "500", "healthy": false },
  "service3": { "path": "/service3", "http_code": "500", "healthy": false }
}
```

✅ **service1 is now returning HTTP 200 and is healthy.**
