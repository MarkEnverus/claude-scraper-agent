"""WEBSITE P2 Validator - Validation phase for WEBSITE sources.

This node handles Phase 2 validation for WEBSITE-type sources to ensure
discovered data download links are complete and usable.

Key responsibilities:
- Validate count of discovered download links (min threshold)
- Validate URL patterns (file-browser-api + file extensions)
- Validate hierarchy completeness (explored all visible folders)
- Validate URL validity (properly formed download URLs)
- Report gaps if validation fails
- Signal completion if validation passes

Success criteria for SPP-style portals:
- Min 10 download links discovered
- All links have file extensions (.csv, .json, .xml, etc.)
- Reached file hierarchy level
- URLs are properly formatted with query parameters
"""

import logging
from typing import Dict, Any, List
from urllib.parse import urlparse
from agentic_scraper.business_analyst.state import BAAnalystState
from agentic_scraper.business_analyst.utils.url_decoder import is_download_link

logger = logging.getLogger(__name__)


def validate_download_link_count(discovered_links: List[str], min_count: int = 10) -> tuple[bool, str]:
    """Validate that sufficient download links were discovered.

    Args:
        discovered_links: List of discovered data download URLs
        min_count: Minimum required links (default: 10 for SPP-style portals)

    Returns:
        Tuple of (is_valid, message)
    """
    count = len(discovered_links)

    if count >= min_count:
        return True, f"Link count validation passed: {count} links (min: {min_count})"
    else:
        return False, f"Insufficient links: {count} links (min: {min_count})"


def validate_file_extensions(discovered_links: List[str]) -> tuple[bool, str]:
    """Validate that links have proper file extensions.

    Args:
        discovered_links: List of discovered data download URLs

    Returns:
        Tuple of (is_valid, message)
    """
    if not discovered_links:
        return False, "No links to validate"

    # Check that at least 80% have file extensions
    links_with_extensions = sum(1 for link in discovered_links if is_download_link(link))
    percentage = (links_with_extensions / len(discovered_links)) * 100

    if percentage >= 80:
        return True, f"File extension validation passed: {percentage:.1f}% have extensions"
    else:
        return False, f"Too few file extensions: {percentage:.1f}% (min: 80%)"


def validate_hierarchy_completeness(
    hierarchy_level: str,
    folder_paths_visited: set
) -> tuple[bool, str]:
    """Validate that folder hierarchy was explored completely.

    Args:
        hierarchy_level: Current hierarchy level
        folder_paths_visited: Set of visited folder paths

    Returns:
        Tuple of (is_valid, message)
    """
    if hierarchy_level == "file":
        return True, f"Reached file level after exploring {len(folder_paths_visited)} folders"
    else:
        return False, f"Did not reach file level (current: {hierarchy_level})"


def validate_url_format(discovered_links: List[str]) -> tuple[bool, str]:
    """Validate that URLs are properly formatted.

    Checks:
    - URLs have query parameters (for file-browser-api)
    - URLs are parseable
    - URLs have scheme and netloc

    Args:
        discovered_links: List of discovered data download URLs

    Returns:
        Tuple of (is_valid, message)
    """
    if not discovered_links:
        return False, "No links to validate"

    # Check first 5 links (sample)
    sample = discovered_links[:5]
    invalid_count = 0

    for url in sample:
        try:
            parsed = urlparse(url)

            # Check basic URL structure
            if not parsed.scheme or not parsed.netloc:
                invalid_count += 1
                continue

            # Check for query parameters (file-browser-api pattern)
            if 'file-browser-api' in url and not parsed.query:
                invalid_count += 1
                continue

        except Exception as e:
            logger.warning(f"Failed to parse URL {url}: {e}")
            invalid_count += 1

    if invalid_count == 0:
        return True, "URL format validation passed (all sample URLs valid)"
    else:
        return False, f"Invalid URL format: {invalid_count}/{len(sample)} sample URLs failed"


def website_p2_validator(state: BAAnalystState) -> Dict[str, Any]:
    """P2: Validate WEBSITE data link discovery.

    Runs validation checks on discovered download links to ensure
    completeness and usability. Reports gaps if validation fails.

    Args:
        state: Current graph state with discovery results

    Returns:
        State updates with validation results, gaps, and control flow
    """
    logger.info("=== WEBSITE P2 Validator: Validation Phase ===")

    discovered_links = state.get("discovered_data_links", [])
    hierarchy_level = state.get("website_hierarchy_level")
    folder_paths_visited = state.get("folder_paths_visited", set())

    logger.info(
        f"Validating {len(discovered_links)} discovered links, "
        f"hierarchy_level={hierarchy_level}, "
        f"folders_visited={len(folder_paths_visited)}"
    )

    # Run validation checks
    checks = {}
    gaps = []

    # Check 1: Link count
    is_valid, message = validate_download_link_count(discovered_links)
    checks["min_links"] = is_valid
    if not is_valid:
        gaps.append(f"Link count: {message}")
    logger.info(f"Check: Link count - {message}")

    # Check 2: File extensions
    is_valid, message = validate_file_extensions(discovered_links)
    checks["has_file_extensions"] = is_valid
    if not is_valid:
        gaps.append(f"File extensions: {message}")
    logger.info(f"Check: File extensions - {message}")

    # Check 3: Hierarchy completeness
    is_valid, message = validate_hierarchy_completeness(hierarchy_level, folder_paths_visited)
    checks["reached_file_level"] = is_valid
    if not is_valid:
        gaps.append(f"Hierarchy: {message}")
    logger.info(f"Check: Hierarchy - {message}")

    # Check 4: URL format
    is_valid, message = validate_url_format(discovered_links)
    checks["proper_url_format"] = is_valid
    if not is_valid:
        gaps.append(f"URL format: {message}")
    logger.info(f"Check: URL format - {message}")

    # Overall validation result
    all_checks_passed = all(checks.values())

    if all_checks_passed:
        logger.info(
            f"✅ WEBSITE P2 validation PASSED: {len(discovered_links)} download links discovered"
        )
        return {
            "next_action": "stop",
            "stop_reason": f"WEBSITE data discovery complete: {len(discovered_links)} download links validated",
            "p2_complete": True,
            "gaps": []  # Clear any previous gaps
        }
    else:
        failed_checks = [name for name, passed in checks.items() if not passed]
        logger.warning(
            f"❌ WEBSITE P2 validation FAILED: {len(failed_checks)} checks failed: {failed_checks}"
        )
        return {
            "next_action": "continue",  # Return to planner to continue exploration
            "gaps": gaps,
            "p2_complete": False
        }


# Export
__all__ = ["website_p2_validator"]
