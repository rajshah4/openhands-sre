---
name: bad-env-config
description: Handle service failures caused by missing or invalid required environment variables.
triggers:
  - bad_env_config
  - required_api_key
  - missing env
  - env config
---

# Environment Config Recovery

## Diagnostic Workflow
1. Verify failure with `curl -i http://127.0.0.1:15000`
2. Inspect `REQUIRED_API_KEY` and related environment values
3. Confirm expected env behavior in code/config

## Remediation Workflow
1. Apply a fix at the correct persistence boundary:
   - process-level fixes require process restart
   - container-level env fixes require container recreate/restart with env set
2. Avoid non-persistent fixes (for example, setting env in a one-off shell that does not affect the serving process).
3. Use the smallest durable change that survives verification.
4. Re-check health from host with `curl -i http://127.0.0.1:15000`

Notes:
- For this demo target, env requirements are enforced by the running app process.
- The objective is a durable recovery, not a one-command shortcut.

## Verification
1. `curl -i http://127.0.0.1:15000`
2. Confirm HTTP 200
