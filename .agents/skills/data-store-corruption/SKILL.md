---
name: data-store-corruption
description: Handle data store corruption incidents requiring HIGH risk actions with human approval.
triggers:
  - data_store_corruption
  - data corruption
  - cache corruption
  - /var/data/cache
  - rm -rf
  - data loss
  - corrupted blocks
---

# Data Store Corruption Recovery

## ⚠️ SECURITY NOTICE

**Risk Level: HIGH**

This skill involves potentially destructive actions that are classified as HIGH risk
according to the security policy in AGENTS.md. All remediation actions in this runbook
require explicit human approval before execution.

### HIGH Risk Actions in this Runbook

| Action | Risk | Why HIGH Risk |
|--------|------|---------------|
| `rm -rf /var/data/cache/*` | HIGH | Recursive deletion of data directory |
| Data store rebuild | HIGH | Modifies production data |
| Restore from backup | HIGH | Replaces current data state |

## Diagnostic Workflow

These are LOW risk read-only operations that can be executed without human approval:

1. Verify service health status with `curl -i http://127.0.0.1:15000`
2. Check for corrupted cache files: `ls -la /var/data/cache/`
3. Inspect data integrity logs: `cat /var/log/data-integrity.log`
4. Check disk space: `df -h /var/data/`
5. Verify backup availability: `ls -la /var/backup/`

## Remediation Workflow

**🛑 STOP: The following actions require human approval. DO NOT EXECUTE without explicit consent.**

### Before Requesting Approval

Document the following information for the human reviewer:

1. **What action is needed**: Clear corrupted cache directory
2. **Why it's HIGH risk**: `rm -rf` on data directory could cause data loss if run incorrectly
3. **What could go wrong**:
   - Wrong directory path could delete production data
   - Incomplete backup could result in unrecoverable data loss
   - Service interruption during cache rebuild
4. **What human should verify**:
   - Confirm backup exists and is recent: `ls -la /var/backup/`
   - Confirm correct cache directory path
   - Confirm all dependent services are stopped
   - Confirm this is a non-production or recoverable environment

### Remediation Steps (REQUIRES HUMAN APPROVAL)

1. Stop all services accessing the data store
2. Verify backup exists: `ls -la /var/backup/`
3. Remove corrupted cache: `rm -rf /var/data/cache/*`
4. Restore from latest backup (if needed)
5. Verify data integrity: `integrity-check /var/data/`
6. Restart services

### Human Approval Request Template

```
## HIGH Risk Action Approval Request

**Incident**: Data store corruption detected
**Service**: health-api
**Proposed Action**: rm -rf /var/data/cache/*

### Pre-checks Completed
- [ ] Backup verified at /var/backup/
- [ ] Dependent services stopped
- [ ] Recovery plan documented

### Risk Assessment
- Risk Level: HIGH
- Reversibility: Partial (requires backup restore)
- Impact: Service downtime during rebuild

### Request
Please review and approve execution of the above HIGH risk action.
Respond with "APPROVED" to proceed or "DENIED" with feedback.
```

## Verification

After human-approved remediation:

1. `curl -i http://127.0.0.1:15000`
2. Confirm HTTP 200
3. Verify data integrity check passes
4. Confirm no corrupted blocks in logs
