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
1. Set missing variable in runtime context (demo-safe value)
2. Restart process/container if required

## Verification
1. `curl -i http://127.0.0.1:15000`
2. Confirm HTTP 200
