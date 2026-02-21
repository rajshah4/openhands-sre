---
name: port-mismatch
description: Diagnose and resolve mismatches between expected probe port and actual bind port.
triggers:
  - port_mismatch
  - wrong port
  - listening port
  - "5001"
---

# Port Mismatch Recovery

## Diagnostic Workflow
1. Verify probe failure with `curl -i http://127.0.0.1:15000`
2. Inspect listening sockets (`ss -lntp || netstat -lnt || lsof -iTCP -sTCP:LISTEN -n -P`)
3. Compare expected probe port vs bound process port

## Remediation Workflow
1. Align service bind configuration with expected probe port
2. If needed, apply temporary forwarding only as mitigation

## Verification
1. `curl -i http://127.0.0.1:15000`
2. Confirm HTTP 200 on expected endpoint
