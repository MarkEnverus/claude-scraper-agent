"""Tests for repository pattern implementation.

Tests file-based persistence with Pydantic models, including
save, load, exists, delete, and error handling.
"""

import pytest
import tempfile
from pathlib import Path
from pydantic import BaseModel, ValidationError
from claude_scraper.storage import AnalysisRepository


class TestModel(BaseModel):
    """Test Pydantic model for repository tests."""
    name: str
    value: int


class TestAnalysisRepository:
    """Test AnalysisRepository."""

    def test_init_creates_directory(self):
        """Test that repository creates base directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "test_repo"
            repo = AnalysisRepository(str(test_dir))

            assert test_dir.exists()
            assert test_dir.is_dir()

    def test_init_validates_base_dir(self):
        """Test that empty base_dir raises ValueError."""
        with pytest.raises(ValueError, match="base_dir cannot be empty"):
            AnalysisRepository("")

    def test_init_rejects_path_traversal(self):
        """Test that path traversal in base_dir raises ValueError."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            AnalysisRepository("../malicious")

    def test_save_creates_file(self):
        """Test that save creates JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)
            model = TestModel(name="test", value=42)

            repo.save("test.json", model)

            file_path = Path(tmpdir) / "test.json"
            assert file_path.exists()

    def test_save_rejects_path_traversal_attack(self):
        """Test that save() prevents path traversal attacks attempting to write outside repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)
            model = TestModel(name="malicious", value=999)

            # Test various path traversal patterns
            traversal_patterns = [
                "../../../etc/passwd",
                "../../malicious.json",
                "subdir/../../malicious.json",
                "../outside.json"
            ]

            for pattern in traversal_patterns:
                with pytest.raises(ValueError, match="Path traversal detected"):
                    repo.save(pattern, model)

    def test_save_creates_subdirectories(self):
        """Test that save creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)
            model = TestModel(name="test", value=42)

            repo.save("subdir/test.json", model)

            file_path = Path(tmpdir) / "subdir" / "test.json"
            assert file_path.exists()

    def test_save_validates_filename(self):
        """Test that save rejects invalid filenames."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)
            model = TestModel(name="test", value=42)

            # Empty filename
            with pytest.raises(ValueError, match="filename cannot be empty"):
                repo.save("", model)

            # Path traversal
            with pytest.raises(ValueError, match="Path traversal detected"):
                repo.save("../malicious.json", model)

    def test_save_validates_model_type(self):
        """Test that save rejects non-Pydantic models."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)

            with pytest.raises(TypeError, match="must be a Pydantic BaseModel"):
                repo.save("test.json", {"not": "pydantic"})

    def test_load_reads_file(self):
        """Test that load reads and deserializes JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)
            original = TestModel(name="test", value=42)

            repo.save("test.json", original)
            loaded = repo.load("test.json", TestModel)

            assert loaded.name == "test"
            assert loaded.value == 42

    def test_load_validates_filename(self):
        """Test that load rejects invalid filenames."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)

            # Empty filename
            with pytest.raises(ValueError, match="filename cannot be empty"):
                repo.load("", TestModel)

            # Path traversal
            with pytest.raises(ValueError, match="Path traversal detected"):
                repo.load("../malicious.json", TestModel)

    def test_load_raises_on_missing_file(self):
        """Test that load raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)

            with pytest.raises(FileNotFoundError, match="File not found"):
                repo.load("missing.json", TestModel)

    def test_load_raises_on_invalid_json(self):
        """Test that load raises on invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)

            # Write invalid JSON
            file_path = Path(tmpdir) / "invalid.json"
            file_path.write_text("not json", encoding="utf-8")

            with pytest.raises(ValueError, match="Invalid JSON"):
                repo.load("invalid.json", TestModel)

    def test_load_raises_on_validation_error(self):
        """Test that load raises on Pydantic validation error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)

            # Write JSON that doesn't match schema
            file_path = Path(tmpdir) / "bad_schema.json"
            file_path.write_text('{"wrong": "schema"}', encoding="utf-8")

            with pytest.raises(ValidationError):
                repo.load("bad_schema.json", TestModel)

    def test_load_propagates_pydantic_validation_details(self):
        """Test that ValidationError preserves full Pydantic validation details."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)

            # Write JSON with wrong field types
            file_path = Path(tmpdir) / "bad_types.json"
            file_path.write_text('{"name": "test", "value": "not_an_int"}', encoding="utf-8")

            with pytest.raises(ValidationError) as exc_info:
                repo.load("bad_types.json", TestModel)

            # Verify we get the original Pydantic ValidationError with full details
            validation_error = exc_info.value
            assert len(validation_error.errors()) > 0
            assert "value" in str(validation_error)
            assert "int" in str(validation_error).lower()

    def test_exists_returns_true_for_existing_file(self):
        """Test that exists returns True for existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)
            model = TestModel(name="test", value=42)

            repo.save("test.json", model)

            assert repo.exists("test.json") is True

    def test_exists_returns_false_for_missing_file(self):
        """Test that exists returns False for missing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)

            assert repo.exists("missing.json") is False

    def test_delete_removes_file(self):
        """Test that delete removes file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)
            model = TestModel(name="test", value=42)

            repo.save("test.json", model)
            assert repo.exists("test.json") is True

            result = repo.delete("test.json")

            assert result is True
            assert repo.exists("test.json") is False

    def test_delete_returns_false_for_missing_file(self):
        """Test that delete returns False for missing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)

            result = repo.delete("missing.json")

            assert result is False

    def test_list_files_returns_json_files(self):
        """Test that list_files returns JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)
            model = TestModel(name="test", value=42)

            repo.save("file1.json", model)
            repo.save("file2.json", model)
            repo.save("subdir/file3.json", model)

            files = repo.list_files("*.json")

            assert "file1.json" in files
            assert "file2.json" in files
            assert len([f for f in files if "file" in f]) >= 2

    def test_list_files_respects_pattern(self):
        """Test that list_files respects glob pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)
            model = TestModel(name="test", value=42)

            repo.save("spec.json", model)
            repo.save("data.json", model)

            # Only list spec files
            spec_files = repo.list_files("spec*.json")

            assert any("spec" in f for f in spec_files)
