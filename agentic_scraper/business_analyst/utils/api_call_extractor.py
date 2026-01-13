"""API call extraction from network_calls for BA Analyst.

This module provides functions to identify likely API endpoints from captured
network calls (XHR/Fetch). This is critical for APIM-style portals like MISO
where real API endpoints are only visible in network traffic, not in page links.
"""

import logging
from typing import List, Set
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# API-relevant path patterns that indicate likely API endpoints
API_PATH_PATTERNS = {
    '/developer/apis/',
    '/operations',
    '/schemas',
    '/api/',
    '/v1/',
    '/v2/',
    '/v3/',
    'openapi',
    'swagger',
    '/endpoints',
    '/resources',
    '/rest/',
    '/graphql',
}

# File-browser-api patterns (WEBSITE sources like SPP portal)
FILE_BROWSER_PATTERNS = {
    '/file-browser-api/',
    '/file-browser-api/download/',
    '/files-api/',
    '/data-browser/',
}

# OpenAPI/Swagger spec patterns (API sources)
OPENAPI_SPEC_PATTERNS = {
    '/openapi.json',
    '/swagger.json',
    '/api-docs',
    '/openapi',
    '/swagger',
    '/api/spec',
}

# APIM-specific patterns (Microsoft Azure API Management / similar)
APIM_PRIORITY_PATTERNS = {
    '/developer/apis/',  # APIM developer portal
    '/operations',       # Operation listing
    '/hostnames',        # Base host info
    '/schemas',          # Schema definitions
}

# Static asset patterns to exclude
STATIC_ASSET_PATTERNS = {
    '.css', '.js', '.woff', '.woff2', '.ttf', '.eot',
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
    '.mp4', '.webm', '.mp3', '.wav',
    '.pdf', '.zip', '.tar', '.gz',
}

# Auth/login patterns to exclude (not data endpoints)
AUTH_PATTERNS = {
    '/login', '/signin', '/logout', '/auth',
    '/oauth', '/token', '/refresh', '/signup',
}

# Policy/documentation pages to exclude (Stage 1 pre-filter)
POLICY_PATTERNS = {
    '/terms', '/privacy', '/sitemap', '/about', '/contact',
    '/help', '/faq', '/support', '/cookies', '/legal',
}

# Portal navigation pages to exclude (Stage 1 pre-filter)
PORTAL_NAV_PATTERNS = {
    '/apis', '/products', '/resources', '/developer',
    '/documentation', '/guides', '/tutorials', '/home',
}

# System/monitoring endpoints to exclude (Stage 1 pre-filter)
SYSTEM_PATTERNS = {
    '/health', '/status', '/ping', '/metrics',
    '/trace', '/config', '/version', '/info',
}


def is_static_asset(url: str) -> bool:
    """Check if URL is a static asset (should be filtered)."""
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in STATIC_ASSET_PATTERNS)


def is_auth_endpoint(url: str) -> bool:
    """Check if URL is an auth/login endpoint (should be filtered)."""
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in AUTH_PATTERNS)


def is_policy_page(url: str) -> bool:
    """Check if URL matches policy/documentation patterns (Stage 1 pre-filter).

    Args:
        url: URL to check

    Returns:
        True if URL matches policy patterns (/terms, /privacy, etc.)

    Example:
        >>> is_policy_page("https://example.com/terms-of-service")
        True
        >>> is_policy_page("https://example.com/api/data")
        False
    """
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in POLICY_PATTERNS)


def is_portal_navigation(url: str) -> bool:
    """Check if URL is portal navigation (not data endpoint, Stage 1 pre-filter).

    Args:
        url: URL to check

    Returns:
        True if URL is portal navigation (/apis, /products, /resources, etc.)

    Example:
        >>> is_portal_navigation("https://portal.example.com/apis")
        True
        >>> is_portal_navigation("https://api.example.com/v1/pricing")
        False
    """
    url_lower = url.lower()
    parsed = urlparse(url_lower)
    path = parsed.path

    # Check if it's a simple portal navigation page (exact match or ends with pattern)
    for pattern in PORTAL_NAV_PATTERNS:
        if path == pattern or path.endswith(pattern) or path.endswith(pattern + '/'):
            return True

    return False


def is_system_endpoint(url: str) -> bool:
    """Check if URL is system/monitoring endpoint (Stage 1 pre-filter).

    Args:
        url: URL to check

    Returns:
        True if URL matches system patterns (/health, /trace, /config, etc.)

    Example:
        >>> is_system_endpoint("https://api.example.com/health")
        True
        >>> is_system_endpoint("https://api.example.com/v1/data")
        False
    """
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in SYSTEM_PATTERNS)


def is_likely_api_call(url: str) -> bool:
    """Check if URL looks like an API endpoint.

    Args:
        url: URL to check

    Returns:
        True if URL matches API patterns

    Example:
        >>> is_likely_api_call("https://api.example.com/v1/users")
        True
        >>> is_likely_api_call("https://example.com/static/main.css")
        False
    """
    # Quick rejection filters
    if is_static_asset(url):
        return False

    if is_auth_endpoint(url):
        return False

    # Check for API path patterns
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in API_PATH_PATTERNS)


def is_apim_priority(url: str) -> bool:
    """Check if URL is a high-priority APIM endpoint.

    APIM portals (like MISO) expose API metadata via specific paths.
    These should be prioritized for discovery.

    Args:
        url: URL to check

    Returns:
        True if URL matches APIM priority patterns

    Example:
        >>> is_apim_priority("https://data-exchange.misoenergy.org/developer/apis/pricing-api/operations")
        True
    """
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in APIM_PRIORITY_PATTERNS)


def is_file_browser_api(url: str) -> bool:
    """Check if URL is a file-browser-api endpoint (WEBSITE source pattern).

    File-browser-api pattern is used by portals like SPP for file downloads
    with hierarchical folder navigation.

    Args:
        url: URL to check

    Returns:
        True if URL matches file-browser-api patterns

    Example:
        >>> is_file_browser_api("https://portal.spp.org/file-browser-api/download/da-lmp-by-bus?path=%2F2026")
        True
        >>> is_file_browser_api("https://portal.spp.org/pages/da-lmp-by-bus")
        False
    """
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in FILE_BROWSER_PATTERNS)


def is_openapi_spec_url(url: str) -> bool:
    """Check if URL is an OpenAPI/Swagger spec file (API source pattern).

    OpenAPI/Swagger specs provide machine-readable API definitions
    with complete endpoint lists, parameters, and schemas.

    Args:
        url: URL to check

    Returns:
        True if URL matches OpenAPI/Swagger spec patterns

    Example:
        >>> is_openapi_spec_url("https://api.example.com/openapi.json")
        True
        >>> is_openapi_spec_url("https://api.example.com/v1/data")
        False
    """
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in OPENAPI_SPEC_PATTERNS)


def extract_api_calls_from_network(
    network_calls: List[str],
    seed_url: str = ""
) -> List[str]:
    """Extract likely API endpoints from network_calls.

    Filters network calls to identify likely API endpoints worth exploring.
    Excludes static assets, auth endpoints, and other noise.

    Args:
        network_calls: List of URLs captured during page render
        seed_url: Seed URL for domain filtering (optional)

    Returns:
        Deduplicated list of likely API call URLs

    Example:
        >>> calls = [
        ...     "https://api.example.com/v1/users",
        ...     "https://example.com/static/main.css",
        ...     "https://api.example.com/v1/products"
        ... ]
        >>> extract_api_calls_from_network(calls)
        ['https://api.example.com/v1/users', 'https://api.example.com/v1/products']
    """
    candidates = []

    for url in network_calls:
        if not url:
            continue

        # Apply filters
        if is_likely_api_call(url):
            candidates.append(url)
            logger.debug(f"Identified API call: {url}")

    # Deduplicate
    unique_candidates = list(dict.fromkeys(candidates))

    logger.info(
        f"Extracted {len(unique_candidates)} API calls from {len(network_calls)} network calls "
        f"({len(network_calls) - len(unique_candidates)} filtered)"
    )

    return unique_candidates


def prioritize_apim_calls(api_calls: List[str]) -> List[str]:
    """Sort API calls by priority, with APIM patterns first.

    APIM portals expose API metadata via specific paths that are
    especially valuable for discovery. Sort these to the top.

    Args:
        api_calls: List of API call URLs

    Returns:
        Sorted list with APIM priority calls first

    Example:
        >>> calls = [
        ...     "https://api.example.com/v1/data",
        ...     "https://api.example.com/developer/apis/pricing-api/operations",
        ...     "https://api.example.com/v2/users"
        ... ]
        >>> prioritize_apim_calls(calls)
        ['https://api.example.com/developer/apis/pricing-api/operations', ...]
    """
    priority_calls = []
    regular_calls = []

    for url in api_calls:
        if is_apim_priority(url):
            priority_calls.append(url)
        else:
            regular_calls.append(url)

    sorted_calls = priority_calls + regular_calls

    if priority_calls:
        logger.info(f"Prioritized {len(priority_calls)} APIM calls to front of queue")

    return sorted_calls


# Export public API
__all__ = [
    'extract_api_calls_from_network',
    'prioritize_apim_calls',
    'is_likely_api_call',
    'is_apim_priority',
    'is_file_browser_api',
    'is_openapi_spec_url',
    'API_PATH_PATTERNS',
    'APIM_PRIORITY_PATTERNS',
    'FILE_BROWSER_PATTERNS',
    'OPENAPI_SPEC_PATTERNS',
]
