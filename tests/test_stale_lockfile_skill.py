"""Unit tests for the stale-lockfile skill functions.

These tests verify the skill's diagnosis and remediation logic
without requiring Docker.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the skill directory to the path
SKILL_DIR = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "stale-lockfile"
sys.path.insert(0, str(SKILL_DIR))

from diagnose import diagnose, _host_file_state
from remediate import remediate


class TestHostFileFunctions(unittest.TestCase):
    """Test host-based file operations without Docker."""
    
    def test_host_file_state_present(self) -> None:
        """Test _host_file_state returns present=True when file exists."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                result = _host_file_state(f.name)
                self.assertTrue(result["present"])
                self.assertEqual(result["error"], "")
            finally:
                os.unlink(f.name)
    
    def test_host_file_state_absent(self) -> None:
        """Test _host_file_state returns present=False when file doesn't exist."""
        result = _host_file_state("/tmp/nonexistent_file_abc123xyz")
        self.assertFalse(result["present"])
        self.assertEqual(result["error"], "")


class TestDiagnoseStaleLockfile(unittest.TestCase):
    """Test diagnose function with mocked dependencies."""
    
    @patch("diagnose._curl_code")
    @patch("diagnose._host_file_state")
    def test_diagnose_identifies_stale_lockfile(self, mock_file_state, mock_curl) -> None:
        """Test diagnose correctly identifies stale lockfile condition."""
        mock_curl.return_value = "500"
        mock_file_state.return_value = {"present": True, "error": ""}
        
        result = diagnose(
            target_url="http://test:5000",
            target_container=None,  # Host mode
            lock_path="/tmp/service.lock"
        )
        
        self.assertEqual(result["http_code"], "500")
        self.assertTrue(result["is_stale_lockfile_candidate"])
        self.assertEqual(result["scope"], "host")
    
    @patch("diagnose._curl_code")
    @patch("diagnose._host_file_state")
    def test_diagnose_healthy_service(self, mock_file_state, mock_curl) -> None:
        """Test diagnose identifies healthy service (no lockfile issue)."""
        mock_curl.return_value = "200"
        mock_file_state.return_value = {"present": False, "error": ""}
        
        result = diagnose(
            target_url="http://test:5000",
            target_container=None,
            lock_path="/tmp/service.lock"
        )
        
        self.assertEqual(result["http_code"], "200")
        self.assertFalse(result["is_stale_lockfile_candidate"])
    
    @patch("diagnose._curl_code")
    @patch("diagnose._host_file_state")
    def test_diagnose_500_without_lockfile_not_stale(self, mock_file_state, mock_curl) -> None:
        """Test diagnose doesn't flag as stale when 500 but no lockfile."""
        mock_curl.return_value = "500"
        mock_file_state.return_value = {"present": False, "error": ""}
        
        result = diagnose(
            target_url="http://test:5000",
            target_container=None,
            lock_path="/tmp/service.lock"
        )
        
        self.assertEqual(result["http_code"], "500")
        self.assertFalse(result["is_stale_lockfile_candidate"])


class TestRemediateStaleLockfile(unittest.TestCase):
    """Test remediate function with host-level file operations."""
    
    def test_remediate_removes_lockfile_host_mode(self) -> None:
        """Test remediate removes lockfile and reports success."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            lock_path = f.name
        
        # Verify file exists
        self.assertTrue(os.path.exists(lock_path))
        
        with patch("remediate._curl_code") as mock_curl:
            # First call returns 500 (before fix), second returns 200 (after fix)
            mock_curl.side_effect = ["500", "200"]
            
            result = remediate(
                target_url="http://test:5000",
                target_container=None,  # Host mode
                lock_path=lock_path
            )
            
            self.assertEqual(result["pre_http_code"], "500")
            self.assertEqual(result["post_http_code"], "200")
            self.assertTrue(result["fixed"])
            self.assertEqual(result["remove_returncode"], 0)
            self.assertEqual(result["scope"], "host")
        
        # Verify file was removed
        self.assertFalse(os.path.exists(lock_path))
    
    def test_remediate_handles_nonexistent_lockfile(self) -> None:
        """Test remediate handles case where lockfile doesn't exist."""
        lock_path = "/tmp/nonexistent_lockfile_test_abc123"
        
        with patch("remediate._curl_code") as mock_curl:
            mock_curl.side_effect = ["200", "200"]
            
            result = remediate(
                target_url="http://test:5000",
                target_container=None,
                lock_path=lock_path
            )
            
            # rm -f should not fail on nonexistent file
            self.assertEqual(result["remove_returncode"], 0)


if __name__ == "__main__":
    unittest.main()
