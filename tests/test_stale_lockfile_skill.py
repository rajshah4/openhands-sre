"""Tests for the stale-lockfile skill diagnose and remediate functions.

These tests verify the incident response workflow for stale lockfile issues.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".agents" / "skills" / "stale-lockfile"
TARGET_SERVICE = ROOT / "target_service"
LOCKFILE = "/tmp/service.lock"


class StaleLockfileSkillTests(unittest.TestCase):
    """Test the stale-lockfile skill diagnose and remediate functions."""

    flask_proc: subprocess.Popen | None = None
    port: int = 5050  # Use a unique port to avoid conflicts

    @classmethod
    def setUpClass(cls) -> None:
        # Start the Flask app with stale_lockfile scenario
        cls._cleanup_lockfile()
        env = os.environ.copy()
        env["SCENARIO"] = "stale_lockfile"
        cls.flask_proc = subprocess.Popen(
            [sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{TARGET_SERVICE}')
from app import app
app.run(host='127.0.0.1', port={cls.port})
"""],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Wait for server to start
        cls._wait_for_server()

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.flask_proc:
            cls.flask_proc.terminate()
            try:
                cls.flask_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.flask_proc.kill()
        cls._cleanup_lockfile()

    @classmethod
    def _cleanup_lockfile(cls) -> None:
        try:
            os.remove(LOCKFILE)
        except FileNotFoundError:
            pass

    @classmethod
    def _wait_for_server(cls, timeout: float = 10.0) -> None:
        """Wait until the Flask server is ready to accept connections."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                proc = subprocess.run(
                    ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
                     f"http://127.0.0.1:{cls.port}"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if proc.returncode == 0 and proc.stdout.strip() in ("200", "500"):
                    return
            except Exception:
                pass
            time.sleep(0.3)
        raise RuntimeError("Flask server did not start in time")

    def setUp(self) -> None:
        # Clean up any existing lockfile before each test
        self._cleanup_lockfile()

    def tearDown(self) -> None:
        self._cleanup_lockfile()

    def _create_lockfile(self) -> None:
        """Create a stale lockfile to simulate the incident."""
        Path(LOCKFILE).write_text("12345\n")

    def _http_code(self) -> str:
        """Get HTTP status code from the service."""
        proc = subprocess.run(
            ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
             f"http://127.0.0.1:{self.port}"],
            capture_output=True,
            text=True,
        )
        return proc.stdout.strip() if proc.returncode == 0 else "000"

    def test_diagnose_detects_stale_lockfile(self) -> None:
        """Test that diagnose correctly identifies a stale lockfile condition."""
        # Create the lockfile to simulate incident
        self._create_lockfile()

        # Run diagnose.py
        proc = subprocess.run(
            [sys.executable, str(SKILL_DIR / "diagnose.py")],
            env={
                **os.environ,
                "TARGET_URL": f"http://127.0.0.1:{self.port}",
                "TARGET_CONTAINER": "",
            },
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"diagnose.py failed: {proc.stderr}")

        import json
        result = json.loads(proc.stdout)
        self.assertEqual(result["http_code"], "500")
        self.assertTrue(result["present"])
        self.assertTrue(result["is_stale_lockfile_candidate"])

    def test_diagnose_healthy_when_no_lockfile(self) -> None:
        """Test that diagnose correctly identifies healthy state without lockfile."""
        # Ensure no lockfile exists
        self._cleanup_lockfile()

        proc = subprocess.run(
            [sys.executable, str(SKILL_DIR / "diagnose.py")],
            env={
                **os.environ,
                "TARGET_URL": f"http://127.0.0.1:{self.port}",
                "TARGET_CONTAINER": "",
            },
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"diagnose.py failed: {proc.stderr}")

        import json
        result = json.loads(proc.stdout)
        self.assertEqual(result["http_code"], "200")
        self.assertFalse(result["present"])
        self.assertFalse(result["is_stale_lockfile_candidate"])

    def test_remediate_removes_lockfile_and_restores_service(self) -> None:
        """Test that remediate removes the lockfile and service returns 200."""
        # Create the lockfile to simulate incident
        self._create_lockfile()

        # Verify service is returning 500
        self.assertEqual(self._http_code(), "500")
        self.assertTrue(Path(LOCKFILE).exists())

        # Run remediate.py
        proc = subprocess.run(
            [sys.executable, str(SKILL_DIR / "remediate.py")],
            env={
                **os.environ,
                "TARGET_URL": f"http://127.0.0.1:{self.port}",
                "TARGET_CONTAINER": "",
            },
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"remediate.py failed: {proc.stderr}")

        import json
        result = json.loads(proc.stdout)
        self.assertEqual(result["pre_http_code"], "500")
        self.assertEqual(result["post_http_code"], "200")
        self.assertTrue(result["fixed"])
        self.assertEqual(result["remove_returncode"], 0)

        # Verify lockfile was removed
        self.assertFalse(Path(LOCKFILE).exists())

        # Verify service is now healthy
        self.assertEqual(self._http_code(), "200")

    def test_full_incident_lifecycle(self) -> None:
        """Test complete incident lifecycle: healthy -> incident -> diagnose -> remediate -> healthy."""
        # 1. Initial healthy state
        self.assertEqual(self._http_code(), "200")

        # 2. Simulate incident
        self._create_lockfile()
        self.assertEqual(self._http_code(), "500")

        # 3. Diagnose
        proc = subprocess.run(
            [sys.executable, str(SKILL_DIR / "diagnose.py")],
            env={
                **os.environ,
                "TARGET_URL": f"http://127.0.0.1:{self.port}",
                "TARGET_CONTAINER": "",
            },
            capture_output=True,
            text=True,
        )
        import json
        diag_result = json.loads(proc.stdout)
        self.assertTrue(diag_result["is_stale_lockfile_candidate"])

        # 4. Remediate
        proc = subprocess.run(
            [sys.executable, str(SKILL_DIR / "remediate.py")],
            env={
                **os.environ,
                "TARGET_URL": f"http://127.0.0.1:{self.port}",
                "TARGET_CONTAINER": "",
            },
            capture_output=True,
            text=True,
        )
        rem_result = json.loads(proc.stdout)
        self.assertTrue(rem_result["fixed"])

        # 5. Verify healthy
        self.assertEqual(self._http_code(), "200")


if __name__ == "__main__":
    unittest.main()
