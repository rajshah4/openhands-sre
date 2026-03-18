from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
import uuid
from pathlib import Path

# Allow importing the target_service package without Docker
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "openhands-gepa-sre-target:latest"
LOCKFILE = "/tmp/service.lock"


class StaleLockfileUnitTests(unittest.TestCase):
    """Unit tests for the stale lockfile scenario using Flask test client.

    These tests run without Docker and directly exercise the Flask app logic.
    """

    def setUp(self) -> None:
        if os.path.exists(LOCKFILE):
            os.remove(LOCKFILE)
        from target_service.app import app
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self) -> None:
        if os.path.exists(LOCKFILE):
            os.remove(LOCKFILE)

    def test_service1_returns_500_when_lockfile_present(self) -> None:
        Path(LOCKFILE).touch()
        resp = self.client.get("/service1", headers={"Accept": "application/json"})
        self.assertEqual(resp.status_code, 500)
        data = resp.get_json()
        self.assertEqual(data["status"], "error")
        self.assertIn("stale lockfile", data["reason"])

    def test_service1_returns_200_after_lockfile_removed(self) -> None:
        Path(LOCKFILE).touch()
        resp_before = self.client.get("/service1", headers={"Accept": "application/json"})
        self.assertEqual(resp_before.status_code, 500)

        # Simulate remediation: remove the stale lockfile
        os.remove(LOCKFILE)

        resp_after = self.client.get("/service1", headers={"Accept": "application/json"})
        self.assertEqual(resp_after.status_code, 200)
        data = resp_after.get_json()
        self.assertEqual(data["status"], "ok")

    def test_service1_returns_200_without_lockfile(self) -> None:
        self.assertFalse(os.path.exists(LOCKFILE))
        resp = self.client.get("/service1", headers={"Accept": "application/json"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "ok")


class TargetServiceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not cls._docker_available():
            raise unittest.SkipTest("Docker CLI or daemon is not available")
        cls._run(["docker", "build", "-t", IMAGE, "target_service"])

    @classmethod
    def _docker_available(cls) -> bool:
        try:
            subprocess.run(
                ["docker", "version"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=8,
            )
            return True
        except Exception:
            return False

    @classmethod
    def _run(cls, cmd: list[str]) -> str:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stdout.strip()

    def _start_container(self, scenario: str) -> str:
        name = f"openhands-gepa-it-{scenario}-{uuid.uuid4().hex[:6]}"
        self._run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                name,
                "-e",
                f"SCENARIO={scenario}",
                IMAGE,
            ]
        )
        self._wait_for_service(name)
        return name

    def _stop_container(self, name: str) -> None:
        subprocess.run(
            ["docker", "rm", "-f", name],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def _container_http_status(self, name: str) -> str:
        return self._run(
            [
                "docker",
                "exec",
                name,
                "sh",
                "-lc",
                "curl -s -o /dev/null -w '%{http_code}' localhost:5000",
            ]
        )

    def _wait_for_service(self, name: str, timeout_s: float = 20.0) -> None:
        deadline = time.time() + timeout_s
        last_status = ""
        while time.time() < deadline:
            try:
                last_status = self._container_http_status(name)
                if last_status in {"500", "200", "000"}:
                    return
            except Exception:
                pass
            time.sleep(0.5)
        raise RuntimeError(f"service did not become reachable in time; last_status={last_status}")

    def test_stale_lockfile_recovers_500_to_200(self) -> None:
        name = self._start_container("stale_lockfile")
        try:
            before = self._container_http_status(name)
            self.assertEqual(before, "500")

            self._run(["docker", "exec", name, "sh", "-lc", "rm -f /tmp/service.lock"])

            after = self._container_http_status(name)
            self.assertEqual(after, "200")
        finally:
            self._stop_container(name)

    def test_readiness_probe_recovers_500_to_200(self) -> None:
        name = self._start_container("readiness_probe_fail")
        try:
            before = self._container_http_status(name)
            self.assertEqual(before, "500")

            self._run(["docker", "exec", name, "sh", "-lc", "touch /tmp/ready.flag"])

            after = self._container_http_status(name)
            self.assertEqual(after, "200")
        finally:
            self._stop_container(name)


if __name__ == "__main__":
    unittest.main()
