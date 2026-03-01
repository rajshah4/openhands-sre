#!/usr/bin/env sh
set -eu

# Reset artifacts on each boot for deterministic failures.
rm -f /tmp/service.lock /tmp/ready.flag

# If SCENARIO is set, use single-scenario mode (legacy)
# If SCENARIO is not set, use multi-scenario mode (all paths work)
if [ -n "${SCENARIO:-}" ]; then
  case "$SCENARIO" in
    stale_lockfile)
      touch /tmp/service.lock
      ;;
    bad_env_config)
      # Intentionally leave REQUIRED_API_KEY unset.
      unset REQUIRED_API_KEY || true
      ;;
    readiness_probe_fail)
      # Intentionally omit /tmp/ready.flag.
      ;;
    port_mismatch)
      # app.py handles mismatch by binding to :5001.
      ;;
    *)
      echo "Unknown SCENARIO=$SCENARIO" >&2
      ;;
  esac
fi

# Multi-scenario mode: no SCENARIO env var means all paths work independently
# Each path (/service1, /service2, /service3) checks its own conditions

exec python /app/app.py
