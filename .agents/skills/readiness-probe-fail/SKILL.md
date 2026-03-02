---
name: readiness-probe-fail
description: Resolve readiness probe failures when startup appears successful but health checks fail.
triggers:
  - readiness_probe_fail
  - readiness
  - ready.flag
  - probe fail
  - service2
---

# Readiness Probe Recovery

**Applies to**: service2 (`/service2` endpoint)
**Risk Level**: LOW (auto-approved)

## How to Fix This

You have MCP tools available. They execute remotely on the server that has Docker access — you do NOT need Docker in your own environment. Just call the tools.

**Do this now, in order:**

1. **Call `get_all_service_status`** — confirm service2 is returning HTTP 500
2. **Call `diagnose_service2`** — confirms `/tmp/ready.flag` is missing
3. **Call `fix_service2`** — creates the readiness flag remotely (LOW risk)
4. **Call `get_all_service_status`** — confirm service2 now returns HTTP 200

That's it. The MCP tools handle everything on the remote server. After verifying the fix, create a PR documenting the incident.

## Success Criteria
- `fix_service2` returns `"fixed": true`
- `get_all_service_status` shows service2 with `"http_code": "200"`
