"""Tests for ci/upload_junit_results.py graceful secret handling."""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add ci directory to path
ci_dir = Path(__file__).parent.parent.parent / "ci"
sys.path.insert(0, str(ci_dir))

import upload_junit_results


@pytest.fixture
def sample_junit_xml():
    """Create a sample JUnit XML file."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="test_suite" tests="5" failures="1" errors="0" skipped="1" time="2.5">
    <testcase name="test_pass_1" classname="tests.test_module" time="0.5"/>
    <testcase name="test_pass_2" classname="tests.test_module" time="0.3"/>
    <testcase name="test_fail" classname="tests.test_module" time="0.7">
        <failure message="AssertionError: expected 1 but got 2"/>
    </testcase>
    <testcase name="test_skip" classname="tests.test_module" time="0.0">
        <skipped message="Not implemented yet"/>
    </testcase>
    <testcase name="test_pass_3" classname="tests.test_module" time="1.0"/>
</testsuite>"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(xml_content)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    os.unlink(temp_path)


@pytest.fixture
def mock_github_env():
    """Mock required GitHub environment variables."""
    return {
        "GITHUB_REPOSITORY": "test-org/test-repo",
        "GITHUB_REF_NAME": "main",
        "GITHUB_SHA": "abc123def456",
        "SAMANVAYA_TEST_SUITE": "backend"
    }


def test_optional_environment_with_value():
    """Test _optional_environment returns value when present."""
    with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
        result = upload_junit_results._optional_environment("TEST_VAR")
        assert result == "test_value"


def test_optional_environment_without_value():
    """Test _optional_environment returns None when missing."""
    with patch.dict(os.environ, {}, clear=True):
        result = upload_junit_results._optional_environment("MISSING_VAR")
        assert result is None


def test_optional_environment_with_empty_value():
    """Test _optional_environment returns None for empty strings."""
    with patch.dict(os.environ, {"EMPTY_VAR": ""}):
        result = upload_junit_results._optional_environment("EMPTY_VAR")
        assert result is None
    
    with patch.dict(os.environ, {"WHITESPACE_VAR": "   "}):
        result = upload_junit_results._optional_environment("WHITESPACE_VAR")
        assert result is None


def test_main_with_missing_api_url(sample_junit_xml, mock_github_env, capsys):
    """Test graceful handling when SAMANVAYA_API_URL is missing."""
    env = mock_github_env.copy()
    env.update({
        "SAMANVAYA_PROJECT_ID": "proj123",
        "SAMANVAYA_TEST_RESULTS_TOKEN": "token456"
    })
    
    with patch.dict(os.environ, env, clear=True):
        with patch('sys.argv', ['upload_junit_results.py', '--junit', sample_junit_xml]):
            exit_code = upload_junit_results.main()
    
    assert exit_code == 0  # Graceful exit
    
    captured = capsys.readouterr()
    assert "Samanvaya secrets not configured" in captured.out
    assert "SAMANVAYA_API_URL" in captured.out
    assert "SAMANVAYA_PROJECT_ID" in captured.out
    assert "SAMANVAYA_TEST_RESULTS_TOKEN" in captured.out


def test_main_with_missing_project_id(sample_junit_xml, mock_github_env, capsys):
    """Test graceful handling when SAMANVAYA_PROJECT_ID is missing."""
    env = mock_github_env.copy()
    env.update({
        "SAMANVAYA_API_URL": "https://api.example.com",
        "SAMANVAYA_TEST_RESULTS_TOKEN": "token456"
    })
    
    with patch.dict(os.environ, env, clear=True):
        with patch('sys.argv', ['upload_junit_results.py', '--junit', sample_junit_xml]):
            exit_code = upload_junit_results.main()
    
    assert exit_code == 0
    
    captured = capsys.readouterr()
    assert "Samanvaya secrets not configured" in captured.out


def test_main_with_missing_token(sample_junit_xml, mock_github_env, capsys):
    """Test graceful handling when SAMANVAYA_TEST_RESULTS_TOKEN is missing."""
    env = mock_github_env.copy()
    env.update({
        "SAMANVAYA_API_URL": "https://api.example.com",
        "SAMANVAYA_PROJECT_ID": "proj123"
    })
    
    with patch.dict(os.environ, env, clear=True):
        with patch('sys.argv', ['upload_junit_results.py', '--junit', sample_junit_xml]):
            exit_code = upload_junit_results.main()
    
    assert exit_code == 0
    
    captured = capsys.readouterr()
    assert "Samanvaya secrets not configured" in captured.out


def test_main_with_all_secrets_missing(sample_junit_xml, mock_github_env, capsys):
    """Test graceful handling when all secrets are missing."""
    env = mock_github_env.copy()
    
    with patch.dict(os.environ, env, clear=True):
        with patch('sys.argv', ['upload_junit_results.py', '--junit', sample_junit_xml]):
            exit_code = upload_junit_results.main()
    
    assert exit_code == 0
    
    captured = capsys.readouterr()
    assert "Samanvaya secrets not configured" in captured.out
    assert "repository secrets:" in captured.out


def test_main_with_empty_secrets(sample_junit_xml, mock_github_env, capsys):
    """Test graceful handling when secrets are empty strings."""
    env = mock_github_env.copy()
    env.update({
        "SAMANVAYA_API_URL": "",
        "SAMANVAYA_PROJECT_ID": "   ",  # Whitespace only
        "SAMANVAYA_TEST_RESULTS_TOKEN": ""
    })
    
    with patch.dict(os.environ, env, clear=True):
        with patch('sys.argv', ['upload_junit_results.py', '--junit', sample_junit_xml]):
            exit_code = upload_junit_results.main()
    
    assert exit_code == 0
    
    captured = capsys.readouterr()
    assert "Samanvaya secrets not configured" in captured.out


@patch('urllib.request.urlopen')
def test_main_with_all_secrets_present(mock_urlopen, sample_junit_xml, mock_github_env):
    """Test normal upload when all secrets are configured."""
    # Mock successful HTTP response
    mock_response = MagicMock()
    mock_response.status = 201
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_response
    
    env = mock_github_env.copy()
    env.update({
        "SAMANVAYA_API_URL": "https://api.example.com",
        "SAMANVAYA_PROJECT_ID": "proj123",
        "SAMANVAYA_TEST_RESULTS_TOKEN": "token456"
    })
    
    with patch.dict(os.environ, env, clear=True):
        with patch('sys.argv', ['upload_junit_results.py', '--junit', sample_junit_xml]):
            exit_code = upload_junit_results.main()
    
    assert exit_code == 0
    
    # Verify HTTP request was made
    assert mock_urlopen.called
    call_args = mock_urlopen.call_args
    request = call_args[0][0]
    
    # Verify request details
    assert request.full_url == "https://api.example.com/api/qa/test-runs"
    assert request.method == "POST"
    assert request.headers["Content-type"] == "application/json"
    assert request.headers["X-test-results-token"] == "token456"
    
    # Verify payload content
    payload = eval(request.data.decode('utf-8').replace('null', 'None').replace('true', 'True').replace('false', 'False'))
    assert payload["project_id"] == "proj123"
    assert payload["repository"] == "test-org/test-repo"
    assert payload["tests_run"] == 5
    assert payload["tests_failed"] == 1
    assert payload["tests_skipped"] == 1
    assert payload["tests_passed"] == 3
    assert payload["status"] == "failed"


def test_preservation_junit_parsing(sample_junit_xml, mock_github_env):
    """Test that JUnit XML parsing behavior is preserved."""
    # This test validates requirement 3.7 - unchanged JUnit parsing
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        env = mock_github_env.copy()
        env.update({
            "SAMANVAYA_API_URL": "https://api.example.com",
            "SAMANVAYA_PROJECT_ID": "proj123",
            "SAMANVAYA_TEST_RESULTS_TOKEN": "token456"
        })
        
        with patch.dict(os.environ, env, clear=True):
            with patch('sys.argv', ['upload_junit_results.py', '--junit', sample_junit_xml]):
                upload_junit_results.main()
        
        # Verify the payload structure matches preservation requirements
        request = mock_urlopen.call_args[0][0]
        payload = eval(request.data.decode('utf-8').replace('null', 'None').replace('true', 'True').replace('false', 'False'))
        
        # Verify required fields are present (requirement 3.7)
        assert "tests_run" in payload
        assert "tests_failed" in payload
        assert "tests_passed" in payload
        assert "tests_skipped" in payload
        assert "duration_seconds" in payload
        assert "status" in payload
        
        # Verify calculations are correct
        assert payload["tests_run"] == 5
        assert payload["tests_failed"] == 1  # failures + errors
        assert payload["tests_skipped"] == 1
        assert payload["tests_passed"] == 3  # tests_run - tests_failed - tests_skipped
        assert abs(payload["duration_seconds"] - 2.5) < 0.01
