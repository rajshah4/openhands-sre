from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from openhands_driver import list_skill_ids, select_skill


# Add skill directories to path for imports
ROOT = Path(__file__).resolve().parents[1]
READINESS_SKILL_PATH = ROOT / ".agents" / "skills" / "readiness-probe-fail"
STALE_LOCKFILE_SKILL_PATH = ROOT / ".agents" / "skills" / "stale-lockfile"
sys.path.insert(0, str(READINESS_SKILL_PATH))
sys.path.insert(0, str(STALE_LOCKFILE_SKILL_PATH))


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

    def test_select_readiness_by_scenario(self) -> None:
        skill = select_skill(
            scenario_id="readiness_probe_fail",
            error_report="",
        )
        self.assertEqual(skill.skill_id, "readiness-probe-fail")

    def test_select_readiness_by_keyword(self) -> None:
        skill = select_skill(
            scenario_id=None,
            error_report="Readiness check failed: /tmp/ready.flag not found",
        )
        self.assertEqual(skill.skill_id, "readiness-probe-fail")


class ReadinessProbeSkillTests(unittest.TestCase):
    """Test readiness probe skill diagnose and remediate functions on host filesystem."""

    def setUp(self) -> None:
        self.ready_path = "/tmp/test_ready.flag"
        if os.path.exists(self.ready_path):
            os.remove(self.ready_path)

    def tearDown(self) -> None:
        if os.path.exists(self.ready_path):
            os.remove(self.ready_path)

    def test_diagnose_detects_missing_ready_flag(self) -> None:
        from diagnose import _host_file_state
        result = _host_file_state(self.ready_path)
        self.assertFalse(result["present"])
        self.assertEqual(result["error"], "")

    def test_diagnose_detects_existing_ready_flag(self) -> None:
        from diagnose import _host_file_state
        Path(self.ready_path).touch()
        result = _host_file_state(self.ready_path)
        self.assertTrue(result["present"])
        self.assertEqual(result["error"], "")

    def test_remediate_creates_ready_flag_on_host(self) -> None:
        """Test that remediation creates the ready.flag file on host when no container is specified."""
        from remediate import remediate

        self.assertFalse(os.path.exists(self.ready_path))

        result = remediate(
            target_url="http://127.0.0.1:9999",
            target_container=None,
            ready_path=self.ready_path,
        )

        self.assertEqual(result["scope"], "host")
        self.assertEqual(result["touch_returncode"], 0)
        self.assertEqual(result["touch_error"], "")
        self.assertTrue(os.path.exists(self.ready_path))


class StaleLockfileSkillTests(unittest.TestCase):
    """Test stale-lockfile skill diagnose and remediate functions on host filesystem."""

    def setUp(self) -> None:
        self.lock_path = "/tmp/test_service.lock"
        if os.path.exists(self.lock_path):
            os.remove(self.lock_path)

    def tearDown(self) -> None:
        if os.path.exists(self.lock_path):
            os.remove(self.lock_path)

    def test_diagnose_detects_missing_lockfile(self) -> None:
        """Test diagnose detects when no lockfile is present."""
        # Import from stale-lockfile skill directory (already on sys.path)
        from diagnose import _host_file_state
        result = _host_file_state(self.lock_path)
        self.assertFalse(result["present"])
        self.assertEqual(result["error"], "")

    def test_diagnose_detects_existing_lockfile(self) -> None:
        """Test diagnose detects when lockfile exists."""
        from diagnose import _host_file_state
        Path(self.lock_path).touch()
        result = _host_file_state(self.lock_path)
        self.assertTrue(result["present"])
        self.assertEqual(result["error"], "")

    def test_remediate_removes_lockfile_on_host(self) -> None:
        """Test that remediation removes the lockfile on host when no container is specified."""
        from remediate import remediate

        Path(self.lock_path).touch()
        self.assertTrue(os.path.exists(self.lock_path))

        result = remediate(
            target_url="http://127.0.0.1:9999",
            target_container=None,
            lock_path=self.lock_path,
        )

        self.assertEqual(result["scope"], "host")
        self.assertEqual(result["remove_returncode"], 0)
        self.assertEqual(result["remove_error"], "")
        self.assertFalse(os.path.exists(self.lock_path))


if __name__ == "__main__":
    unittest.main()
