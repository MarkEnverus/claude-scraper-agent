"""Repository pattern for file-based persistence.

This module provides a repository for saving and loading Pydantic models
to/from JSON files, with directory management and validation.

Example:
    >>> from pydantic import BaseModel
    >>> from claude_scraper.storage.repository import AnalysisRepository
    >>>
    >>> class DataSourceSpec(BaseModel):
    ...     name: str
    ...     url: str
    >>>
    >>> repo = AnalysisRepository("datasource_analysis")
    >>> spec = DataSourceSpec(name="NYISO", url="https://example.com")
    >>> repo.save("nyiso_spec.json", spec)
    >>> loaded = repo.load("nyiso_spec.json", DataSourceSpec)
"""

import json
import logging
from pathlib import Path
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class AnalysisRepository:
    """Repository for file-based persistence of Pydantic models.

    Provides methods for saving and loading Pydantic models to/from JSON files
    with automatic directory creation and validation.

    Attributes:
        base_dir: Base directory for storing files
        _path: Path object for base directory

    Example:
        >>> repo = AnalysisRepository("datasource_analysis")
        >>> repo.save("spec.json", my_spec_model)
        >>> loaded = repo.load("spec.json", DataSourceSpec)
    """

    def __init__(self, base_dir: str | Path = "datasource_analysis") -> None:
        """Initialize repository with base directory.

        Creates the base directory if it doesn't exist.

        Args:
            base_dir: Base directory path for storing files (string or Path)

        Raises:
            ValueError: If base_dir is empty or invalid
            OSError: If directory creation fails

        Example:
            >>> repo = AnalysisRepository("datasource_analysis")
        """
        # Convert to string if Path provided
        base_dir_str = str(base_dir) if isinstance(base_dir, Path) else base_dir

        if not base_dir_str or not base_dir_str.strip():
            raise ValueError("base_dir cannot be empty")

        # Validate no path traversal
        if ".." in base_dir_str:
            raise ValueError(f"Path traversal detected in base_dir: {base_dir_str}")

        self.base_dir = base_dir_str
        self._path = Path(base_dir_str)

        # Create directory if it doesn't exist
        try:
            self._path.mkdir(parents=True, exist_ok=True)
            logger.debug(
                f"Initialized repository at {self._path.absolute()}",
                extra={"base_dir": base_dir}
            )
        except OSError as e:
            logger.error(
                f"Failed to create repository directory: {e}",
                extra={"base_dir": base_dir},
                exc_info=True
            )
            raise OSError(f"Failed to create directory {base_dir}: {e}") from e

    def save(self, filename: str, data: BaseModel, overwrite: bool = True) -> None:
        """Save Pydantic model to JSON file.

        Serializes the Pydantic model to JSON and writes to file.
        Creates parent directories if needed.

        Args:
            filename: File name (can include subdirectories)
            data: Pydantic model instance to save
            overwrite: If False, raise FileExistsError if file exists (default: True)

        Raises:
            ValueError: If filename is invalid or contains path traversal
            TypeError: If data is not a Pydantic model
            FileExistsError: If file exists and overwrite=False
            OSError: If file write fails

        Example:
            >>> spec = DataSourceSpec(name="NYISO", url="https://example.com")
            >>> repo.save("nyiso_spec.json", spec)
            >>> repo.save("specs/nyiso.json", spec)  # Creates subdirectory
            >>> repo.save("nyiso_spec.json", spec, overwrite=False)  # Raises if exists
        """
        # Validate filename
        if not filename or not filename.strip():
            raise ValueError("filename cannot be empty")

        if ".." in filename:
            raise ValueError(f"Path traversal detected in filename: {filename}")

        # Ensure data is a Pydantic model
        if not isinstance(data, BaseModel):
            raise TypeError(
                f"data must be a Pydantic BaseModel, got {type(data)}"
            )

        # Build full path
        file_path = self._path / filename

        # Check if file exists and overwrite is False
        if not overwrite and file_path.exists():
            raise FileExistsError(
                f"File already exists: {filename} (full path: {file_path.absolute()}). "
                "Use overwrite=True to replace it."
            )

        # Create parent directories if needed
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(
                f"Failed to create parent directories: {e}",
                extra={"file_name": filename},
                exc_info=True
            )
            raise OSError(
                f"Failed to create directories for {filename}: {e}"
            ) from e

        # Serialize to JSON
        try:
            json_data = data.model_dump_json(indent=2)
        except Exception as e:
            logger.error(
                f"Failed to serialize model to JSON: {e}",
                extra={"file_name": filename, "model_type": type(data).__name__},
                exc_info=True
            )
            raise ValueError(f"Failed to serialize model: {e}") from e

        # Write to file
        try:
            file_path.write_text(json_data, encoding="utf-8")
            logger.info(
                f"Saved model to {file_path.absolute()}",
                extra={
                    "file_name": filename,
                    "model_type": type(data).__name__,
                    "size": len(json_data)
                }
            )
        except OSError as e:
            logger.error(
                f"Failed to write file: {e}",
                extra={"file_name": filename},
                exc_info=True
            )
            raise OSError(f"Failed to write {filename}: {e}") from e

    def load(self, filename: str, model_type: Type[T]) -> T:
        """Load JSON file into Pydantic model.

        Reads JSON file and deserializes into the specified Pydantic model type.

        Args:
            filename: File name to load
            model_type: Pydantic model class to deserialize into

        Returns:
            Instance of model_type

        Raises:
            ValueError: If filename is invalid or JSON is invalid
            FileNotFoundError: If file doesn't exist
            ValidationError: If JSON doesn't match model schema

        Example:
            >>> loaded = repo.load("nyiso_spec.json", DataSourceSpec)
            >>> print(loaded.name)
            NYISO
        """
        # Validate filename
        if not filename or not filename.strip():
            raise ValueError("filename cannot be empty")

        if ".." in filename:
            raise ValueError(f"Path traversal detected in filename: {filename}")

        # Build full path
        file_path = self._path / filename

        # Check file exists
        if not file_path.exists():
            raise FileNotFoundError(
                f"File not found: {filename} (full path: {file_path.absolute()})"
            )

        # Read file
        try:
            json_text = file_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.error(
                f"Failed to read file: {e}",
                extra={"file_name": filename},
                exc_info=True
            )
            raise OSError(f"Failed to read {filename}: {e}") from e

        # Parse JSON
        try:
            json_data = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(
                f"Invalid JSON in file: {e}",
                extra={"file_name": filename},
                exc_info=True
            )
            raise ValueError(f"Invalid JSON in {filename}: {e}") from e

        # Deserialize into Pydantic model
        try:
            model = model_type.model_validate(json_data)
            logger.info(
                f"Loaded model from {file_path.absolute()}",
                extra={
                    "file_name": filename,
                    "model_type": model_type.__name__
                }
            )
            return model
        except ValidationError as e:
            logger.error(
                f"Validation error loading model: {e}",
                extra={
                    "file_name": filename,
                    "model_type": model_type.__name__
                },
                exc_info=True
            )
            raise  # Re-raise original exception with full Pydantic validation details

    def exists(self, filename: str) -> bool:
        """Check if file exists in repository.

        Args:
            filename: File name to check

        Returns:
            True if file exists, False otherwise

        Raises:
            ValueError: If filename is invalid

        Example:
            >>> if repo.exists("nyiso_spec.json"):
            ...     print("File exists")
        """
        # Validate filename
        if not filename or not filename.strip():
            raise ValueError("filename cannot be empty")

        if ".." in filename:
            raise ValueError(f"Path traversal detected in filename: {filename}")

        file_path = self._path / filename
        return file_path.exists()

    def delete(self, filename: str) -> bool:
        """Delete file from repository.

        Args:
            filename: File name to delete

        Returns:
            True if file was deleted, False if it didn't exist

        Raises:
            ValueError: If filename is invalid
            OSError: If deletion fails

        Example:
            >>> if repo.delete("nyiso_spec.json"):
            ...     print("File deleted")
        """
        # Validate filename
        if not filename or not filename.strip():
            raise ValueError("filename cannot be empty")

        if ".." in filename:
            raise ValueError(f"Path traversal detected in filename: {filename}")

        file_path = self._path / filename

        if not file_path.exists():
            return False

        try:
            file_path.unlink()
            logger.info(
                f"Deleted file {file_path.absolute()}",
                extra={"file_name": filename}
            )
            return True
        except OSError as e:
            logger.error(
                f"Failed to delete file: {e}",
                extra={"file_name": filename},
                exc_info=True
            )
            raise OSError(f"Failed to delete {filename}: {e}") from e

    def list_files(self, pattern: str = "*.json") -> list[str]:
        """List files in repository matching pattern.

        Args:
            pattern: Glob pattern for file matching (default: "*.json")

        Returns:
            List of relative file paths

        Example:
            >>> files = repo.list_files("*.json")
            >>> print(files)
            ['nyiso_spec.json', 'aeso_spec.json']
        """
        try:
            files = [
                str(p.relative_to(self._path))
                for p in self._path.glob(pattern)
                if p.is_file()
            ]
            return sorted(files)
        except Exception as e:
            logger.error(
                f"Failed to list files: {e}",
                extra={"pattern": pattern},
                exc_info=True
            )
            raise OSError(f"Failed to list files with pattern {pattern}: {e}") from e
