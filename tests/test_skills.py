from __future__ import annotations

import unittest
from pathlib import Path

from openhands_driver import list_skill_ids, select_skill


class SkillRouterTests(unittest.TestCase):
    def test_catalog_contains_core_sre_skills(self) -> None:
        ids = set(list_skill_ids())
        self.assertTrue({"stale-lockfile", "bad-env-config", "readiness-probe-fail", "port-mismatch"}.issubset(ids))

    def test_catalog_contains_data_store_corruption_skill(self) -> None:
        ids = set(list_skill_ids())
        self.assertIn("data-store-corruption", ids)

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

    def test_select_data_store_corruption_by_scenario(self) -> None:
        skill = select_skill(
            scenario_id="data_store_corruption",
            error_report="Database integrity checks failing",
        )
        self.assertEqual(skill.skill_id, "data-store-corruption")

    def test_select_data_store_corruption_by_data_corruption_keyword(self) -> None:
        skill = select_skill(
            scenario_id=None,
            error_report="Data corruption detected in cache files",
        )
        self.assertEqual(skill.skill_id, "data-store-corruption")

    def test_select_data_store_corruption_by_cache_corruption_keyword(self) -> None:
        skill = select_skill(
            scenario_id=None,
            error_report="Cache corruption detected in /var/data/",
        )
        self.assertEqual(skill.skill_id, "data-store-corruption")

    def test_select_data_store_corruption_by_var_data_cache_keyword(self) -> None:
        skill = select_skill(
            scenario_id=None,
            error_report="Corrupted files found in /var/data/cache/",
        )
        self.assertEqual(skill.skill_id, "data-store-corruption")

    def test_select_data_store_corruption_by_corrupted_blocks_keyword(self) -> None:
        skill = select_skill(
            scenario_id=None,
            error_report="[CRITICAL] Corrupted blocks detected",
        )
        self.assertEqual(skill.skill_id, "data-store-corruption")

    def test_select_data_store_corruption_by_rm_rf_keyword(self) -> None:
        skill = select_skill(
            scenario_id=None,
            error_report="Recommendation: Clear corrupted cache with rm -rf /var/data/cache/*",
        )
        self.assertEqual(skill.skill_id, "data-store-corruption")

    def test_data_store_corruption_skill_hint_warns_high_risk(self) -> None:
        skill = select_skill(
            scenario_id="data_store_corruption",
            error_report="Data store corruption detected",
        )
        self.assertIn("HIGH risk", skill.strategy_hint)
        self.assertIn("human approval", skill.strategy_hint)

    def test_data_store_corruption_skill_file_exists(self) -> None:
        skill = select_skill(
            scenario_id="data_store_corruption",
            error_report="",
        )
        self.assertTrue(skill.skill_path.exists())
        content = skill.skill_path.read_text()
        self.assertIn("HIGH", content)
        self.assertIn("human approval", content.lower())


if __name__ == "__main__":
    unittest.main()
