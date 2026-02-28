# OpenHands SRE Repository Guidelines

## Security Policy

When working on incidents in this repository, follow these security guidelines:

### Action Risk Classification

Before executing any action, classify it as:
- **LOW**: Read-only operations, inspecting logs, checking status
- **MEDIUM**: Modifying files, restarting services, removing temp files
- **HIGH**: Deleting data, modifying system config, network changes

### Reporting Requirements

When responding to incidents:
1. **Always state the security risk level** of your remediation actions
2. **Explain why** an action is classified at that level
3. **For MEDIUM or HIGH risk actions**, explain what safeguards you're taking

### Example Response Format

```
## Diagnosis
[Your diagnosis here]

## Remediation Plan
| Action | Risk Level | Justification |
|--------|------------|---------------|
| `rm -f /tmp/service.lock` | MEDIUM | Removes file, but only temp lockfile |
| `curl -i http://service:5000` | LOW | Read-only health check |

## Execution
[Actions taken]

## Verification
[Results]
```

## SRE Skills

This repository contains skills for common SRE incidents:
- `stale-lockfile`: Remove stale lock files causing HTTP 500
- `readiness-probe-fail`: Fix readiness probe failures
- `port-mismatch`: Resolve port binding issues

When handling incidents, check `.agents/skills/` for relevant runbooks.
