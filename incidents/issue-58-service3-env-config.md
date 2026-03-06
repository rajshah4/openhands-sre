# Incident Report: Service3 Configuration Error

**Issue**: #58  
**Service**: service3  
**Endpoint**: `/service3`  
**Date**: 2026-03-02  
**Skill Used**: `bad-env-config`

## Summary

Service3 was returning HTTP 500 due to missing `REQUIRED_API_KEY` environment variable.

## Diagnosis

Using MCP diagnostic tools:

| Step | Tool | Result |
|------|------|--------|
| 1 | `get_all_service_status` | service3 returning HTTP 500 |
| 2 | `diagnose_service3` | Confirmed `REQUIRED_API_KEY` not set |

```json
{
  "service": "service3",
  "scenario": "bad_env_config",
  "http_status": "500",
  "healthy": false,
  "required_api_key_set": false,
  "diagnosis": "REQUIRED_API_KEY not set",
  "recommended_action": "fix_service3"
}
```

## Risk Assessment

| Action | Risk Level | Justification |
|--------|------------|---------------|
| `get_all_service_status` | LOW | Read-only health check |
| `diagnose_service3` | LOW | Read-only diagnosis |
| `fix_service3` | MEDIUM | Container restart required with env var |

## Remediation

Called `fix_service3` which returned instructions for container restart:

```bash
docker rm -f openhands-gepa-demo && docker run -d -p 15000:5000 -e REQUIRED_API_KEY=secret --name openhands-gepa-demo openhands-gepa-sre-target:latest
```

**Note**: This fix requires manual intervention as it involves restarting the container with the correct environment variable.

## Prevention

Added integration tests for the `bad_env_config` scenario to verify:
1. Service returns HTTP 500 when `REQUIRED_API_KEY` is missing
2. Service returns HTTP 200 when `REQUIRED_API_KEY` is properly set

## Verification

After remediation is applied:
- Service3 should return HTTP 200
- `/service3` endpoint should respond with `{"status": "ok", "scenario": "bad_env_config"}`
