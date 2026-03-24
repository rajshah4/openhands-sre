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

The MCP tools `get_all_service_status`, `diagnose_service2`, and `fix_service2` are in your tool list. They execute remotely — you do NOT need Docker or shell access. Just call them.

**Do this now. Paste the raw JSON from each tool call in your response.**

1. **Call `get_all_service_status`** — confirm service2 HTTP 500. Paste the JSON.
2. **Call `diagnose_service2`** — confirm ready flag missing. Paste the JSON.
3. **Call `fix_service2`** — creates the readiness flag. Paste the JSON. Must show `"fixed": true`.
4. **Call `get_all_service_status`** — confirm service2 HTTP 200. Paste the JSON.
5. Create a PR. The PR body MUST follow the **Incident Response Format** defined in `AGENTS.md`. Include:
    - Skill Used
    - Diagnosis (with tool outputs)
    - Risk Assessment
    - Remediation (with tool outputs)
    - Verification (with tool outputs)

## Success Criteria
- `fix_service2` returns `"fixed": true` and `"post_http_status": "200"`
- `get_all_service_status` shows service2 with `"http_code": "200"`
- Your response includes the actual JSON output from each tool call
