# Incident Report: service1 Stale Lockfile (Issue #76)

**Date**: 2026-03-16T19:30:16 UTC
**Severity**: High (service unavailable)
**Service**: service1 (health-api) — `/service1`
**Skill Used**: `stale-lockfile` (`.agents/skills/stale-lockfile/SKILL.md`)

---

## Diagnosis

service1 was returning HTTP 500 due to a stale lockfile at `/tmp/service.lock`.

## Risk Assessment

| Action | Risk Level | Rationale |
|--------|------------|-----------|
| `get_all_service_status` | LOW | Read-only health check |
| `diagnose_service1` | LOW | Read-only diagnostic check |
| `fix_service1` (`rm -f /tmp/service.lock`) | MEDIUM | Removes temp file only — auto-approved per AGENTS.md |
| `get_all_service_status` (post-fix) | LOW | Read-only verification |

## Remediation

### Step 1 — Baseline status (`get_all_service_status`)

```json
{
  "service1": { "path": "/service1", "http_code": "500", "healthy": false },
  "service2": { "path": "/service2", "http_code": "200", "healthy": true },
  "service3": { "path": "/service3", "http_code": "200", "healthy": true }
}
```

### Step 2 — Diagnosis (`diagnose_service1`)

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

### Step 3 — Fix (`fix_service1`)

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

### Step 4 — Verification (`get_all_service_status`)

```json
{
  "service1": { "path": "/service1", "http_code": "200", "healthy": true },
  "service2": { "path": "/service2", "http_code": "200", "healthy": true },
  "service3": { "path": "/service3", "http_code": "200", "healthy": true }
}
```

## Verification

All services healthy. service1 now returns HTTP 200 with `"status": "ok"`.
