"""Unit tests for the stale lockfile (service1) scenario.

These tests verify that:
  - service1 returns HTTP 500 when /tmp/service.lock exists.
  - service1 returns HTTP 200 after the stale lockfile is removed.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure the target_service package is importable
TARGET_SERVICE = Path(__file__).resolve().parents[1] / "target_service"
sys.path.insert(0, str(TARGET_SERVICE))

import app as service_app  # noqa: E402


LOCKFILE = "/tmp/service.lock"


class StaleLockfileUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        service_app.app.config["TESTING"] = True
        self.client = service_app.app.test_client()
        # Ensure a clean slate before each test
        if os.path.exists(LOCKFILE):
            os.remove(LOCKFILE)

    def tearDown(self) -> None:
        # Clean up after each test
        if os.path.exists(LOCKFILE):
            os.remove(LOCKFILE)

    def test_service1_returns_500_when_lockfile_present(self) -> None:
        """service1 must return HTTP 500 if the stale lockfile exists."""
        Path(LOCKFILE).touch()
        response = self.client.get("/service1", headers={"Accept": "application/json"})
        self.assertEqual(response.status_code, 500)
        data = response.get_json()
        self.assertEqual(data["status"], "error")
        self.assertIn("stale lockfile", data["reason"])
        self.assertIn(LOCKFILE, data["reason"])

    def test_service1_returns_200_when_lockfile_absent(self) -> None:
        """service1 must return HTTP 200 when no lockfile is present."""
        # Lockfile is already absent (cleaned in setUp)
        response = self.client.get("/service1", headers={"Accept": "application/json"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")

    def test_service1_recovers_after_lockfile_removal(self) -> None:
        """service1 must recover to HTTP 200 after the stale lockfile is removed."""
        # Break the service by creating the lockfile
        Path(LOCKFILE).touch()
        broken = self.client.get("/service1", headers={"Accept": "application/json"})
        self.assertEqual(broken.status_code, 500)

        # Remediate: remove the lockfile
        os.remove(LOCKFILE)

        # Verify recovery
        recovered = self.client.get("/service1", headers={"Accept": "application/json"})
        self.assertEqual(recovered.status_code, 200)
        data = recovered.get_json()
        self.assertEqual(data["status"], "ok")


if __name__ == "__main__":
    unittest.main()
