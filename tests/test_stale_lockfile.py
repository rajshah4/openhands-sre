"""Unit tests for the stale-lockfile scenario on /service1.

These tests exercise the Flask app directly via its test client and do NOT
require Docker, making them fast and suitable for CI without container access.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Make the target_service package importable without a Docker build.
TARGET_SERVICE_DIR = Path(__file__).resolve().parents[1] / "target_service"
if str(TARGET_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(TARGET_SERVICE_DIR))


class StaleLockfileUnitTests(unittest.TestCase):
    """Test /service1 behaviour with and without the lockfile present."""

    def _make_app(self, lockfile: str):
        """Import (or re-import) app.py with LOCKFILE pointing to *lockfile*."""
        # Remove any previously cached module so patching takes effect.
        sys.modules.pop("app", None)
        with patch.dict(os.environ, {"SCENARIO": ""}):
            import app as service_app  # noqa: PLC0415
            service_app.LOCKFILE = lockfile
            service_app.READY_FILE = lockfile + ".ready"
            return service_app.app.test_client()

    def test_service1_returns_500_when_lockfile_present(self) -> None:
        """service1 must return HTTP 500 while /tmp/service.lock exists."""
        with tempfile.NamedTemporaryFile(suffix=".lock", delete=False) as f:
            lock_path = f.name
        try:
            client = self._make_app(lock_path)
            response = client.get("/service1")
            self.assertEqual(response.status_code, 500)
        finally:
            os.unlink(lock_path)

    def test_service1_returns_200_after_lockfile_removed(self) -> None:
        """service1 must return HTTP 200 once the stale lockfile is removed."""
        with tempfile.NamedTemporaryFile(suffix=".lock", delete=False) as f:
            lock_path = f.name

        # First confirm it is unhealthy while the file exists.
        client = self._make_app(lock_path)
        self.assertEqual(client.get("/service1").status_code, 500)

        # Remove the lockfile (the remediation step).
        os.unlink(lock_path)

        # Now confirm it recovers to healthy.
        self.assertEqual(client.get("/service1").status_code, 200)

    def test_service1_returns_200_when_no_lockfile(self) -> None:
        """service1 must return HTTP 200 when no lockfile exists at startup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = os.path.join(tmpdir, "nonexistent.lock")
            client = self._make_app(lock_path)
            self.assertEqual(client.get("/service1").status_code, 200)


if __name__ == "__main__":
    unittest.main()
