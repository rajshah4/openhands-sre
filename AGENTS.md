# OpenHands SRE Agent Guidelines

## Repository Overview

This repository contains SRE skills for automated incident remediation. Skills are located in `.agents/skills/` and provide runbooks for common incident types.

## Security Policy

**All actions must be classified by security risk level before execution.**

### Risk Levels

| Level | Description | Examples | Approval |
|-------|-------------|----------|----------|
| **LOW** | Read-only, non-destructive | `curl`, `ls`, `cat`, `grep`, health checks | Auto-approved |
| **MEDIUM** | Modifies state, reversible | `rm` temp files, `touch`, restart services | Report in response |
| **HIGH** | Potentially destructive, hard to reverse | `rm -rf`, system config changes, data deletion | Requires justification |

### Reporting Requirements

When executing remediation actions:

1. **State the risk level** for each action you take
2. **Explain your reasoning** for MEDIUM or HIGH risk actions
3. **Use this format** in your responses:

```
### Actions Taken

| Action | Risk | Rationale |
|--------|------|-----------|
| `curl -i http://service:5000` | LOW | Read-only health check |
| `rm -f /tmp/service.lock` | MEDIUM | Removes temp file only, service unaffected |
```

### Policy Triggers

- **LOW risk only**: Proceed and execute without special notation
- **MEDIUM risk present**: **EXECUTE the action**, then include risk table in response explaining what was done
- **HIGH risk present**: **STOP IMMEDIATELY. DO NOT EXECUTE.** Request human review with:
  1. What action would be needed
  2. Why it's classified as HIGH risk
  3. What could go wrong
  4. What human should verify before approving

### HIGH Risk Actions (Always Require Human Approval)

The following actions are ALWAYS HIGH risk and must NOT be executed without explicit human approval:
- `rm -rf` on any directory
- Modifying production configuration files
- Database schema changes or data deletion
- Restarting critical infrastructure services
- Network/firewall rule changes
- Any action affecting multiple services simultaneously

## MCP Tools (Infrastructure Execution)

**⚠️ CRITICAL: When MCP tools are available, you MUST use them to execute real fixes on live infrastructure. Do NOT just document fixes — actually call the fix tools.**

The MCP tools execute commands inside the demo Docker container. They are the primary way to diagnose and remediate incidents:

| Tool | Description | Risk Level |
|------|-------------|------------|
| `get_all_service_status` | Quick health check of all services | LOW |
| `diagnose_service1` | Diagnose stale lockfile issue | LOW |
| `diagnose_service2` | Diagnose readiness probe issue | LOW |
| `diagnose_service3` | Diagnose env config issue | LOW |
| `fix_service1` | Remove `/tmp/service.lock` | MEDIUM |
| `fix_service2` | Create `/tmp/ready.flag` | LOW |
| `fix_service3` | Returns instructions (needs restart) | MEDIUM |

### Required Workflow for Incidents

When an incident issue mentions MCP tools, follow this exact sequence:

1. **Diagnose** — Call the appropriate `diagnose_serviceN` tool
2. **Fix** — Call the appropriate `fix_serviceN` tool to execute the remediation
3. **Verify** — Call `get_all_service_status` or `diagnose_serviceN` again to confirm the fix worked
4. **Document** — Create a PR with the incident report and risk assessment

**Do NOT skip step 2.** The fix tools are MEDIUM risk at most and are auto-approved per the security policy above. Documenting a fix without executing it leaves the service broken.

## Available Skills

| Skill | Trigger Keywords | Risk Level |
|-------|-----------------|------------|
| `stale-lockfile` | stale lock, service.lock, lockfile | MEDIUM |
| `readiness-probe-fail` | readiness, ready.flag, probe fail | LOW |
| `port-mismatch` | wrong port, port mismatch, 5001 | LOW-MEDIUM |
| `bad-env-config` | env config, missing env, API key | MEDIUM |

## Incident Response Format

When responding to incidents, use this structure:

```
## Skill Used
[Name the skill from `.agents/skills/` that matches this incident, e.g., "stale-lockfile", "readiness-probe-fail"]

## Diagnosis
[What you found]

## Risk Assessment
[Risk level of planned actions and why]

## Remediation
[Actions taken with risk annotations]

## Verification
[How you confirmed the fix worked]
```

**Important**: Always identify which skill from `.agents/skills/` you are using and reference the runbook. This provides audit trail and traceability.
