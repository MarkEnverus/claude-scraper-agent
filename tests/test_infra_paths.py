"""Tests for infrastructure path resolution utilities."""

import pytest
from pathlib import Path

from agentic_scraper.utils.infra_paths import (
    find_repo_root,
    validate_commons_directory,
    resolve_commons_source,
    REQUIRED_INFRASTRUCTURE_FILES,
)


class TestFindRepoRoot:
    """Tests for find_repo_root()."""

    def test_finds_pyproject_toml(self, tmp_path):
        """Should find repo root with pyproject.toml."""
        # Create structure: root/pyproject.toml, root/subdir/
        (tmp_path / "pyproject.toml").touch()
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        result = find_repo_root(subdir)
        assert result == tmp_path

    def test_finds_git_directory(self, tmp_path):
        """Should find repo root with .git/."""
        # Create structure: root/.git/, root/subdir/
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        result = find_repo_root(subdir)
        assert result == tmp_path

    def test_returns_none_if_not_found(self, tmp_path):
        """Should return None if no markers found."""
        result = find_repo_root(tmp_path)
        assert result is None

    def test_stops_at_filesystem_root(self):
        """Should not infinite loop at filesystem root."""
        result = find_repo_root(Path("/"))
        # Should either return None or / (both are acceptable)
        assert result is None or result == Path("/")


class TestValidateCommonsDirectory:
    """Tests for validate_commons_directory()."""

    def test_valid_directory(self, tmp_path):
        """Should validate when all files exist."""
        commons = tmp_path / "commons"
        commons.mkdir()

        for filename in REQUIRED_INFRASTRUCTURE_FILES:
            (commons / filename).touch()

        is_valid, missing = validate_commons_directory(commons)
        assert is_valid is True
        assert missing == []

    def test_missing_files(self, tmp_path):
        """Should report missing files."""
        commons = tmp_path / "commons"
        commons.mkdir()

        # Only create first 2 files
        for filename in REQUIRED_INFRASTRUCTURE_FILES[:2]:
            (commons / filename).touch()

        is_valid, missing = validate_commons_directory(commons)
        assert is_valid is False
        assert set(missing) == set(REQUIRED_INFRASTRUCTURE_FILES[2:])

    def test_directory_not_exists(self, tmp_path):
        """Should handle non-existent directory."""
        commons = tmp_path / "nonexistent"

        is_valid, missing = validate_commons_directory(commons)
        assert is_valid is False
        assert missing == list(REQUIRED_INFRASTRUCTURE_FILES)


class TestResolveCommonsSource:
    """Tests for resolve_commons_source()."""

    def test_finds_sourcing_commons(self, tmp_path):
        """Should find sourcing/commons/ (priority 1)."""
        # Create repo structure
        (tmp_path / "pyproject.toml").touch()
        commons = tmp_path / "sourcing" / "commons"
        commons.mkdir(parents=True)

        for filename in REQUIRED_INFRASTRUCTURE_FILES:
            (commons / filename).touch()

        result = resolve_commons_source(repo_root=tmp_path)
        assert result == commons

    def test_finds_sourcing_scraping_commons(self, tmp_path):
        """Should find sourcing/scraping/commons/ (priority 2)."""
        # Create repo structure (no sourcing/commons)
        (tmp_path / "pyproject.toml").touch()
        commons = tmp_path / "sourcing" / "scraping" / "commons"
        commons.mkdir(parents=True)

        for filename in REQUIRED_INFRASTRUCTURE_FILES:
            (commons / filename).touch()

        result = resolve_commons_source(repo_root=tmp_path)
        assert result == commons

    def test_finds_legacy_commons(self, tmp_path):
        """Should find commons/ (priority 3 - legacy)."""
        # Create repo structure (no sourcing/)
        (tmp_path / "pyproject.toml").touch()
        commons = tmp_path / "commons"
        commons.mkdir()

        for filename in REQUIRED_INFRASTRUCTURE_FILES:
            (commons / filename).touch()

        result = resolve_commons_source(repo_root=tmp_path)
        assert result == commons

    def test_raises_when_not_found(self, tmp_path):
        """Should raise FileNotFoundError with detailed message."""
        (tmp_path / "pyproject.toml").touch()

        with pytest.raises(FileNotFoundError) as exc_info:
            resolve_commons_source(repo_root=tmp_path)

        error_msg = str(exc_info.value)
        assert "Infrastructure commons not found" in error_msg
        assert "sourcing/commons" in error_msg
        assert "Required files:" in error_msg
        assert "collection_framework.py" in error_msg

    def test_auto_detects_repo_root(self, tmp_path, monkeypatch):
        """Should auto-detect repo root from CWD."""
        # Create repo structure
        (tmp_path / "pyproject.toml").touch()
        commons = tmp_path / "sourcing" / "commons"
        commons.mkdir(parents=True)

        for filename in REQUIRED_INFRASTRUCTURE_FILES:
            (commons / filename).touch()

        # Change CWD to subdir
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        monkeypatch.chdir(subdir)

        result = resolve_commons_source()
        assert result == commons

    def test_validates_all_required_files(self, tmp_path):
        """Should reject directory missing required files."""
        (tmp_path / "pyproject.toml").touch()
        commons = tmp_path / "sourcing" / "commons"
        commons.mkdir(parents=True)

        # Only create some files
        (commons / "collection_framework.py").touch()

        with pytest.raises(FileNotFoundError) as exc_info:
            resolve_commons_source(repo_root=tmp_path)

        error_msg = str(exc_info.value)
        assert "missing files:" in error_msg

    def test_priority_order(self, tmp_path):
        """Should prefer sourcing/commons/ over legacy commons/."""
        (tmp_path / "pyproject.toml").touch()

        # Create both sourcing/commons and commons/
        sourcing_commons = tmp_path / "sourcing" / "commons"
        sourcing_commons.mkdir(parents=True)
        legacy_commons = tmp_path / "commons"
        legacy_commons.mkdir()

        # Both have all files
        for filename in REQUIRED_INFRASTRUCTURE_FILES:
            (sourcing_commons / filename).touch()
            (legacy_commons / filename).touch()

        result = resolve_commons_source(repo_root=tmp_path)
        # Should choose sourcing/commons (higher priority)
        assert result == sourcing_commons
