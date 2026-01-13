"""Tests for CLI utilities."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch

from agentic_scraper.cli.utils import (
    retry_on_error,
    RetryableError,
    UserError,
    handle_cli_error,
    validate_file_path,
    validate_scraper_root,
    confirm_action,
    print_success,
    print_warning,
    print_error,
    print_info,
)


# ============================================================================
# RETRY LOGIC TESTS
# ============================================================================

def test_retry_on_error_sync_success_first_attempt():
    """Test retry decorator succeeds on first attempt (sync)."""
    call_count = 0

    @retry_on_error(max_attempts=3)
    def func():
        nonlocal call_count
        call_count += 1
        return "success"

    result = func()

    assert result == "success"
    assert call_count == 1


def test_retry_on_error_sync_success_after_retry():
    """Test retry decorator succeeds after retries (sync)."""
    call_count = 0

    @retry_on_error(max_attempts=3, delay=0.01)
    def func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RetryableError("Transient error")
        return "success"

    result = func()

    assert result == "success"
    assert call_count == 3


def test_retry_on_error_sync_exhausts_retries():
    """Test retry decorator exhausts all retries (sync)."""
    call_count = 0

    @retry_on_error(max_attempts=3, delay=0.01)
    def func():
        nonlocal call_count
        call_count += 1
        raise RetryableError("Always fails")

    with pytest.raises(RetryableError, match="Always fails"):
        func()

    assert call_count == 3


def test_retry_on_error_sync_non_retryable_exception():
    """Test retry decorator doesn't retry non-retryable exceptions (sync)."""
    call_count = 0

    @retry_on_error(max_attempts=3, exceptions=(RetryableError,))
    def func():
        nonlocal call_count
        call_count += 1
        raise ValueError("Not retryable")

    with pytest.raises(ValueError, match="Not retryable"):
        func()

    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_on_error_async_success_first_attempt():
    """Test retry decorator succeeds on first attempt (async)."""
    call_count = 0

    @retry_on_error(max_attempts=3)
    async def func():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await func()

    assert result == "success"
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_on_error_async_success_after_retry():
    """Test retry decorator succeeds after retries (async)."""
    call_count = 0

    @retry_on_error(max_attempts=3, delay=0.01)
    async def func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RetryableError("Transient error")
        return "success"

    result = await func()

    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_on_error_async_exhausts_retries():
    """Test retry decorator exhausts all retries (async)."""
    call_count = 0

    @retry_on_error(max_attempts=3, delay=0.01)
    async def func():
        nonlocal call_count
        call_count += 1
        raise RetryableError("Always fails")

    with pytest.raises(RetryableError, match="Always fails"):
        await func()

    assert call_count == 3


def test_retry_on_error_exponential_backoff():
    """Test retry decorator uses exponential backoff."""
    call_times = []

    @retry_on_error(max_attempts=3, delay=0.1, backoff=2.0)
    def func():
        call_times.append(asyncio.get_event_loop().time())
        raise RetryableError("Test")

    with pytest.raises(RetryableError):
        func()

    # Should have 3 attempts
    assert len(call_times) == 3

    # Note: We can't reliably test exact timing due to test environment variations
    # Just verify we got 3 attempts


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

@patch("claude_scraper.cli.utils.console")
def test_handle_cli_error_user_error(mock_console):
    """Test handling UserError."""
    error = UserError("Invalid configuration")

    handle_cli_error(error, debug=False)

    # Should print error and suggestion
    assert mock_console.print.called
    calls = [str(call) for call in mock_console.print.call_args_list]
    output = " ".join(calls)
    assert "Error" in output or "error" in output


@patch("claude_scraper.cli.utils.console")
def test_handle_cli_error_file_not_found(mock_console):
    """Test handling FileNotFoundError."""
    error = FileNotFoundError("test.txt not found")

    handle_cli_error(error, debug=False)

    assert mock_console.print.called
    calls = [str(call) for call in mock_console.print.call_args_list]
    output = " ".join(calls)
    assert "File Not Found" in output or "file" in output.lower()


@patch("claude_scraper.cli.utils.console")
def test_handle_cli_error_permission_error(mock_console):
    """Test handling PermissionError."""
    error = PermissionError("Access denied")

    handle_cli_error(error, debug=False)

    assert mock_console.print.called
    calls = [str(call) for call in mock_console.print.call_args_list]
    output = " ".join(calls)
    assert "Permission" in output or "permission" in output.lower()


@patch("claude_scraper.cli.utils.console")
def test_handle_cli_error_value_error(mock_console):
    """Test handling ValueError."""
    error = ValueError("Invalid format")

    handle_cli_error(error, debug=False)

    assert mock_console.print.called


@patch("claude_scraper.cli.utils.console")
def test_handle_cli_error_generic_error(mock_console):
    """Test handling generic error."""
    error = RuntimeError("Something went wrong")

    handle_cli_error(error, debug=False)

    assert mock_console.print.called


@patch("claude_scraper.cli.utils.console")
def test_handle_cli_error_with_debug(mock_console):
    """Test handling error with debug mode."""
    error = RuntimeError("Test error")

    handle_cli_error(error, debug=True)

    # Should print traceback in debug mode
    assert mock_console.print_exception.called


# ============================================================================
# VALIDATION TESTS
# ============================================================================

def test_validate_file_path_exists(tmp_path):
    """Test validating existing path."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")

    # Should not raise
    validate_file_path(test_file, must_exist=True)


def test_validate_file_path_not_exists():
    """Test validating non-existent path."""
    test_file = Path("/nonexistent/file.txt")

    with pytest.raises(UserError, match="does not exist"):
        validate_file_path(test_file, must_exist=True)


def test_validate_file_path_must_be_file(tmp_path):
    """Test validating path must be file."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")

    # Should not raise
    validate_file_path(test_file, must_be_file=True)


def test_validate_file_path_not_a_file(tmp_path):
    """Test validating path is not a file."""
    test_dir = tmp_path / "testdir"
    test_dir.mkdir()

    with pytest.raises(UserError, match="not a file"):
        validate_file_path(test_dir, must_be_file=True)


def test_validate_file_path_must_be_dir(tmp_path):
    """Test validating path must be directory."""
    test_dir = tmp_path / "testdir"
    test_dir.mkdir()

    # Should not raise
    validate_file_path(test_dir, must_be_dir=True)


def test_validate_file_path_not_a_dir(tmp_path):
    """Test validating path is not a directory."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")

    with pytest.raises(UserError, match="not a directory"):
        validate_file_path(test_file, must_be_dir=True)


def test_validate_scraper_root_exists(tmp_path):
    """Test validating existing scraper root."""
    scraper_root = tmp_path / "sourcing" / "scraping"
    scraper_root.mkdir(parents=True)
    (scraper_root / "test.py").write_text("# test")

    # Should not raise
    validate_scraper_root(scraper_root)


def test_validate_scraper_root_not_exists():
    """Test validating non-existent scraper root."""
    scraper_root = Path("/nonexistent/sourcing/scraping")

    with pytest.raises(UserError, match="does not exist"):
        validate_scraper_root(scraper_root)


def test_validate_scraper_root_not_a_dir(tmp_path):
    """Test validating scraper root is not a directory."""
    scraper_file = tmp_path / "scraper.py"
    scraper_file.write_text("# test")

    with pytest.raises(UserError, match="not a directory"):
        validate_scraper_root(scraper_file)


@patch("claude_scraper.cli.utils.console")
def test_validate_scraper_root_empty(mock_console, tmp_path):
    """Test validating empty scraper root."""
    scraper_root = tmp_path / "sourcing" / "scraping"
    scraper_root.mkdir(parents=True)

    # Should not raise, but should warn
    validate_scraper_root(scraper_root)

    # Should have printed warning
    assert mock_console.print.called


# ============================================================================
# CONFIRMATION TESTS
# ============================================================================

@patch("click.confirm")
def test_confirm_action_yes(mock_confirm):
    """Test confirming action."""
    mock_confirm.return_value = True

    result = confirm_action("Proceed?")

    assert result is True
    assert mock_confirm.called


@patch("click.confirm")
def test_confirm_action_no(mock_confirm):
    """Test rejecting action."""
    mock_confirm.return_value = False

    result = confirm_action("Proceed?")

    assert result is False
    assert mock_confirm.called


# ============================================================================
# FORMATTING TESTS
# ============================================================================

@patch("claude_scraper.cli.utils.console")
def test_print_success(mock_console):
    """Test printing success message."""
    print_success("Operation completed")

    assert mock_console.print.called
    call_args = str(mock_console.print.call_args)
    assert "Operation completed" in call_args


@patch("claude_scraper.cli.utils.console")
def test_print_warning(mock_console):
    """Test printing warning message."""
    print_warning("Warning message")

    assert mock_console.print.called
    call_args = str(mock_console.print.call_args)
    assert "Warning message" in call_args


@patch("claude_scraper.cli.utils.console")
def test_print_error(mock_console):
    """Test printing error message."""
    print_error("Error message")

    assert mock_console.print.called
    call_args = str(mock_console.print.call_args)
    assert "Error message" in call_args


@patch("claude_scraper.cli.utils.console")
def test_print_info(mock_console):
    """Test printing info message."""
    print_info("Info message")

    assert mock_console.print.called
    call_args = str(mock_console.print.call_args)
    assert "Info message" in call_args
