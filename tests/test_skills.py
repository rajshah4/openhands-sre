from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from openhands_driver import list_skill_ids, select_skill

SKILLS_ROOT = Path(__file__).resolve().parents[1] / ".agents" / "skills"


class SkillRouterTests(unittest.TestCase):
    def test_catalog_contains_core_sre_skills(self) -> None:
        ids = set(list_skill_ids())
        self.assertTrue({"stale-lockfile", "bad-env-config", "readiness-probe-fail", "port-mismatch"}.issubset(ids))

    def test_select_by_scenario(self) -> None:
        skill = select_skill(
            scenario_id="stale_lockfile",
            error_report="Service is down after restart",
        )
        self.assertEqual(skill.skill_id, "stale-lockfile")

    def test_select_by_keywords(self) -> None:
        skill = select_skill(
            scenario_id=None,
            error_report="Probe expects 5000 but process seems on 5001",
        )
        self.assertEqual(skill.skill_id, "port-mismatch")


class StaleLockfileSkillTests(unittest.TestCase):
    """Tests for the stale-lockfile skill's diagnose and remediate functions on host."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.service_proc = None
        cls.test_port = 15123
        cls.test_url = f"http://127.0.0.1:{cls.test_port}"
        cls.lock_path = tempfile.mktemp(prefix="test_service_", suffix=".lock")

    def _start_service(self) -> None:
        """Start the target service in the background."""
        app_path = Path(__file__).resolve().parents[1] / "target_service" / "app.py"
        env = os.environ.copy()
        env["SCENARIO"] = "stale_lockfile"
        # Modify app.py to use test port by running with custom PORT env
        self.service_proc = subprocess.Popen(
            [sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{app_path.parent}')
import os
os.environ['SCENARIO'] = 'stale_lockfile'
LOCKFILE = '{self.lock_path}'
from flask import Flask, jsonify
app = Flask(__name__)
@app.route("/")
def healthcheck():
    if os.path.exists(LOCKFILE):
        return jsonify({{"status": "error", "reason": f"stale lockfile present at {{LOCKFILE}}"}}), 500
    return jsonify({{"status": "ok", "scenario": "stale_lockfile"}}), 200
app.run(host="0.0.0.0", port={self.test_port})
"""],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        # Wait for service to start
        for _ in range(20):
            try:
                result = subprocess.run(
                    ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", self.test_url],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if result.stdout.strip() in ("200", "500"):
                    return
            except Exception:
                pass
            time.sleep(0.25)
        raise RuntimeError("Service did not start in time")

    def _stop_service(self) -> None:
        """Stop the target service."""
        if self.service_proc:
            self.service_proc.terminate()
            try:
                self.service_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.service_proc.kill()
            self.service_proc = None

    def _create_lockfile(self) -> None:
        """Create a stale lockfile."""
        Path(self.lock_path).touch()

    def _remove_lockfile(self) -> None:
        """Remove the lockfile if it exists."""
        try:
            os.remove(self.lock_path)
        except FileNotFoundError:
            pass

    def setUp(self) -> None:
        self._remove_lockfile()
        self._start_service()

    def tearDown(self) -> None:
        self._stop_service()
        self._remove_lockfile()

    def test_diagnose_detects_stale_lockfile(self) -> None:
        """Test that diagnose correctly detects a stale lockfile issue."""
        sys.path.insert(0, str(SKILLS_ROOT / "stale-lockfile"))
        from diagnose import diagnose

        # First verify service is healthy without lockfile
        result = diagnose(
            target_url=self.test_url,
            target_container=None,
            lock_path=self.lock_path,
        )
        self.assertEqual(result["http_code"], "200")
        self.assertFalse(result["present"])
        self.assertFalse(result["is_stale_lockfile_candidate"])

        # Now create lockfile and verify diagnosis
        self._create_lockfile()
        result = diagnose(
            target_url=self.test_url,
            target_container=None,
            lock_path=self.lock_path,
        )
        self.assertEqual(result["http_code"], "500")
        self.assertTrue(result["present"])
        self.assertTrue(result["is_stale_lockfile_candidate"])

    def test_remediate_fixes_stale_lockfile(self) -> None:
        """Test that remediate correctly removes stale lockfile and fixes service."""
        sys.path.insert(0, str(SKILLS_ROOT / "stale-lockfile"))
        from remediate import remediate

        # Create lockfile to simulate stale state
        self._create_lockfile()

        # Verify service is unhealthy
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", self.test_url],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout.strip(), "500")

        # Apply remediation
        result = remediate(
            target_url=self.test_url,
            target_container=None,
            lock_path=self.lock_path,
        )
        self.assertEqual(result["pre_http_code"], "500")
        self.assertEqual(result["post_http_code"], "200")
        self.assertTrue(result["fixed"])
        self.assertEqual(result["scope"], "host")

        # Verify lockfile is gone
        self.assertFalse(Path(self.lock_path).exists())


if __name__ == "__main__":
    unittest.main()
