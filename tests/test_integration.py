from __future__ import annotations

import json
import subprocess
import time
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMAGE = "openhands-gepa-sre-target:latest"


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

    def _container_http_response(self, name: str, path: str = "") -> str:
        return self._run(
            [
                "docker",
                "exec",
                name,
                "sh",
                "-lc",
                f"curl -s localhost:5000{path}",
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


class StaleLockfileIncidentTests(unittest.TestCase):
    """Test case for Issue #28: service1 returning HTTP 500 - stale lockfile suspected.
    
    This test validates the incident remediation workflow for the stale lockfile scenario.
    Risk Level: MEDIUM (requires file deletion)
    """
    
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

    def _start_multi_service_container(self) -> str:
        """Start container in multi-service mode (no SCENARIO env)."""
        name = f"openhands-gepa-it-multi-{uuid.uuid4().hex[:6]}"
        self._run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                name,
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

    def _container_http_status(self, name: str, path: str = "/service1") -> str:
        return self._run(
            [
                "docker",
                "exec",
                name,
                "sh",
                "-lc",
                f"curl -s -o /dev/null -w '%{{http_code}}' localhost:5000{path}",
            ]
        )

    def _container_http_json(self, name: str, path: str = "/service1") -> dict:
        output = self._run(
            [
                "docker",
                "exec",
                name,
                "sh",
                "-lc",
                f"curl -s -H 'Accept: application/json' localhost:5000{path}",
            ]
        )
        return json.loads(output)

    def _wait_for_service(self, name: str, timeout_s: float = 20.0) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                status = self._container_http_status(name, "/")
                if status in {"500", "200", "000"}:
                    return
            except Exception:
                pass
            time.sleep(0.5)
        raise RuntimeError("service did not become reachable in time")

    def _create_lockfile(self, name: str) -> None:
        """Simulate a stale lockfile from a crashed process."""
        self._run(["docker", "exec", name, "touch", "/tmp/service.lock"])

    def _remove_lockfile(self, name: str) -> None:
        """Remediation action: remove stale lockfile (MEDIUM risk)."""
        self._run(["docker", "exec", name, "rm", "-f", "/tmp/service.lock"])

    def _lockfile_exists(self, name: str) -> bool:
        """Check if lockfile exists in container."""
        result = subprocess.run(
            ["docker", "exec", name, "ls", "/tmp/service.lock"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def test_service1_stale_lockfile_incident_response(self) -> None:
        """Test full incident response workflow for Issue #28.
        
        Workflow:
        1. Diagnose: service1 returns HTTP 500 with error JSON
        2. Verify: lockfile exists at /tmp/service.lock
        3. Remediate: Remove stale lockfile (MEDIUM risk)
        4. Verify: service1 returns HTTP 200 with status ok
        """
        name = self._start_multi_service_container()
        try:
            # Simulate incident: create stale lockfile
            self._create_lockfile(name)
            
            # Step 1: Diagnose - check HTTP status
            http_status = self._container_http_status(name, "/service1")
            self.assertEqual(http_status, "500", "Expected HTTP 500 when lockfile present")
            
            # Step 2: Verify error message in JSON response
            response = self._container_http_json(name, "/service1")
            self.assertEqual(response["status"], "error")
            self.assertIn("stale lockfile", response["reason"])
            self.assertIn("/tmp/service.lock", response["reason"])
            
            # Step 3: Verify lockfile exists
            self.assertTrue(self._lockfile_exists(name), "Lockfile should exist before remediation")
            
            # Step 4: Remediate - remove stale lockfile (MEDIUM risk action)
            self._remove_lockfile(name)
            
            # Step 5: Verify fix - lockfile should be gone
            self.assertFalse(self._lockfile_exists(name), "Lockfile should not exist after remediation")
            
            # Step 6: Verify fix - service should return 200
            after_status = self._container_http_status(name, "/service1")
            self.assertEqual(after_status, "200", "Expected HTTP 200 after remediation")
            
            # Step 7: Verify fix - response should show status ok
            after_response = self._container_http_json(name, "/service1")
            self.assertEqual(after_response["status"], "ok")
            self.assertEqual(after_response["scenario"], "stale_lockfile")
            
        finally:
            self._stop_container(name)

    def test_service1_no_lockfile_healthy(self) -> None:
        """Test that service1 is healthy when no lockfile exists."""
        name = self._start_multi_service_container()
        try:
            # Without lockfile, service should be healthy
            http_status = self._container_http_status(name, "/service1")
            self.assertEqual(http_status, "200")
            
            response = self._container_http_json(name, "/service1")
            self.assertEqual(response["status"], "ok")
        finally:
            self._stop_container(name)


if __name__ == "__main__":
    unittest.main()
