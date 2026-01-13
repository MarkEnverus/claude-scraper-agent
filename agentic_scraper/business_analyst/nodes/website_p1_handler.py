"""WEBSITE P1 Handler - Discovery phase for WEBSITE sources.

This node handles Phase 1 discovery for WEBSITE-type sources (e.g., SPP portal)
where data is accessed through hierarchical folder structures with file downloads.

Key responsibilities:
- Extract file-browser-api URLs from artifacts (network calls, links)
- Decode query parameters (%2F → /)
- Navigate folder hierarchies to discover file download links
- Identify hierarchy level (portal/category/folder/file)
- Stop when file-level reached (data download links discovered)

Example flow for SPP portal:
1. Portal page: https://portal.spp.org/pages/da-lmp-by-bus
2. Extract network calls: file-browser-api URLs with encoded paths
3. Decode: path=%2F2026%2F01%2FBy_Day → /2026/01/By_Day
4. Navigate folders until file level reached
5. Collect download links: https://portal.spp.org/file-browser-api/download/...?path=.../file.csv
"""

import logging
from typing import Dict, Any, List
from agentic_scraper.business_analyst.state import BAAnalystState
from agentic_scraper.business_analyst.utils.url_decoder import (
    extract_file_browser_urls,
    decode_file_browser_api_url,
    is_download_link
)
from agentic_scraper.business_analyst.utils.api_call_extractor import is_file_browser_api

logger = logging.getLogger(__name__)


def detect_hierarchy_level(
    url: str,
    artifact: Any,
    browser_api_urls: List[str]
) -> str:
    """Detect hierarchy level of current URL.

    Hierarchy levels for WEBSITE sources:
    - portal: Top-level entry page (e.g., /pages/da-lmp-by-bus)
    - category: Category/dataset page with multiple folders
    - folder: Folder page with subfolders or files
    - file: File-level page with direct download links

    Detection logic:
    - If browser_api_urls contain file extensions (.csv, .json) → file level
    - If browser_api_urls are all folders (no extensions) → folder level
    - If page has many navigation links but few browser_api_urls → category level
    - Default: portal level

    Args:
        url: Current URL
        artifact: Page artifact with links and network calls
        browser_api_urls: Extracted file-browser-api URLs

    Returns:
        Hierarchy level: "portal", "category", "folder", or "file"
    """
    if not browser_api_urls:
        # No file-browser URLs yet → portal or category level
        return "portal"

    # Check if any browser_api_urls are files (have extensions)
    file_count = sum(1 for u in browser_api_urls if is_download_link(u))

    if file_count > 0:
        # Has direct download links → file level
        logger.info(f"Detected file level: {file_count} download links found")
        return "file"
    else:
        # Only folders → folder or category level
        if len(browser_api_urls) > 10:
            return "category"  # Many folders → category level
        else:
            return "folder"  # Few folders → folder level


def select_next_folder(
    browser_api_urls: List[str],
    visited_folders: set
) -> str:
    """Select next folder to navigate into.

    Prioritizes:
    1. Unvisited folders
    2. Recent folders (by path depth and date patterns)

    Args:
        browser_api_urls: List of file-browser-api URLs
        visited_folders: Set of already visited folder paths

    Returns:
        Next folder URL to visit, or empty string if none available
    """
    # Filter out already visited
    unvisited = [url for url in browser_api_urls if url not in visited_folders]

    if not unvisited:
        logger.warning("No unvisited folders available")
        return ""

    # Decode URLs and prioritize by path depth (deeper = more specific)
    decoded_urls = []
    for url in unvisited:
        decoded = decode_file_browser_api_url(url)
        if decoded and decoded.is_folder:
            decoded_urls.append((url, len(decoded.path_segments)))

    if not decoded_urls:
        # No folders found, return first unvisited URL
        return unvisited[0]

    # Sort by depth (deeper first)
    decoded_urls.sort(key=lambda x: x[1], reverse=True)

    selected_url = decoded_urls[0][0]
    logger.info(f"Selected next folder: {selected_url}")

    return selected_url


def website_p1_handler(state: BAAnalystState) -> Dict[str, Any]:
    """P1: Discover data download links from WEBSITE sources.

    Handles hierarchical folder navigation to extract file-browser-api
    download URLs. Stops when file-level reached with sufficient download links.

    Args:
        state: Current graph state with artifacts

    Returns:
        State updates with discovered_data_links, hierarchy_level, and control flow
    """
    logger.info("=== WEBSITE P1 Handler: Discovery Phase ===")

    # P1/P2 Bug #2 fix: Use last_analyzed_url instead of current_url
    last_analyzed_url = state.get("last_analyzed_url")
    artifacts = state.get("artifacts", {})

    if not last_analyzed_url or last_analyzed_url not in artifacts:
        logger.error(f"No artifact found for last_analyzed_url: {last_analyzed_url}")
        return {
            "p1_complete": False,
            "next_action": "continue",
            "gaps": ["WEBSITE P1: No artifact available for analysis"]
        }

    artifact = artifacts[last_analyzed_url]

    # Extract file-browser-api URLs from network calls and links
    network_calls = artifact.network_calls
    navigation_links = [link.url for link in artifact.links]

    browser_api_urls = extract_file_browser_urls(network_calls, navigation_links)

    logger.info(f"Extracted {len(browser_api_urls)} file-browser-api URLs")

    if not browser_api_urls:
        logger.warning("No file-browser-api URLs found - may not be a file-browser portal")
        return {
            "p1_complete": False,
            "next_action": "continue",
            "gaps": ["WEBSITE P1: No file-browser-api URLs detected"]
        }

    # Determine hierarchy level
    hierarchy_level = detect_hierarchy_level(last_analyzed_url, artifact, browser_api_urls)

    logger.info(f"Detected hierarchy level: {hierarchy_level}")

    # Navigate deeper if not at file level
    if hierarchy_level in ["portal", "category", "folder"]:
        # Select next folder to navigate
        visited_folders = state.get("folder_paths_visited", set())
        next_folder_url = select_next_folder(browser_api_urls, visited_folders)

        if next_folder_url:
            logger.info(f"Adding next folder to queue: {next_folder_url}")

            # Add folder URL to queue for planner to explore
            queue = state.get("queue", [])
            queue_entry = {
                "url": next_folder_url,
                "score": 0.9,  # High priority for folder navigation
                "reason": f"WEBSITE P1: Folder navigation at {hierarchy_level} level"
            }

            return {
                "queue": queue + [queue_entry],
                "website_hierarchy_level": hierarchy_level,
                "folder_paths_visited": visited_folders | {next_folder_url},
                "p1_complete": False,  # Not done yet, keep exploring
                "next_action": "continue"  # Return to planner to fetch from queue
            }
        else:
            # No more folders to explore, use what we have
            logger.warning("No more folders to explore, proceeding with current data")

    # File level reached - extract download links
    data_links = [url for url in browser_api_urls if is_download_link(url)]

    # Decode URLs for better readability
    decoded_links = []
    for url in data_links:
        decoded = decode_file_browser_api_url(url)
        if decoded:
            decoded_links.append(decoded.full_url)
        else:
            decoded_links.append(url)

    logger.info(f"Discovered {len(decoded_links)} data download links at file level")

    return {
        "discovered_data_links": decoded_links,
        "website_hierarchy_level": "file",
        "p1_complete": True,
        "next_action": "continue"  # Move to P2 validation
    }


# Export
__all__ = ["website_p1_handler"]
