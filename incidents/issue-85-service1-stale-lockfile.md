# Incident Report: Issue #85 — service1 Stale Lockfile

**Date**: 2026-03-16  
**Skill Used**: `stale-lockfile` (`.agents/skills/stale-lockfile/SKILL.md`)

## Diagnosis

### Step 1 — `get_all_service_status`
```json
{
  "service1": { "path": "/service1", "http_code": "500", "healthy": false },
  "service2": { "path": "/service2", "http_code": "200", "healthy": true },
  "service3": { "path": "/service3", "http_code": "200", "healthy": true }
}
```

### Step 2 — `diagnose_service1`
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

Root cause confirmed: `/tmp/service.lock` was left behind by a previous crash, causing `service1` to return HTTP 500.

## Risk Assessment

| Action | Risk | Rationale |
|--------|------|-----------|
| `diagnose_service1` | LOW | Read-only check |
| `fix_service1` (removes `/tmp/service.lock`) | MEDIUM (auto-approved) | Removes temp file only; service is unaffected |

## Remediation

### Step 3 — `fix_service1`
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

## Verification

### Step 4 — `get_all_service_status` (post-fix)
```json
{
  "service1": { "path": "/service1", "http_code": "200", "healthy": true },
  "service2": { "path": "/service2", "http_code": "200", "healthy": true },
  "service3": { "path": "/service3", "http_code": "200", "healthy": true }
}
```

All services healthy. `service1` now returns HTTP 200 as expected.

## Test Coverage

The integration test `test_stale_lockfile_recovers_500_to_200` in `tests/test_integration.py` validates this exact recovery path: it confirms the service returns 500 with the lockfile present and 200 after removal.
