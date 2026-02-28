#!/usr/bin/env python3
"""
Create a GitHub issue to trigger OpenHands Cloud for the outer loop demo.

Usage:
    # Create issue with openhands label (triggers OpenHands Cloud)
    python scripts/create_demo_issue.py

    # Create issue without label (for manual triggering)
    python scripts/create_demo_issue.py --no-label

    # Dry run (just print what would be created)
    python scripts/create_demo_issue.py --dry-run

Requirements:
    - gh CLI installed and authenticated
    - Repository: rajshah4/openhands-sre
"""

import argparse
import subprocess
import sys
from datetime import datetime


REPO = "rajshah4/openhands-sre"

SCENARIOS = {
    "stale_lockfile": {
        "title": "🚨 Incident: Service returning HTTP 500 - stale lockfile suspected",
        "body": """## Incident Report

**Service**: health-api
**Status**: HTTP 500 Internal Server Error
**Time Detected**: {timestamp}

### Symptoms
- Health endpoint returning 500 status code
- Error message indicates: "stale lockfile present at /tmp/service.lock"
- Service was healthy before last deployment

### Logs
```
[ERROR] Service startup blocked by existing lockfile
[ERROR] /tmp/service.lock exists but owning process is not running
[ERROR] Health check failed: stale lockfile present
```

### Expected Behavior
Service should return HTTP 200 with healthy status.

### Environment
- Container: `openhands-gepa-demo`
- Target URL: `http://127.0.0.1:15000`

---

**Please diagnose and remediate this incident using the appropriate SRE skill.**
""",
    },
    "readiness_probe_fail": {
        "title": "🚨 Incident: Readiness probe failing - service not ready",
        "body": """## Incident Report

**Service**: health-api  
**Status**: HTTP 500 - Readiness probe failure
**Time Detected**: {timestamp}

### Symptoms
- Readiness probe returning 500 status
- Service appears to have started but is not ready to serve traffic
- Missing readiness flag file

### Logs
```
[ERROR] Readiness check failed: /tmp/ready.flag not found
[ERROR] Service started but readiness conditions not met
```

### Expected Behavior
Service should create readiness flag and return HTTP 200.

### Environment
- Container: `openhands-gepa-demo`
- Target URL: `http://127.0.0.1:15000`

---

**Please diagnose and remediate this incident using the appropriate SRE skill.**
""",
    },
}


def create_issue(scenario: str, add_label: bool, dry_run: bool) -> None:
    if scenario not in SCENARIOS:
        print(f"Unknown scenario: {scenario}")
        print(f"Available: {list(SCENARIOS.keys())}")
        sys.exit(1)

    config = SCENARIOS[scenario]
    title = config["title"]
    body = config["body"].format(timestamp=datetime.now().isoformat())

    print(f"{'[DRY RUN] ' if dry_run else ''}Creating issue in {REPO}")
    print(f"  Title: {title}")
    print(f"  Scenario: {scenario}")
    print(f"  Label: {'openhands' if add_label else '(none)'}")
    print()

    if dry_run:
        print("--- Issue Body ---")
        print(body)
        print("--- End Body ---")
        return

    cmd = [
        "gh", "issue", "create",
        "--repo", REPO,
        "--title", title,
        "--body", body,
    ]

    if add_label:
        cmd.extend(["--label", "openhands"])

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        issue_url = result.stdout.strip()
        print(f"✅ Issue created: {issue_url}")
        print()
        if add_label:
            print("🚀 OpenHands Cloud should pick this up automatically!")
            print("   Watch for a comment from @openhands on the issue.")
        else:
            print("ℹ️  No label added. To trigger OpenHands:")
            print("   - Add the 'openhands' label, OR")
            print("   - Comment '@openhands' on the issue")
    else:
        print(f"❌ Failed to create issue:")
        print(result.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Create a GitHub issue to trigger OpenHands Cloud demo"
    )
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="stale_lockfile",
        help="Incident scenario to create (default: stale_lockfile)",
    )
    parser.add_argument(
        "--no-label",
        action="store_true",
        help="Don't add the 'openhands' label (won't auto-trigger)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without actually creating",
    )

    args = parser.parse_args()
    create_issue(args.scenario, not args.no_label, args.dry_run)


if __name__ == "__main__":
    main()
