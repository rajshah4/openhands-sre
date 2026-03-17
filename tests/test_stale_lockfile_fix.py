"""Tests for the stale lockfile remediation scenario.

This test verifies that removing the stale lockfile at /tmp/service.lock
restores service1 to healthy (HTTP 200) status.

Skill: stale-lockfile (.agents/skills/stale-lockfile/SKILL.md)
Risk Level: MEDIUM (removes temp file only)
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "target_service"))

import app as target_app


class StaleLockfileFixTest(unittest.TestCase):
    """Test stale lockfile detection and remediation."""

    def setUp(self) -> None:
        """Create Flask test client."""
        target_app.app.testing = True
        self.client = target_app.app.test_client()
        self.temp_dir = tempfile.mkdtemp()
        self.lockfile = os.path.join(self.temp_dir, "service.lock")

    def tearDown(self) -> None:
        """Clean up lockfile if it exists."""
        if os.path.exists(self.lockfile):
            os.remove(self.lockfile)
        os.rmdir(self.temp_dir)

    def test_service1_returns_500_when_lockfile_exists(self) -> None:
        """Service1 should return HTTP 500 when stale lockfile is present."""
        with patch.object(target_app, "LOCKFILE", self.lockfile):
            Path(self.lockfile).touch()

            response = self.client.get(
                "/service1", headers={"User-Agent": "curl/7.68.0"}
            )

            self.assertEqual(response.status_code, 500)
            json_data = response.get_json()
            self.assertEqual(json_data["status"], "error")
            self.assertIn("stale lockfile", json_data["reason"])

    def test_service1_returns_200_after_lockfile_removed(self) -> None:
        """Service1 should return HTTP 200 after removing the stale lockfile."""
        with patch.object(target_app, "LOCKFILE", self.lockfile):
            Path(self.lockfile).touch()
            response_before = self.client.get(
                "/service1", headers={"User-Agent": "curl/7.68.0"}
            )
            self.assertEqual(response_before.status_code, 500)

            os.remove(self.lockfile)

            response_after = self.client.get(
                "/service1", headers={"User-Agent": "curl/7.68.0"}
            )
            self.assertEqual(response_after.status_code, 200)
            json_data = response_after.get_json()
            self.assertEqual(json_data["status"], "ok")

    def test_remediation_is_idempotent(self) -> None:
        """Removing lockfile when it doesn't exist should be safe (rm -f behavior)."""
        with patch.object(target_app, "LOCKFILE", self.lockfile):
            self.assertFalse(os.path.exists(self.lockfile))

            response = self.client.get(
                "/service1", headers={"User-Agent": "curl/7.68.0"}
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
