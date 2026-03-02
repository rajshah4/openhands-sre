---
name: stale-lockfile
description: Diagnose and remediate stale lockfile failures that return HTTP 500 after crashes.
triggers:
  - stale_lockfile
  - stale lock
  - lockfile
  - service.lock
  - service1
---

# Stale Lockfile Recovery

**Applies to**: service1 (`/service1` endpoint)
**Risk Level**: MEDIUM (auto-approved — no human approval needed)

## How to Fix This

You have MCP tools available. They execute remotely on the server that has Docker access — you do NOT need Docker in your own environment. Just call the tools.

**Do this now, in order:**

1. **Call `get_all_service_status`** — confirm service1 is returning HTTP 500
2. **Call `diagnose_service1`** — confirms stale lockfile at `/tmp/service.lock`
3. **Call `fix_service1`** — removes the lockfile remotely (MEDIUM risk, auto-approved)
4. **Call `get_all_service_status`** — confirm service1 now returns HTTP 200

That's it. The MCP tools handle everything on the remote server. After verifying the fix, create a PR documenting the incident.

## Success Criteria
- `fix_service1` returns `"fixed": true`
- `get_all_service_status` shows service1 with `"http_code": "200"`
