"""Unit tests for the target service application.

These tests verify the stale lockfile remediation workflow without requiring Docker.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

# We need to import the app after setting up the test environment
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'target_service'))


class TestStaleLockfileRemediation(unittest.TestCase):
    """Test the stale lockfile scenario and remediation."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create a temp directory for our test lockfile
        self.temp_dir = tempfile.mkdtemp()
        self.lockfile_path = os.path.join(self.temp_dir, "service.lock")

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        # Remove lockfile if it exists
        if os.path.exists(self.lockfile_path):
            os.remove(self.lockfile_path)
        os.rmdir(self.temp_dir)

    def test_service_returns_500_when_lockfile_present(self) -> None:
        """Service1 should return HTTP 500 when stale lockfile exists."""
        # Patch the LOCKFILE constant to use our temp path
        with patch('app.LOCKFILE', self.lockfile_path):
            from app import app
            # Create the lockfile
            with open(self.lockfile_path, 'w') as f:
                f.write('stale lock')

            client = app.test_client()
            response = client.get('/service1', headers={'Accept': 'application/json'})

            self.assertEqual(response.status_code, 500)
            data = response.get_json()
            self.assertEqual(data['status'], 'error')
            self.assertIn('stale lockfile', data['reason'])

    def test_service_returns_200_when_lockfile_removed(self) -> None:
        """Service1 should return HTTP 200 after lockfile is removed."""
        with patch('app.LOCKFILE', self.lockfile_path):
            from app import app

            # First, create the lockfile to simulate the error state
            with open(self.lockfile_path, 'w') as f:
                f.write('stale lock')

            client = app.test_client()
            
            # Verify it's broken first
            response = client.get('/service1', headers={'Accept': 'application/json'})
            self.assertEqual(response.status_code, 500)

            # Apply the fix: remove the lockfile (MEDIUM risk action)
            os.remove(self.lockfile_path)

            # Verify the fix worked
            response = client.get('/service1', headers={'Accept': 'application/json'})
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data['status'], 'ok')

    def test_service_healthy_when_no_lockfile(self) -> None:
        """Service1 should return HTTP 200 when no lockfile exists."""
        with patch('app.LOCKFILE', self.lockfile_path):
            from app import app
            
            # Ensure no lockfile exists
            if os.path.exists(self.lockfile_path):
                os.remove(self.lockfile_path)

            client = app.test_client()
            response = client.get('/service1', headers={'Accept': 'application/json'})

            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data['status'], 'ok')
            self.assertEqual(data['scenario'], 'stale_lockfile')


class TestRemediationRiskLevels(unittest.TestCase):
    """Test that remediation actions are correctly classified by risk level."""

    def test_lockfile_removal_is_medium_risk(self) -> None:
        """Verify that lockfile removal is classified as MEDIUM risk.
        
        This test documents the expected risk classification for the
        stale lockfile remediation action.
        """
        # The fix_demo.sh script and MCP server both classify
        # lockfile removal as MEDIUM risk
        expected_risk_level = "MEDIUM"
        
        # Read the skill documentation to verify
        skill_path = os.path.join(
            os.path.dirname(__file__), 
            '..', '.agents', 'skills', 'stale-lockfile', 'SKILL.md'
        )
        
        with open(skill_path, 'r') as f:
            skill_content = f.read()
        
        self.assertIn(expected_risk_level, skill_content)
        self.assertIn("rm -f /tmp/service.lock", skill_content)


if __name__ == "__main__":
    unittest.main()
