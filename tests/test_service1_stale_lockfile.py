"""Unit tests for service1 stale-lockfile scenario (issue #81).

These tests use Flask's built-in test client and do not require Docker.
They verify that:
  - service1 returns HTTP 500 when /tmp/service.lock exists
  - service1 returns HTTP 200 once the lockfile is removed
"""
from __future__ import annotations

import sys
import os
import unittest
import tempfile
from pathlib import Path

# Ensure target_service is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "target_service"))

import app as service_app


class TestService1StaleLockfile(unittest.TestCase):
    def setUp(self) -> None:
        self.client = service_app.app.test_client()
        # Patch LOCKFILE to a temp path so tests are isolated from each other
        self._tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".lock")
        self._tmp.close()
        self._original_lockfile = service_app.LOCKFILE
        service_app.LOCKFILE = self._tmp.name

    def tearDown(self) -> None:
        service_app.LOCKFILE = self._original_lockfile
        try:
            os.unlink(self._tmp.name)
        except FileNotFoundError:
            pass

    def test_returns_500_when_lockfile_exists(self) -> None:
        """service1 must return HTTP 500 when the lockfile is present."""
        # Lockfile was created in setUp — it exists
        response = self.client.get("/service1", headers={"User-Agent": "curl/7.0"})
        self.assertEqual(response.status_code, 500)
        data = response.get_json()
        self.assertEqual(data["status"], "error")
        self.assertIn("stale lockfile", data["reason"])

    def test_returns_200_after_lockfile_removed(self) -> None:
        """service1 must return HTTP 200 once the stale lockfile has been removed."""
        os.unlink(self._tmp.name)  # simulate fix: remove the lockfile

        response = self.client.get("/service1", headers={"User-Agent": "curl/7.0"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")

    def test_lockfile_removal_recovers_service(self) -> None:
        """End-to-end: 500 before fix, 200 after — mirrors the incident remediation."""
        # Before fix
        before = self.client.get("/service1", headers={"User-Agent": "curl/7.0"})
        self.assertEqual(before.status_code, 500)

        # Apply fix: remove stale lockfile
        os.unlink(self._tmp.name)

        # After fix
        after = self.client.get("/service1", headers={"User-Agent": "curl/7.0"})
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.get_json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
