---
name: readiness-probe-fail
description: Resolve readiness probe failures when startup appears successful but health checks fail.
triggers:
  - readiness_probe_fail
  - readiness
  - ready.flag
  - probe fail
---

# Readiness Probe Recovery

## Diagnostic Workflow
1. Verify failure with `curl -i http://127.0.0.1:15000`
2. Check readiness artifacts (e.g., `/tmp/ready.flag`)
3. Confirm readiness conditions in service code

## Remediation Workflow
1. Restore required readiness artifact/state
2. Restart only if readiness is initialized at boot

## Verification
1. `curl -i http://127.0.0.1:15000`
2. Confirm HTTP 200 and healthy readiness signal
