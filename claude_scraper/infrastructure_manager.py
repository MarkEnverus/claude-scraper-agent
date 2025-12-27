"""Infrastructure management for scraper generation and updates.

This module provides utilities to:
- Bundle infrastructure files into generated scrapers
- Copy infrastructure for monorepo updates
- Validate infrastructure versions
- Generate project configuration files
"""

import shutil
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Current infrastructure version
INFRASTRUCTURE_VERSION = "1.6.0"

# All infrastructure files (consolidated into single directory)
ALL_INFRASTRUCTURE_FILES = [
    "collection_framework.py",
    "s3_utils.py",
    "kafka_utils.py",
    "hash_registry.py",
    "logging_json.py",
]


class InfrastructureManager:
    """Manage infrastructure bundling and copying for scrapers."""

    def __init__(self, infrastructure_source: Optional[Path] = None):
        """Initialize infrastructure manager.

        Args:
            infrastructure_source: Path to source infrastructure files
                (default: ./commons/ relative to project root)
        """
        self.source = infrastructure_source or Path("commons")

        if not self.source.exists():
            raise FileNotFoundError(
                f"Infrastructure source not found: {self.source}\n"
                f"Expected directory with files: {', '.join(ALL_INFRASTRUCTURE_FILES)}"
            )

        logger.info(f"Initialized InfrastructureManager: source={self.source}")

    def bundle_for_scraper(self, output_dir: Path) -> bool:
        """Bundle infrastructure into a generated scraper directory.

        Creates structure:
            output_dir/
            └── infrastructure/
                ├── __init__.py
                ├── collection_framework.py
                ├── s3_utils.py
                ├── kafka_utils.py
                ├── hash_registry.py
                └── logging_json.py

        Args:
            output_dir: Root directory for generated scraper

        Returns:
            True if successful, False otherwise
        """
        infra_dir = output_dir / "infrastructure"
        copied_files: list[Path] = []

        try:
            # Create infrastructure directory
            infra_dir.mkdir(parents=True, exist_ok=True)

            # Copy all infrastructure files with rollback tracking
            files_copied = 0
            for filename in ALL_INFRASTRUCTURE_FILES:
                src = self.source / filename
                dst = infra_dir / filename

                if not src.exists():
                    logger.warning(f"Infrastructure file missing: {filename}")
                    continue

                shutil.copy2(src, dst)
                copied_files.append(dst)
                logger.debug(f"Copied {filename} → {infra_dir}")
                files_copied += 1

            # Add __init__.py to make it a package
            init_file = infra_dir / "__init__.py"
            init_file.touch()
            copied_files.append(init_file)

            if files_copied == 0:
                logger.error("No infrastructure files were copied")
                return False

            logger.info(
                f"✓ Infrastructure bundled to {output_dir} "
                f"({files_copied}/{len(ALL_INFRASTRUCTURE_FILES)} files, v{INFRASTRUCTURE_VERSION})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to bundle infrastructure: {e}")
            # Rollback: remove any files that were copied
            for copied_file in copied_files:
                try:
                    copied_file.unlink()
                    logger.debug(f"Rolled back: {copied_file}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to rollback {copied_file}: {cleanup_error}")
            return False

    def copy_for_monorepo(self, monorepo_root: Path) -> bool:
        """Copy infrastructure to existing monorepo (gold standard).

        Assumes monorepo structure:
            monorepo_root/
            └── scraping/
                ├── commons/  ← Infrastructure goes here (gold standard)
                └── {sources}/

        This method follows the "gold standard" pattern:
        - Always overwrites existing infrastructure files
        - Ensures infrastructure version matches INFRASTRUCTURE_VERSION
        - No version checks - infrastructure IS the truth

        Args:
            monorepo_root: Root directory of monorepo (e.g., sourcing/)

        Returns:
            True if successful, False otherwise
        """
        commons_dir = monorepo_root / "scraping" / "commons"
        copied_files: list[Path] = []
        backup_files: list[tuple[Path, Path]] = []

        try:
            # Target directory for monorepo (uses commons/ for compatibility)
            commons_dir.mkdir(parents=True, exist_ok=True)

            # Copy all files (OVERWRITE - gold standard) with backup tracking
            files_copied = 0
            for filename in ALL_INFRASTRUCTURE_FILES:
                src = self.source / filename
                dst = commons_dir / filename

                if not src.exists():
                    logger.warning(f"Infrastructure file missing: {filename}")
                    continue

                # Backup existing file if it exists (for gold standard overwrite)
                if dst.exists():
                    backup_path = dst.with_suffix(dst.suffix + ".backup")
                    shutil.copy2(dst, backup_path)
                    backup_files.append((dst, backup_path))

                shutil.copy2(src, dst)
                copied_files.append(dst)
                logger.debug(f"Copied {filename} → {commons_dir}")
                files_copied += 1

            # Add __init__.py
            init_file = commons_dir / "__init__.py"
            init_file.touch()
            copied_files.append(init_file)

            # Clean up backup files after successful copy
            for _, backup_path in backup_files:
                try:
                    backup_path.unlink()
                except Exception:
                    pass

            if files_copied == 0:
                logger.error("No infrastructure files were copied")
                return False

            logger.info(
                f"✓ Infrastructure copied to {monorepo_root} "
                f"({files_copied}/{len(ALL_INFRASTRUCTURE_FILES)} files, v{INFRASTRUCTURE_VERSION})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to copy infrastructure: {e}")
            # Rollback: restore from backups
            for dst, backup_path in backup_files:
                try:
                    if backup_path.exists():
                        shutil.copy2(backup_path, dst)
                        backup_path.unlink()
                        logger.debug(f"Restored backup: {dst}")
                except Exception as restore_error:
                    logger.warning(f"Failed to restore backup {dst}: {restore_error}")
            return False

    def generate_pyproject_toml(self, output_dir: Path, source_name: str) -> bool:
        """Generate pyproject.toml from template.

        Args:
            output_dir: Directory to create pyproject.toml
            source_name: Name of data source (for metadata)

        Returns:
            True if successful, False otherwise
        """
        template_path = self.source / "pyproject.toml.template"

        if not template_path.exists():
            logger.warning("pyproject.toml.template not found, skipping")
            return False

        try:
            # Sanitize source_name to prevent path traversal and special characters
            safe_source_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', source_name)

            template = template_path.read_text()

            # Basic substitution (can be enhanced with Jinja2 if needed)
            rendered = template.replace("{{SOURCE_NAME}}", safe_source_name)
            rendered = rendered.replace("{{INFRASTRUCTURE_VERSION}}", INFRASTRUCTURE_VERSION)

            output_path = output_dir / "pyproject.toml"
            output_path.write_text(rendered)

            logger.info(f"✓ Generated pyproject.toml for {safe_source_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to generate pyproject.toml: {e}")
            return False

    def generate_gitignore(self, output_dir: Path) -> bool:
        """Generate .gitignore for Python projects.

        Args:
            output_dir: Directory to create .gitignore

        Returns:
            True if successful
        """
        gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
.venv/
venv/
ENV/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Environment
.env
.env.local

# OS
.DS_Store
Thumbs.db
"""
        try:
            output_path = output_dir / ".gitignore"
            output_path.write_text(gitignore_content)
            logger.info("✓ Generated .gitignore")
            return True

        except Exception as e:
            logger.error(f"Failed to generate .gitignore: {e}")
            return False

    def validate_infrastructure_exists(self, directory: Path) -> bool:
        """Check if infrastructure files exist in given directory.

        Args:
            directory: Directory to check for infrastructure files

        Returns:
            True if all infrastructure files exist, False otherwise
        """
        infra_dir = directory / "infrastructure"
        if not infra_dir.exists():
            return False

        missing_files = []
        for filename in ALL_INFRASTRUCTURE_FILES:
            if not (infra_dir / filename).exists():
                missing_files.append(filename)

        if missing_files:
            logger.warning(f"Infrastructure incomplete, missing: {', '.join(missing_files)}")
            return False

        return True
