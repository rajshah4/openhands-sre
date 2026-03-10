"""Unit tests for the stale lockfile scenario.

These tests verify the lockfile remediation logic without requiring Docker.
Related to incident #32: service1 returning HTTP 500 due to stale lockfile.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'target_service'))

from app import app, LOCKFILE


class StaleLockfileScenarioTests(unittest.TestCase):
    """Test the stale lockfile scenario without Docker."""

    def setUp(self):
        self.client = app.test_client()
        self.temp_lockfile = tempfile.mktemp()
        self._original_lockfile = LOCKFILE
        
    def tearDown(self):
        if os.path.exists(self.temp_lockfile):
            os.remove(self.temp_lockfile)

    def test_service1_returns_500_when_lockfile_present(self):
        """Service1 should return 500 when lockfile exists."""
        with patch('app.LOCKFILE', self.temp_lockfile):
            # Create the lockfile
            with open(self.temp_lockfile, 'w') as f:
                f.write('locked')
            
            # Simulate JSON client (curl)
            response = self.client.get('/service1', headers={'User-Agent': 'curl/7.x'})
            self.assertEqual(response.status_code, 500)
            data = response.get_json()
            self.assertEqual(data['status'], 'error')
            self.assertIn('stale lockfile', data['reason'])

    def test_service1_returns_200_after_lockfile_removed(self):
        """Service1 should return 200 after lockfile is removed (remediation)."""
        with patch('app.LOCKFILE', self.temp_lockfile):
            # Create the lockfile first
            with open(self.temp_lockfile, 'w') as f:
                f.write('locked')
            
            # Verify it's broken
            response = self.client.get('/service1', headers={'User-Agent': 'curl/7.x'})
            self.assertEqual(response.status_code, 500)
            
            # Remediation: Remove the lockfile (simulates fix_service1)
            os.remove(self.temp_lockfile)
            
            # Verify service is healthy
            response = self.client.get('/service1', headers={'User-Agent': 'curl/7.x'})
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data['status'], 'ok')
            self.assertEqual(data['scenario'], 'stale_lockfile')

    def test_service1_healthy_when_no_lockfile(self):
        """Service1 should be healthy when no lockfile exists."""
        with patch('app.LOCKFILE', self.temp_lockfile):
            # Ensure lockfile doesn't exist
            if os.path.exists(self.temp_lockfile):
                os.remove(self.temp_lockfile)
            
            response = self.client.get('/service1', headers={'User-Agent': 'curl/7.x'})
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
