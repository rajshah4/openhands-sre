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


class FanoutSmokeTests(unittest.TestCase):
    def test_one_shot_fanout_mock(self) -> None:
        out = run_cmd(
            [
                "scripts/fanout_sre.py",
                "--simulate",
                "--incidents",
                "6",
                "--concurrency",
                "3",
                "--optimizer",
                "gepa",
                "--seed",
                "11",
            ]
        )
        self.assertIn("=== Final Results ===", out)
        self.assertIn("generated=6", out)
        self.assertIn("completed=6", out)
        self.assertIn("fixed=6", out)

    def test_continuous_fanout_mock(self) -> None:
        out = run_cmd(
            [
                "scripts/fanout_sre.py",
                "--simulate",
                "--continuous",
                "--duration-s",
                "3",
                "--arrival-rate",
                "2",
                "--concurrency",
                "2",
                "--optimizer",
                "iterative",
                "--scorecard-interval-s",
                "1",
                "--seed",
                "13",
            ]
        )
        self.assertIn("=== Final Results ===", out)
        self.assertIn("continuous=True", out)
        self.assertIn("completed=", out)

    def test_live_demo_mock(self) -> None:
        out = run_cmd(
            [
                "scripts/fanout_live_demo.py",
                "--simulate",
                "--incidents",
                "6",
                "--concurrency",
                "3",
                "--optimizer",
                "gepa",
                "--seed",
                "17",
            ]
        )
        self.assertIn("OpenHands Fan-Out SRE Demo", out)
        self.assertIn("[controller] incident intake", out)
        self.assertIn("Final Scorecard", out)
        self.assertIn("completed=6", out)

    def test_dashboard_mock_with_trace_links(self) -> None:
        out = run_cmd(
            [
                "scripts/fanout_dashboard.py",
                "--simulate",
                "--incidents",
                "6",
                "--concurrency",
                "3",
                "--optimizer",
                "gepa",
                "--refresh-s",
                "0.2",
                "--trace-url-template",
                "https://example.local/trace/{run_id}/{incident_id}",
            ]
        )
        self.assertIn("Dashboard Final Summary", out)
        self.assertIn("Trace Links", out)
        self.assertIn("https://example.local/trace/", out)

    def test_orchestrated_remote_mock(self) -> None:
        out = run_cmd(
            [
                "scripts/fanout_orchestrated_remote.py",
                "--simulate",
                "--incidents",
                "4",
                "--concurrency",
                "2",
                "--optimizer",
                "gepa",
                "--seed",
                "19",
            ]
        )
        self.assertIn("Orchestrated Fan-Out Summary", out)
        self.assertIn("completed=4", out)


if __name__ == "__main__":
    unittest.main()
