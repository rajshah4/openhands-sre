# Incident Report: service1 HTTP 500 - Stale Lockfile

**Incident ID**: #48
**Service**: service1 (health-api)
**Endpoint**: `/service1`
**Status**: ✅ RESOLVED
**Time Detected**: 2026-03-02T13:54:36.675375
**Time Resolved**: 2026-03-02T19:56:19 UTC

---

## Skill Used

**stale-lockfile** - Diagnose and remediate stale lockfile failures that return HTTP 500 after crashes.

---

## Symptoms

- Health endpoint `/service1` returning HTTP 500 Internal Server Error
- Error message: `"stale lockfile present at /tmp/service.lock"`

## Expected Behavior

Service should return HTTP 200 with `"status": "ok"`.

---

## Diagnosis

### Step 1: get_all_service_status

Confirmed service1 was returning HTTP 500:

```json
{
  "service1": { "path": "/service1", "http_code": "500", "healthy": false },
  "service2": { "path": "/service2", "http_code": "500" },
  "service3": { "path": "/service3", "http_code": "500" }
}
```

### Step 2: diagnose_service1

Confirmed stale lockfile exists at `/tmp/service.lock`:

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
| `rm -f /tmp/service.lock` | MEDIUM | Removes temp file only, service unaffected. Auto-approved per AGENTS.md |

---

## Remediation

### Step 3: fix_service1

Removed the stale lockfile:

```json
{
  "service": "service1",
  "action": "rm -f /tmp/service.lock",
  "risk_level": "MEDIUM",
  "pre_http_status": "500",
  "post_http_status": "200",
  "fixed": true,
  "rm_returncode": 0
}
```

---

## Verification

### Step 4: get_all_service_status (post-fix)

Confirmed service1 is now returning HTTP 200:

```json
{
  "service1": { "path": "/service1", "http_code": "200", "healthy": true },
  "service2": { "path": "/service2", "http_code": "500" },
  "service3": { "path": "/service3", "http_code": "500" }
}
```

---

## Root Cause

A previous service crash left behind a stale lockfile at `/tmp/service.lock`. The service health check detected this file and returned HTTP 500 to prevent concurrent instances.

## Resolution

The stale lockfile was removed using `rm -f /tmp/service.lock`, which restored the service to healthy state (HTTP 200).

## Preventive Measures

1. Consider implementing automatic lockfile cleanup on service startup
2. Add monitoring alerts for lockfile age
3. Document lockfile cleanup procedure in runbook

---

## Actions Taken

| Action | Risk | Rationale |
|--------|------|-----------|
| `curl -i http://service:5000/service1` | LOW | Read-only health check |
| `ls -la /tmp/service.lock` | LOW | Read-only file check |
| `rm -f /tmp/service.lock` | MEDIUM | Removes temp file only, service unaffected |
