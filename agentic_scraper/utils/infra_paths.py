"""Infrastructure path resolution utilities.

Resolves commons infrastructure directory across different project layouts:
- Monorepo: sourcing/commons/ or sourcing/scraping/commons/
- Standalone: commons/
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Required infrastructure files
REQUIRED_INFRASTRUCTURE_FILES = [
    "collection_framework.py",
    "s3_utils.py",
    "kafka_utils.py",
    "hash_registry.py",
    "logging_json.py",
]


def find_repo_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find repository root by walking up directory tree.

    Looks for marker files:
    - pyproject.toml (Python project root)
    - .git (Git repository root)

    Args:
        start_path: Starting directory (default: current working directory)

    Returns:
        Path to repository root, or None if not found

    Example:
        >>> root = find_repo_root()
        >>> print(root)  # /Users/mark.johnson/.../claude_scraper_agent
    """
    current = (start_path or Path.cwd()).resolve()

    # Limit walk to 10 levels to prevent infinite loops
    for _ in range(10):
        # Check for repo markers
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            logger.debug(f"Found repo root at {current}")
            return current

        # Move up one level
        parent = current.parent
        if parent == current:  # Reached filesystem root
            logger.debug("Reached filesystem root without finding repo markers")
            break
        current = parent

    logger.warning("Could not find repository root (no pyproject.toml or .git found)")
    return None


def validate_commons_directory(commons_path: Path) -> tuple[bool, list[str]]:
    """Validate that all required infrastructure files exist in commons directory.

    Args:
        commons_path: Path to commons directory to validate

    Returns:
        Tuple of (is_valid, missing_files)
        - is_valid: True if all files exist, False otherwise
        - missing_files: List of missing filenames (empty if is_valid=True)
    """
    if not commons_path.exists():
        return False, list(REQUIRED_INFRASTRUCTURE_FILES)

    missing = []
    for filename in REQUIRED_INFRASTRUCTURE_FILES:
        if not (commons_path / filename).exists():
            missing.append(filename)

    return len(missing) == 0, missing


def resolve_commons_source(repo_root: Optional[Path] = None) -> Path:
    """Resolve commons infrastructure source directory.

    Search order (relative to repo_root):
    1. sourcing/commons/ (current standard location)
    2. sourcing/scraping/commons/ (legacy monorepo location)
    3. commons/ (legacy standalone location)

    Args:
        repo_root: Repository root path (default: auto-detect from CWD)

    Returns:
        Absolute path to commons directory with all required files

    Raises:
        FileNotFoundError: If commons directory not found or missing required files

    Example:
        >>> commons = resolve_commons_source()
        >>> print(commons)  # /Users/.../claude_scraper_agent/sourcing/commons
    """
    # Auto-detect repo root if not provided
    if repo_root is None:
        repo_root = find_repo_root()
        if repo_root is None:
            # Fallback: use CWD as repo root
            repo_root = Path.cwd().resolve()
            logger.warning(f"Could not detect repo root, using CWD: {repo_root}")
    else:
        repo_root = repo_root.resolve()

    # Search paths in priority order
    search_paths = [
        repo_root / "sourcing" / "commons",
        repo_root / "sourcing" / "scraping" / "commons",
        repo_root / "commons",
    ]

    # Track validation results for error reporting
    check_results = []

    for path in search_paths:
        is_valid, missing_files = validate_commons_directory(path)

        if is_valid:
            logger.info(f"Found valid commons infrastructure at {path}")
            return path

        # Record result for error message
        if path.exists():
            check_results.append(f"  - {path} (missing files: {', '.join(missing_files)})")
        else:
            check_results.append(f"  - {path} (directory not found)")

    # Not found - raise detailed error
    error_msg = (
        f"Infrastructure commons not found. Checked paths:\n"
        f"{chr(10).join(check_results)}\n\n"
        f"Required files:\n"
        f"{chr(10).join(f'  - {f}' for f in REQUIRED_INFRASTRUCTURE_FILES)}\n\n"
        f"Repository root detected: {repo_root}"
    )
    raise FileNotFoundError(error_msg)
