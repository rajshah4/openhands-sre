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

## Execution Modes
- Manual runbook: follow the shell steps below.
- Executable helper path: run the skill code directly.

Skill helper files:
- `diagnose.py`
- `remediate.py`
- `skill.py` (exports `diagnose` and `remediate`)

Examples:
- `TARGET_URL=http://127.0.0.1:15000 TARGET_CONTAINER=openhands-gepa-demo python .agents/skills/stale-lockfile/diagnose.py`
- `TARGET_URL=http://127.0.0.1:15000 TARGET_CONTAINER=openhands-gepa-demo python .agents/skills/stale-lockfile/remediate.py`
- `cd .agents/skills/stale-lockfile && python -c "from skill import diagnose, remediate; print(diagnose()); print(remediate())"`

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
