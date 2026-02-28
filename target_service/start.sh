#!/usr/bin/env sh
set -eu

SCENARIO="${SCENARIO:-stale_lockfile}"

# Reset artifacts on each boot for deterministic failures.
rm -f /tmp/service.lock /tmp/ready.flag

case "$SCENARIO" in
  stale_lockfile)
    touch /tmp/service.lock
    ;;
  bad_env_config)
    # Intentionally leave REQUIRED_API_KEY unset.
    unset REQUIRED_API_KEY || true
    ;;
  readiness_probe_fail)
    # Create the readiness flag so the service is healthy and ready to serve traffic.
    touch /tmp/ready.flag
    ;;
  port_mismatch)
    # app.py handles mismatch by binding to :5001.
    ;;
  *)
    echo "Unknown SCENARIO=$SCENARIO" >&2
    ;;
esac

exec python /app/app.py
