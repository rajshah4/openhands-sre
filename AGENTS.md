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

- **LOW risk only**: Proceed without special notation
- **MEDIUM risk present**: Include risk table in response, explain safeguards
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
