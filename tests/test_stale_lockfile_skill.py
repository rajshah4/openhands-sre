"""Tests for the stale-lockfile skill diagnose and remediate functions.

These tests verify the stale-lockfile remediation skill works correctly
for both host mode (no container) and container mode (with Docker).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / ".agents" / "skills" / "stale-lockfile"
sys.path.insert(0, str(SKILLS_DIR))

from diagnose import diagnose, _host_file_state
from remediate import remediate


class TestHostFileState(unittest.TestCase):
    """Test the _host_file_state helper function."""

    def test_file_present(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                result = _host_file_state(f.name)
                self.assertTrue(result["present"])
                self.assertEqual(result["error"], "")
            finally:
                os.unlink(f.name)

    def test_file_absent(self) -> None:
        result = _host_file_state("/nonexistent/path/file.lock")
        self.assertFalse(result["present"])
        self.assertEqual(result["error"], "")


class TestDiagnoseHostMode(unittest.TestCase):
    """Test diagnose function in host mode (no container)."""

    def test_diagnose_no_lockfile(self) -> None:
        """When no lockfile exists, is_stale_lockfile_candidate should be False."""
        lock_path = "/tmp/test_nonexistent_lock_file.lock"
        if os.path.exists(lock_path):
            os.unlink(lock_path)

        with patch("diagnose._curl_code", return_value="200"):
            result = diagnose(
                target_url="http://localhost:5000",
                target_container=None,
                lock_path=lock_path,
            )

        self.assertEqual(result["http_code"], "200")
        self.assertFalse(result["present"])
        self.assertFalse(result["is_stale_lockfile_candidate"])
        self.assertEqual(result["scope"], "host")

    def test_diagnose_with_lockfile_and_500(self) -> None:
        """When lockfile exists and HTTP 500, is_stale_lockfile_candidate is True."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".lock") as f:
            lock_path = f.name
        try:
            with patch("diagnose._curl_code", return_value="500"):
                result = diagnose(
                    target_url="http://localhost:5000",
                    target_container=None,
                    lock_path=lock_path,
                )

            self.assertEqual(result["http_code"], "500")
            self.assertTrue(result["present"])
            self.assertTrue(result["is_stale_lockfile_candidate"])
            self.assertEqual(result["scope"], "host")
        finally:
            if os.path.exists(lock_path):
                os.unlink(lock_path)

    def test_diagnose_lockfile_exists_but_200(self) -> None:
        """When lockfile exists but HTTP 200, not a stale lockfile issue."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".lock") as f:
            lock_path = f.name
        try:
            with patch("diagnose._curl_code", return_value="200"):
                result = diagnose(
                    target_url="http://localhost:5000",
                    target_container=None,
                    lock_path=lock_path,
                )

            self.assertEqual(result["http_code"], "200")
            self.assertTrue(result["present"])
            self.assertFalse(result["is_stale_lockfile_candidate"])
        finally:
            if os.path.exists(lock_path):
                os.unlink(lock_path)


class TestRemediateHostMode(unittest.TestCase):
    """Test remediate function in host mode (no container)."""

    def test_remediate_removes_lockfile(self) -> None:
        """Remediate should remove the lockfile and return fixed=True."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".lock") as f:
            lock_path = f.name

        self.assertTrue(os.path.exists(lock_path))

        with patch("remediate._curl_code", side_effect=["500", "200"]):
            result = remediate(
                target_url="http://localhost:5000",
                target_container=None,
                lock_path=lock_path,
            )

        self.assertEqual(result["pre_http_code"], "500")
        self.assertEqual(result["post_http_code"], "200")
        self.assertTrue(result["fixed"])
        self.assertEqual(result["remove_returncode"], 0)
        self.assertFalse(os.path.exists(lock_path))
        self.assertEqual(result["scope"], "host")

    def test_remediate_nonexistent_lockfile(self) -> None:
        """Remediate should handle missing lockfile gracefully."""
        lock_path = "/tmp/test_nonexistent_remediate.lock"
        if os.path.exists(lock_path):
            os.unlink(lock_path)

        with patch("remediate._curl_code", side_effect=["200", "200"]):
            result = remediate(
                target_url="http://localhost:5000",
                target_container=None,
                lock_path=lock_path,
            )

        self.assertEqual(result["remove_returncode"], 0)
        self.assertTrue(result["fixed"])


class TestIntegrationWithLocalFlask(unittest.TestCase):
    """Integration tests that run against the actual Flask app (host mode)."""

    flask_process = None
    port = 5000  # Default Flask port used by app.py

    @classmethod
    def setUpClass(cls) -> None:
        """Start the Flask app for integration testing."""
        app_path = ROOT / "target_service" / "app.py"
        if not app_path.exists():
            raise unittest.SkipTest("target_service/app.py not found")

        subprocess.run(
            ["rm", "-f", "/tmp/service.lock"],
            check=False,
        )

        cls.flask_process = subprocess.Popen(
            [sys.executable, str(app_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(ROOT / "target_service"),
        )
        time.sleep(2)

    @classmethod
    def tearDownClass(cls) -> None:
        """Stop the Flask app."""
        if cls.flask_process:
            cls.flask_process.terminate()
            cls.flask_process.wait(timeout=5)
        subprocess.run(["rm", "-f", "/tmp/service.lock"], check=False)

    def setUp(self) -> None:
        """Ensure clean state before each test."""
        subprocess.run(["rm", "-f", "/tmp/service.lock"], check=False)

    def tearDown(self) -> None:
        """Clean up after each test."""
        subprocess.run(["rm", "-f", "/tmp/service.lock"], check=False)

    def test_full_incident_lifecycle(self) -> None:
        """Test complete incident: healthy -> broken -> diagnosed -> remediated."""
        target_url = f"http://localhost:{self.port}/service1"
        lock_path = "/tmp/service.lock"

        initial = diagnose(
            target_url=target_url,
            target_container=None,
            lock_path=lock_path,
        )
        self.assertEqual(initial["http_code"], "200")
        self.assertFalse(initial["is_stale_lockfile_candidate"])

        Path(lock_path).touch()
        self.assertTrue(os.path.exists(lock_path))

        broken = diagnose(
            target_url=target_url,
            target_container=None,
            lock_path=lock_path,
        )
        self.assertEqual(broken["http_code"], "500")
        self.assertTrue(broken["is_stale_lockfile_candidate"])

        fixed = remediate(
            target_url=target_url,
            target_container=None,
            lock_path=lock_path,
        )
        self.assertTrue(fixed["fixed"])
        self.assertEqual(fixed["pre_http_code"], "500")
        self.assertEqual(fixed["post_http_code"], "200")
        self.assertFalse(os.path.exists(lock_path))


if __name__ == "__main__":
    unittest.main()
