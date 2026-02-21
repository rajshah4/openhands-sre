---
name: stale-lockfile
description: Diagnose and remediate stale lockfile failures that return HTTP 500 after crashes.
triggers:
  - stale_lockfile
  - stale lock
  - lockfile
  - service.lock
---

# Stale Lockfile Recovery

## Diagnostic Workflow
1. Verify failure with `curl -i http://127.0.0.1:15000`
2. Check `/tmp/service.lock` and related lock files
3. Check lock owner process if tools are available (`fuser`/`lsof`)

## Remediation Workflow
1. Remove stale lock: `rm -f /tmp/service.lock`
2. Restart service only if still unhealthy

## Verification
1. `curl -i http://127.0.0.1:15000`
2. Confirm HTTP 200
3. Confirm lock file is absent
