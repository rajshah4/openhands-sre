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

The MCP tools `get_all_service_status`, `diagnose_service1`, and `fix_service1` are in your tool list. They execute remotely — you do NOT need Docker or shell access. Just call them.

**Do this now. Paste the raw JSON from each tool call in your response.**

1. **Call `get_all_service_status`** — confirm service1 HTTP 500. Paste the JSON.
2. **Call `diagnose_service1`** — confirm lockfile exists. Paste the JSON.
3. **Call `fix_service1`** — removes the lockfile. Paste the JSON. Must show `"fixed": true`.
4. **Call `get_all_service_status`** — confirm service1 HTTP 200. Paste the JSON.
5. Create a PR. The PR body MUST follow the **Incident Response Format** defined in `AGENTS.md`. Include:
    - Skill Used
    - Diagnosis (with tool outputs)
    - Risk Assessment
    - Remediation (with tool outputs)
    - Verification (with tool outputs)

## Success Criteria
- `fix_service1` returns `"fixed": true` and `"post_http_status": "200"`
- `get_all_service_status` shows service1 with `"http_code": "200"`
- Your response includes the actual JSON output from each tool call
