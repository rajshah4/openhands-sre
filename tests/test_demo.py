from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cmd(args: list[str]) -> str:
    proc = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


class DemoSmokeTests(unittest.TestCase):
    def test_optimize_simulation_prints_multi_scenario(self) -> None:
        out = run_cmd(["optimize.py"])
        self.assertIn("[sim-gepa] scenarios:", out)
        self.assertIn("stale_lockfile", out)
        self.assertIn("readiness_probe_fail", out)
        self.assertIn("port_mismatch", out)

    def test_baseline_and_optimized_step_gap_for_lockfile(self) -> None:
        baseline = run_cmd(["run_demo.py", "--mode", "baseline", "--scenario", "stale_lockfile", "--simulate"])
        optimized = run_cmd(["run_demo.py", "--mode", "optimized", "--scenario", "stale_lockfile", "--simulate"])

        self.assertIn("mode: baseline", baseline)
        self.assertIn("scenario: stale_lockfile", baseline)
        self.assertIn("service_up: True", baseline)
        self.assertIn("step_count: 6", baseline)

        self.assertIn("mode: optimized", optimized)
        self.assertIn("scenario: stale_lockfile", optimized)
        self.assertIn("service_up: True", optimized)
        self.assertIn("step_count: 3", optimized)

    def test_optimized_mode_supports_other_scenarios(self) -> None:
        out = run_cmd(["run_demo.py", "--mode", "optimized", "--scenario", "readiness_probe_fail", "--simulate"])
        self.assertIn("scenario: readiness_probe_fail", out)
        self.assertIn("service_up: True", out)
        self.assertIn("step_count: 3", out)


if __name__ == "__main__":
    unittest.main()
