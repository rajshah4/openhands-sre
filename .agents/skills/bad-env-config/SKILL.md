---
name: bad-env-config
description: Handle service failures caused by missing or invalid required environment variables.
triggers:
  - bad_env_config
  - required_api_key
  - missing env
  - env config
  - service3
---

# Environment Config Recovery

**Applies to**: service3 (`/service3` endpoint)
**Risk Level**: MEDIUM

## How to Fix This

You have MCP tools available. They execute remotely on the server that has Docker access — you do NOT need Docker in your own environment. Just call the tools.

**Do this now, in order:**

1. **Call `get_all_service_status`** — confirm service3 is returning HTTP 500
2. **Call `diagnose_service3`** — confirms `REQUIRED_API_KEY` is not set
3. **Call `fix_service3`** — returns instructions for container restart with env var (MEDIUM risk)
4. **Call `get_all_service_status`** — check if fix was applied

Note: `fix_service3` may require a container restart with the correct env var. The tool will return instructions. This is the one scenario that may need manual follow-up.

## Success Criteria
- `diagnose_service3` confirms the missing env var
- `fix_service3` returns remediation instructions
- Service3 returns HTTP 200 after remediation
