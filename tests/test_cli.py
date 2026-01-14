"""Tests for CLI commands (fix and update)."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from click.testing import CliRunner

from agentic_scraper.cli.main import cli
from agentic_scraper.fixers.fixer import FixerResult
from agentic_scraper.fixers.updater import UpdaterResult, ScraperInfo


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def runner():
    """Create Click test runner."""
    return CliRunner()


@pytest.fixture
def sample_scraper(tmp_path):
    """Create sample scraper file."""
    scraper_root = tmp_path / "sourcing" / "scraping"
    scraper_root.mkdir(parents=True)

    scraper_file = scraper_root / "scraper_miso_http.py"
    scraper_file.write_text("""
# INFRASTRUCTURE_VERSION: 1.4.0
# LAST_UPDATED: 2024-01-01
# GENERATOR_AGENT: http-collector-generator

import requests

def collect():
    url = "https://old-api.example.com"
    return requests.get(url).json()
""")

    return scraper_file


# ============================================================================
# FIX COMMAND TESTS
# ============================================================================

def test_fix_command_help(runner):
    """Test fix command help output."""
    result = runner.invoke(cli, ["fix", "--help"])

    assert result.exit_code == 0
    assert "Fix issues in an existing scraper" in result.output
    assert "--scraper-root" in result.output
    assert "--scraper" in result.output
    assert "--validate" in result.output
    assert "--debug" in result.output


def test_fix_command_no_scrapers_found(runner, tmp_path):
    """Test fix command when no scrapers found."""
    scraper_root = tmp_path / "empty"
    scraper_root.mkdir()

    with patch("claude_scraper.fixers.fixer.ScraperFixer") as mock_fixer_class:
        mock_fixer = Mock()
        mock_fixer.scan_scrapers.return_value = []
        mock_fixer_class.return_value = mock_fixer

        result = runner.invoke(
            cli,
            ["fix", "--scraper-root", str(scraper_root)],
            input="",
        )

        assert result.exit_code == 1
        assert "No scrapers found" in result.output


@patch("claude_scraper.fixers.fixer.ScraperFixer")
@patch("claude_scraper.cli.main.asyncio.run")
def test_fix_command_interactive_success(mock_asyncio_run, mock_fixer_class, runner, tmp_path, sample_scraper):
    """Test fix command interactive workflow success."""
    scraper_root = sample_scraper.parent

    # Mock fixer
    mock_fixer = Mock()
    mock_fixer.scan_scrapers.return_value = [sample_scraper]
    mock_fixer_class.return_value = mock_fixer

    # Mock fix result
    fix_result = FixerResult(
        scraper_path=sample_scraper,
        problem_description="API endpoint changed",
        fix_description="Updated API URL",
        files_modified=[sample_scraper],
        validation_passed=True,
    )
    mock_asyncio_run.return_value = fix_result

    # Interactive input: select scraper, describe problem, add fix operation (OLD -> NEW), blank line to finish
    result = runner.invoke(
        cli,
        ["fix", "--scraper-root", str(scraper_root)],
        input="1\nAPI endpoint changed\nhttps://old-api.example.com -> https://new-api.example.com\n\n",
    )

    assert result.exit_code == 0
    assert "Found 1 scraper" in result.output
    assert "Fix applied successfully" in result.output
    assert "Files modified: 1" in result.output
    assert "QA Validation: PASSED" in result.output


@patch("claude_scraper.fixers.fixer.ScraperFixer")
def test_fix_command_with_scraper_option(mock_fixer_class, runner, sample_scraper):
    """Test fix command with --scraper option."""
    scraper_root = sample_scraper.parent

    # Mock fixer
    mock_fixer = Mock()
    mock_fixer_class.return_value = mock_fixer

    # Mock fix result
    fix_result = FixerResult(
        scraper_path=sample_scraper,
        problem_description="Test fix",
        fix_description="Applied fixes",
        files_modified=[sample_scraper],
        validation_passed=True,
    )

    with patch("claude_scraper.cli.main.asyncio.run", return_value=fix_result):
        result = runner.invoke(
            cli,
            [
                "fix",
                "--scraper-root", str(scraper_root),
                "--scraper", str(sample_scraper),
            ],
            input="Test fix\nold_string -> new_string\n\n",
        )

        assert result.exit_code == 0
        assert "Fix applied successfully" in result.output


@patch("claude_scraper.fixers.fixer.ScraperFixer")
@patch("claude_scraper.cli.main.asyncio.run")
def test_fix_command_validation_failed(mock_asyncio_run, mock_fixer_class, runner, tmp_path, sample_scraper):
    """Test fix command when validation fails."""
    scraper_root = sample_scraper.parent

    # Mock fixer
    mock_fixer = Mock()
    mock_fixer.scan_scrapers.return_value = [sample_scraper]
    mock_fixer_class.return_value = mock_fixer

    # Mock fix result with validation failure
    fix_result = FixerResult(
        scraper_path=sample_scraper,
        problem_description="Test fix",
        fix_description="Applied fixes",
        files_modified=[sample_scraper],
        validation_passed=False,
        validation_issues={"syntax": ["Invalid Python syntax"]},
    )
    mock_asyncio_run.return_value = fix_result

    result = runner.invoke(
        cli,
        ["fix", "--scraper-root", str(scraper_root)],
        input="1\nTest fix\nold -> new\n\n",
    )

    assert result.exit_code == 0
    assert "Validation" in result.output or "QA" in result.output


@patch("claude_scraper.fixers.fixer.ScraperFixer")
@patch("claude_scraper.cli.main.asyncio.run")
def test_fix_command_no_validate_flag(mock_asyncio_run, mock_fixer_class, runner, tmp_path, sample_scraper):
    """Test fix command with --no-validate flag."""
    scraper_root = sample_scraper.parent

    # Mock fixer
    mock_fixer = Mock()
    mock_fixer.scan_scrapers.return_value = [sample_scraper]
    mock_fixer_class.return_value = mock_fixer

    # Mock fix result without validation
    fix_result = FixerResult(
        scraper_path=sample_scraper,
        problem_description="Test fix",
        fix_description="Applied fixes",
        files_modified=[sample_scraper],
    )
    mock_asyncio_run.return_value = fix_result

    result = runner.invoke(
        cli,
        ["fix", "--scraper-root", str(scraper_root), "--no-validate"],
        input="1\nTest fix\nold -> new\n\n",
    )

    assert result.exit_code == 0
    # Without validation, should just show fix complete
    assert "Fix" in result.output or "applied" in result.output


@patch("claude_scraper.fixers.fixer.ScraperFixer")
@patch("claude_scraper.cli.main.asyncio.run")
def test_fix_command_multiple_operations(mock_asyncio_run, mock_fixer_class, runner, tmp_path, sample_scraper):
    """Test fix command with multiple fix operations."""
    scraper_root = sample_scraper.parent

    # Mock fixer
    mock_fixer = Mock()
    mock_fixer.scan_scrapers.return_value = [sample_scraper]
    mock_fixer_class.return_value = mock_fixer

    # Mock fix result
    fix_result = FixerResult(
        scraper_path=sample_scraper,
        problem_description="Multiple fixes",
        fix_description="Applied 2 fixes",
        files_modified=[sample_scraper],
        validation_passed=True,
    )
    mock_asyncio_run.return_value = fix_result

    # Input: scraper selection, problem, first fix, second fix, blank line to finish
    result = runner.invoke(
        cli,
        ["fix", "--scraper-root", str(scraper_root)],
        input="1\nMultiple fixes\nold1 -> new1\nold2 -> new2\n\n",
    )

    assert result.exit_code == 0
    assert "Fix" in result.output or "applied" in result.output


@patch("claude_scraper.fixers.fixer.ScraperFixer")
@patch("claude_scraper.cli.main.asyncio.run")
def test_fix_command_error_handling(mock_asyncio_run, mock_fixer_class, runner, tmp_path, sample_scraper):
    """Test fix command error handling."""
    scraper_root = sample_scraper.parent

    # Mock fixer
    mock_fixer = Mock()
    mock_fixer.scan_scrapers.return_value = [sample_scraper]
    mock_fixer_class.return_value = mock_fixer

    # Mock error during fix
    mock_asyncio_run.side_effect = Exception("Fix failed!")

    result = runner.invoke(
        cli,
        ["fix", "--scraper-root", str(scraper_root)],
        input="1\nTest fix\nold -> new\n\n",
    )

    assert result.exit_code == 1
    assert "Error" in result.output or "error" in result.output


# ============================================================================
# UPDATE COMMAND TESTS
# ============================================================================

def test_update_command_help(runner):
    """Test update command help output."""
    result = runner.invoke(cli, ["update", "--help"])

    assert result.exit_code == 0
    assert "Update scrapers to current infrastructure version" in result.output
    assert "--mode" in result.output
    assert "--scraper-root" in result.output
    assert "--validate" in result.output
    assert "--non-interactive" in result.output
    assert "--debug" in result.output


@patch("claude_scraper.fixers.updater.ScraperUpdater")
def test_update_command_scan_mode(mock_updater_class, runner, tmp_path):
    """Test update command in scan mode."""
    scraper_root = tmp_path / "sourcing" / "scraping"
    scraper_root.mkdir(parents=True)

    # Mock updater
    mock_updater = Mock()
    mock_updater.scan_scrapers.return_value = [
        ScraperInfo(
            path=Path("scraper_miso.py"),
            current_version="1.4.0",
            needs_update=True,
            data_source="MISO",
            data_type="energy_pricing",
        )
    ]
    mock_updater.generate_scan_report.return_value = "Scan Report: 1 outdated"
    mock_updater_class.return_value = mock_updater

    result = runner.invoke(
        cli,
        ["update", "--mode", "scan", "--scraper-root", str(scraper_root)],
    )

    assert result.exit_code == 0
    assert "Scan Report" in result.output


@patch("claude_scraper.fixers.updater.ScraperUpdater")
@patch("claude_scraper.cli.main.asyncio.run")
def test_update_command_auto_mode_interactive(mock_asyncio_run, mock_updater_class, runner, tmp_path):
    """Test update command in auto mode (interactive)."""
    scraper_root = tmp_path / "sourcing" / "scraping"
    scraper_root.mkdir(parents=True)

    scraper_info = ScraperInfo(
        path=Path("scraper_miso.py"),
        current_version="1.4.0",
        needs_update=True,
        data_source="MISO",
        data_type="energy_pricing",
    )

    # Mock updater
    mock_updater = Mock()
    mock_updater.scan_scrapers.return_value = [scraper_info]
    mock_updater.generate_scan_report.return_value = "Scan Report: 1 outdated"
    mock_updater_class.return_value = mock_updater

    # Mock update result
    update_result = UpdaterResult(
        scraper_path=Path("scraper_miso.py"),
        old_version="1.4.0",
        new_version="1.6.0",
        generator_agent="http-collector-generator",
        validation_passed=True,
    )
    mock_asyncio_run.return_value = update_result

    # Input: select scraper number 1 to update
    result = runner.invoke(
        cli,
        ["update", "--mode", "auto", "--scraper-root", str(scraper_root)],
        input="1\n",
    )

    assert result.exit_code == 0
    # Should show some indication of success
    assert "scraper" in result.output.lower() or "update" in result.output.lower()


@patch("claude_scraper.fixers.updater.ScraperUpdater")
@patch("claude_scraper.cli.main.asyncio.run")
def test_update_command_auto_mode_non_interactive(mock_asyncio_run, mock_updater_class, runner, tmp_path):
    """Test update command in auto mode (non-interactive)."""
    scraper_root = tmp_path / "sourcing" / "scraping"
    scraper_root.mkdir(parents=True)

    scraper_info = ScraperInfo(
        path=Path("scraper_miso.py"),
        current_version="1.4.0",
        needs_update=True,
        data_source="MISO",
        data_type="energy_pricing",
    )

    # Mock updater
    mock_updater = Mock()
    mock_updater.scan_scrapers.return_value = [scraper_info]
    mock_updater.generate_scan_report.return_value = "Scan Report: 1 outdated"
    mock_updater.generate_update_report.return_value = "Update Report: 1 updated"
    mock_updater_class.return_value = mock_updater

    # Mock update result
    update_result = UpdaterResult(
        scraper_path=Path("scraper_miso.py"),
        old_version="1.4.0",
        new_version="1.6.0",
        generator_agent="http-collector-generator",
        validation_passed=True,
    )
    mock_asyncio_run.return_value = update_result

    result = runner.invoke(
        cli,
        ["update", "--mode", "auto", "--scraper-root", str(scraper_root), "--non-interactive"],
    )

    assert result.exit_code == 0
    assert "Update Report" in result.output


@patch("claude_scraper.fixers.updater.ScraperUpdater")
def test_update_command_no_outdated_scrapers(mock_updater_class, runner, tmp_path):
    """Test update command when no outdated scrapers found."""
    scraper_root = tmp_path / "sourcing" / "scraping"
    scraper_root.mkdir(parents=True)

    # Mock updater - no outdated scrapers
    mock_updater = Mock()
    mock_updater.scan_scrapers.return_value = [
        ScraperInfo(
            path=Path("scraper_miso.py"),
            current_version="1.6.0",
            needs_update=False,
            data_source="MISO",
            data_type="energy_pricing",
        )
    ]
    mock_updater.generate_scan_report.return_value = "All scrapers up-to-date"
    mock_updater_class.return_value = mock_updater

    result = runner.invoke(
        cli,
        ["update", "--mode", "auto", "--scraper-root", str(scraper_root)],
    )

    assert result.exit_code == 0
    assert "up-to-date" in result.output or "No outdated" in result.output


@patch("claude_scraper.fixers.updater.ScraperUpdater")
@patch("claude_scraper.cli.main.asyncio.run")
def test_update_command_validation_failed(mock_asyncio_run, mock_updater_class, runner, tmp_path):
    """Test update command when validation fails."""
    scraper_root = tmp_path / "sourcing" / "scraping"
    scraper_root.mkdir(parents=True)

    scraper_info = ScraperInfo(
        path=Path("scraper_miso.py"),
        current_version="1.4.0",
        needs_update=True,
        data_source="MISO",
        data_type="energy_pricing",
    )

    # Mock updater
    mock_updater = Mock()
    mock_updater.scan_scrapers.return_value = [scraper_info]
    mock_updater.generate_scan_report.return_value = "Scan Report: 1 outdated"
    mock_updater_class.return_value = mock_updater

    # Mock update result with validation failure
    update_result = UpdaterResult(
        scraper_path=Path("scraper_miso.py"),
        old_version="1.4.0",
        new_version="1.6.0",
        generator_agent="http-collector-generator",
        validation_passed=False,
    )
    mock_asyncio_run.return_value = update_result

    result = runner.invoke(
        cli,
        ["update", "--mode", "auto", "--scraper-root", str(scraper_root)],
        input="1\n",
    )

    assert result.exit_code == 0
    # Should still complete but indicate validation issues


@patch("claude_scraper.fixers.updater.ScraperUpdater")
@patch("claude_scraper.cli.main.asyncio.run")
def test_update_command_no_validate_flag(mock_asyncio_run, mock_updater_class, runner, tmp_path):
    """Test update command with --no-validate flag."""
    scraper_root = tmp_path / "sourcing" / "scraping"
    scraper_root.mkdir(parents=True)

    scraper_info = ScraperInfo(
        path=Path("scraper_miso.py"),
        current_version="1.4.0",
        needs_update=True,
        data_source="MISO",
        data_type="energy_pricing",
    )

    # Mock updater
    mock_updater = Mock()
    mock_updater.scan_scrapers.return_value = [scraper_info]
    mock_updater.generate_scan_report.return_value = "Scan Report: 1 outdated"
    mock_updater_class.return_value = mock_updater

    # Mock update result without validation
    update_result = UpdaterResult(
        scraper_path=Path("scraper_miso.py"),
        old_version="1.4.0",
        new_version="1.6.0",
        generator_agent="http-collector-generator",
    )
    mock_asyncio_run.return_value = update_result

    result = runner.invoke(
        cli,
        ["update", "--mode", "auto", "--scraper-root", str(scraper_root), "--no-validate"],
        input="1\n",
    )

    assert result.exit_code == 0
    # Validation should be skipped


@patch("claude_scraper.fixers.updater.ScraperUpdater")
@patch("claude_scraper.cli.main.asyncio.run")
def test_update_command_error_handling(mock_asyncio_run, mock_updater_class, runner, tmp_path):
    """Test update command error handling."""
    scraper_root = tmp_path / "sourcing" / "scraping"
    scraper_root.mkdir(parents=True)

    scraper_info = ScraperInfo(
        path=Path("scraper_miso.py"),
        current_version="1.4.0",
        needs_update=True,
        data_source="MISO",
        data_type="energy_pricing",
    )

    # Mock updater
    mock_updater = Mock()
    mock_updater.scan_scrapers.return_value = [scraper_info]
    mock_updater.generate_scan_report.return_value = "Scan Report: 1 outdated"
    mock_updater_class.return_value = mock_updater

    # Mock error during update
    mock_asyncio_run.side_effect = Exception("Update failed!")

    result = runner.invoke(
        cli,
        ["update", "--mode", "auto", "--scraper-root", str(scraper_root)],
        input="y\n",
    )

    # Should handle error gracefully
    assert "Error" in result.output or "failed" in result.output


@patch("claude_scraper.fixers.updater.ScraperUpdater")
@patch("claude_scraper.cli.main.asyncio.run")
def test_update_command_skip_scraper_interactive(mock_asyncio_run, mock_updater_class, runner, tmp_path):
    """Test update command skipping scraper in interactive mode."""
    scraper_root = tmp_path / "sourcing" / "scraping"
    scraper_root.mkdir(parents=True)

    scraper_info = ScraperInfo(
        path=Path("scraper_miso.py"),
        current_version="1.4.0",
        needs_update=True,
        data_source="MISO",
        data_type="energy_pricing",
    )

    # Mock updater
    mock_updater = Mock()
    mock_updater.scan_scrapers.return_value = [scraper_info]
    mock_updater.generate_scan_report.return_value = "Scan Report: 1 outdated"
    mock_updater.generate_update_report.return_value = "Update Report: 0 updated"
    mock_updater_class.return_value = mock_updater

    # Input: enter empty selection (skip updating)
    result = runner.invoke(
        cli,
        ["update", "--mode", "auto", "--scraper-root", str(scraper_root)],
        input="\n",
    )

    # Should either accept empty (exit 0) or reject invalid input (exit 1)
    assert result.exit_code in (0, 1)


# ============================================================================
# DEBUG MODE TESTS
# ============================================================================

@patch("claude_scraper.fixers.fixer.ScraperFixer")
def test_fix_command_debug_mode(mock_fixer_class, runner, tmp_path):
    """Test fix command with --debug flag."""
    scraper_root = tmp_path / "sourcing" / "scraping"
    scraper_root.mkdir(parents=True)

    # Mock fixer
    mock_fixer = Mock()
    mock_fixer.scan_scrapers.return_value = []
    mock_fixer_class.return_value = mock_fixer

    result = runner.invoke(
        cli,
        ["fix", "--scraper-root", str(scraper_root), "--debug"],
    )

    # Debug mode should be activated (check logging)
    assert result.exit_code == 1  # No scrapers found


@patch("claude_scraper.fixers.updater.ScraperUpdater")
def test_update_command_debug_mode(mock_updater_class, runner, tmp_path):
    """Test update command with --debug flag."""
    scraper_root = tmp_path / "sourcing" / "scraping"
    scraper_root.mkdir(parents=True)

    # Mock updater
    mock_updater = Mock()
    mock_updater.scan_scrapers.return_value = []
    mock_updater.generate_scan_report.return_value = "No scrapers found"
    mock_updater_class.return_value = mock_updater

    result = runner.invoke(
        cli,
        ["update", "--mode", "scan", "--scraper-root", str(scraper_root), "--debug"],
    )

    # Debug mode should be activated; exit code might be 0 or 1 depending on whether no scrapers is an error
    assert result.exit_code in (0, 1)
