from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from openhands_driver import list_skill_ids, select_skill

# Add stale-lockfile skill to path for direct testing
SKILL_PATH = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "stale-lockfile"
sys.path.insert(0, str(SKILL_PATH))

from diagnose import diagnose, _host_file_state
from remediate import remediate


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
    """Tests for the stale-lockfile skill diagnose and remediate functions."""

    def test_host_file_state_detects_present_file(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name
        try:
            state = _host_file_state(temp_path)
            self.assertTrue(state["present"])
            self.assertEqual(state["error"], "")
        finally:
            os.unlink(temp_path)

    def test_host_file_state_detects_absent_file(self) -> None:
        state = _host_file_state("/tmp/nonexistent_file_12345.lock")
        self.assertFalse(state["present"])
        self.assertEqual(state["error"], "")

    def test_diagnose_identifies_stale_lockfile_candidate(self) -> None:
        # Create a temporary lock file
        lock_path = "/tmp/test_stale_lockfile_skill.lock"
        try:
            Path(lock_path).touch()
            result = diagnose(
                target_url="http://127.0.0.1:99999",  # Non-existent URL will fail
                target_container=None,  # Test host mode
                lock_path=lock_path,
            )
            self.assertEqual(result["lock_path"], lock_path)
            self.assertEqual(result["scope"], "host")
            self.assertTrue(result["present"])
        finally:
            if os.path.exists(lock_path):
                os.unlink(lock_path)

    def test_remediate_removes_lockfile_on_host(self) -> None:
        # Create a temporary lock file
        lock_path = "/tmp/test_remediate_lockfile.lock"
        try:
            Path(lock_path).touch()
            self.assertTrue(os.path.exists(lock_path))

            result = remediate(
                target_url="http://127.0.0.1:99999",  # Non-existent URL
                target_container=None,  # Test host mode
                lock_path=lock_path,
            )

            self.assertEqual(result["lock_path"], lock_path)
            self.assertEqual(result["scope"], "host")
            self.assertEqual(result["remove_returncode"], 0)
            self.assertFalse(os.path.exists(lock_path))
        finally:
            if os.path.exists(lock_path):
                os.unlink(lock_path)


if __name__ == "__main__":
    unittest.main()
