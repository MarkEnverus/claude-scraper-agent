"""URL decoding utilities for WEBSITE sources (file-browser-api pattern extraction).

This module provides functions to decode file-browser-api URLs with encoded
query parameters and extract meaningful path components for folder navigation.

Critical for SPP portal pattern where download links use encoded paths:
https://portal.spp.org/file-browser-api/download/da-lmp-by-bus?path=%2F2026%2F01%2FBy_Day%2FDA-LMP-B-202601040100.csv

Decoded: /2026/01/By_Day/DA-LMP-B-202601040100.csv
"""

import logging
import re
from typing import List, Optional
from urllib.parse import urlparse, parse_qs, unquote
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DecodedFileBrowserURL:
    """Decoded file-browser-api URL components."""
    base_url: str  # https://portal.spp.org/file-browser-api/download/da-lmp-by-bus
    fs_name: str  # Filesystem name (e.g., "da-lmp-by-bus")
    path: str  # Decoded path (/2026/01/By_Day/DA-LMP-B-202601040100.csv)
    path_segments: List[str]  # ["2026", "01", "By_Day", "DA-LMP-B-202601040100.csv"]
    full_url: str  # Original full URL
    is_file: bool  # True if path ends with file extension
    is_folder: bool  # True if path is a folder (no file extension)


def decode_file_browser_api_url(url: str) -> Optional[DecodedFileBrowserURL]:
    """Decode file-browser-api URL into components.

    Parses URLs like:
    https://portal.spp.org/file-browser-api/download/da-lmp-by-bus?path=%2F2026%2F01%2FBy_Day%2FDA-LMP-B-202601040100.csv

    Into components:
    - base_url: https://portal.spp.org/file-browser-api/download/da-lmp-by-bus
    - fs_name: da-lmp-by-bus
    - path: /2026/01/By_Day/DA-LMP-B-202601040100.csv (decoded)
    - path_segments: ["2026", "01", "By_Day", "DA-LMP-B-202601040100.csv"]

    Args:
        url: File-browser-api URL to decode

    Returns:
        DecodedFileBrowserURL with components, or None if not a file-browser-api URL

    Example:
        >>> decoded = decode_file_browser_api_url(
        ...     "https://portal.spp.org/file-browser-api/download/da-lmp-by-bus?path=%2F2026%2F01%2FBy_Day%2FDA-LMP-B-202601040100.csv"
        ... )
        >>> decoded.path
        '/2026/01/By_Day/DA-LMP-B-202601040100.csv'
        >>> decoded.path_segments
        ['2026', '01', 'By_Day', 'DA-LMP-B-202601040100.csv']
    """
    # Check if URL matches file-browser-api pattern
    if 'file-browser-api' not in url:
        return None

    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Extract base URL (everything before query string)
        base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        # Extract filesystem name from path (last segment before query)
        # /file-browser-api/download/da-lmp-by-bus → da-lmp-by-bus
        path_parts = parsed.path.rstrip('/').split('/')
        fs_name = path_parts[-1] if path_parts else ""

        # Decode path parameter (%2F → /)
        encoded_path = params.get("path", [""])[0]
        decoded_path = unquote(encoded_path)

        # Split into segments (remove empty strings from leading slash)
        path_segments = [seg for seg in decoded_path.split('/') if seg]

        # Determine if this is a file or folder
        # File: has extension like .csv, .json, .xml
        # Folder: no extension or ends with /
        is_file = bool(path_segments and '.' in path_segments[-1])
        is_folder = not is_file

        result = DecodedFileBrowserURL(
            base_url=base_url,
            fs_name=fs_name,
            path=decoded_path,
            path_segments=path_segments,
            full_url=url,
            is_file=is_file,
            is_folder=is_folder
        )

        logger.debug(
            f"Decoded file-browser URL: fs_name={fs_name}, "
            f"path={decoded_path}, is_file={is_file}"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to decode file-browser URL {url}: {e}", exc_info=True)
        return None


def extract_file_browser_urls(network_calls: List[str], links: List[str]) -> List[str]:
    """Extract file-browser-api URLs from network calls and links.

    Filters URLs matching the file-browser-api pattern from multiple sources.
    Deduplicates and returns unique file-browser URLs.

    Args:
        network_calls: List of network call URLs
        links: List of navigation link URLs

    Returns:
        Deduplicated list of file-browser-api URLs

    Example:
        >>> network_calls = [
        ...     "https://portal.spp.org/file-browser-api/download/da-lmp-by-bus?path=%2F2026",
        ...     "https://portal.spp.org/api/login",
        ...     "https://portal.spp.org/file-browser-api/download/da-mcp?path=%2F2026"
        ... ]
        >>> extract_file_browser_urls(network_calls, [])
        ['https://portal.spp.org/file-browser-api/download/da-lmp-by-bus?path=%2F2026', ...]
    """
    pattern = re.compile(r'file-browser-api')
    candidates = []

    # Check network calls
    for url in network_calls:
        if pattern.search(url):
            candidates.append(url)

    # Check links
    for url in links:
        if pattern.search(url):
            candidates.append(url)

    # Deduplicate while preserving order
    unique_urls = list(dict.fromkeys(candidates))

    logger.info(
        f"Extracted {len(unique_urls)} file-browser-api URLs from "
        f"{len(network_calls)} network calls and {len(links)} links"
    )

    return unique_urls


def is_download_link(url: str) -> bool:
    """Check if URL is a file download link.

    Detects common download link patterns:
    - file-browser-api with file extensions (.csv, .json, .xml, .xlsx)
    - /download/ in path
    - /export/ in path
    - /data/ with file extensions

    Args:
        url: URL to check

    Returns:
        True if URL appears to be a download link

    Example:
        >>> is_download_link("https://portal.spp.org/file-browser-api/download/da-lmp-by-bus?path=%2FDA-LMP-B.csv")
        True
        >>> is_download_link("https://portal.spp.org/pages/da-lmp-by-bus")
        False
    """
    url_lower = url.lower()

    # Check for file extensions
    file_extensions = ['.csv', '.json', '.xml', '.xlsx', '.xls', '.txt', '.zip']
    if any(url_lower.endswith(ext) for ext in file_extensions):
        return True

    # Check for download/export patterns
    download_patterns = ['/download', '/export', '/file-browser-api']
    if any(pattern in url_lower for pattern in download_patterns):
        # Additional check: if file-browser-api, must have path param
        if 'file-browser-api' in url_lower:
            return 'path=' in url_lower
        return True

    return False


def get_parent_folder_url(decoded_url: DecodedFileBrowserURL) -> Optional[str]:
    """Get parent folder URL from decoded file-browser URL.

    Constructs the parent folder URL by removing the last path segment.
    Useful for navigating up the folder hierarchy.

    Args:
        decoded_url: Decoded file-browser URL

    Returns:
        Parent folder URL, or None if already at root

    Example:
        >>> decoded = decode_file_browser_api_url(
        ...     "https://portal.spp.org/file-browser-api/download/da-lmp-by-bus?path=%2F2026%2F01%2FBy_Day"
        ... )
        >>> get_parent_folder_url(decoded)
        'https://portal.spp.org/file-browser-api/download/da-lmp-by-bus?path=%2F2026%2F01'
    """
    if not decoded_url.path_segments:
        # Already at root
        return None

    # Remove last segment
    parent_segments = decoded_url.path_segments[:-1]

    if not parent_segments:
        # Parent is root
        parent_path = "/"
    else:
        parent_path = "/" + "/".join(parent_segments)

    # Encode the path for URL
    from urllib.parse import quote
    encoded_parent_path = quote(parent_path, safe='/')

    parent_url = f"{decoded_url.base_url}?path={encoded_parent_path}"

    logger.debug(f"Parent folder URL: {parent_url}")

    return parent_url


# Export public API
__all__ = [
    'DecodedFileBrowserURL',
    'decode_file_browser_api_url',
    'extract_file_browser_urls',
    'is_download_link',
    'get_parent_folder_url',
]
