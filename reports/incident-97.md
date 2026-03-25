# Incident 97: service1 stale lockfile

## Summary
Service1 returned HTTP 500 due to a stale lockfile at `/tmp/service.lock`. The lockfile was removed via the MCP remediation tool and service1 recovered to HTTP 200.

## Diagnosis
- `/service1` responded with HTTP 500.
- MCP diagnosis confirmed a stale lockfile at `/tmp/service.lock`.

## Risk Assessment
- **MEDIUM**: Removing `/tmp/service.lock` is a reversible action that modifies service state.

## Remediation
- Executed MCP `fix_service1` to remove the stale lockfile.

## Verification
- MCP status check confirmed `/service1` returned HTTP 200.
- `get_all_service_status` outputs also include service2/service3 failures that were pre-existing and out of scope for incident 97.

## MCP Tool Outputs

### 1) get_all_service_status (pre-fix)
```json
{
  "service1": {
    "path": "/service1",
    "http_code": "500",
    "healthy": false
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

### 2) diagnose_service1
```json
{
  "service": "service1",
  "scenario": "stale_lockfile",
  "http_status": "500",
  "healthy": false,
  "lock_file_exists": true,
  "diagnosis": "Stale lockfile present - needs removal",
  "recommended_action": "fix_service1",
  "next_step": "IMPORTANT: Call the fix_service1 tool NOW to remove the lockfile. This is MEDIUM risk and auto-approved per AGENTS.md."
}
```

### 3) fix_service1
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

### 4) get_all_service_status (post-fix)
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
