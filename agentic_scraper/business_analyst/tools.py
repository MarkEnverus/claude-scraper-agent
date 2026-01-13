"""LangChain tool wrappers for BA Analyst.

This module provides LangChain @tool decorators that wrap the underlying
Botasaurus and HTTP utilities for use in LangGraph workflows.
"""

import logging
from typing import Optional
import httpx
from langchain_core.tools import tool

from agentic_scraper.tools.botasaurus_tool import BotasaurusTool

logger = logging.getLogger(__name__)


def is_portal_url(url: str) -> bool:
    """Detect if URL matches portal patterns.

    Portal patterns indicate sites that need special extraction
    with click-through and comprehensive link discovery.

    Portal indicators:
    - Domain contains 'portal' (e.g., portal.spp.org)
    - Path contains '/groups/' (e.g., /groups/integrated-marketplace)
    - Path contains '/projects/' (project management portals)
    - Domain starts with 'my.' (user-facing portals)

    Args:
        url: URL to check

    Returns:
        True if URL matches portal patterns

    Example:
        >>> is_portal_url("https://portal.spp.org/groups/integrated-marketplace")
        True
        >>> is_portal_url("https://data-exchange.misoenergy.org/api-details")
        False
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()

    # Portal domain patterns
    if 'portal' in domain or domain.startswith('my.'):
        return True

    # Portal path patterns
    if '/groups/' in path or '/projects/' in path:
        return True

    return False


def _adapt_portal_schema_to_standard(portal_data: dict, url: str) -> dict:
    """Adapt portal extractor schema to standard BA pipeline schema.

    Portal extractor returns: {all_links, navigation_text, data_links, late_api_calls, ...}
    BA pipeline expects: {markdown, full_text, navigation_links, network_calls, screenshot}

    Args:
        portal_data: Output from extract_comprehensive_website_data()
        url: Source URL (for logging)

    Returns:
        Normalized dict matching standard schema
    """
    # Convert all_links to navigation_links format
    navigation_links = []
    for link in portal_data.get('all_links', []):
        navigation_links.append({
            'text': link.get('text', ''),
            'href': link.get('href', ''),
            'className': '',  # Portal extractor doesn't track className
            'source': link.get('source', 'portal_extractor')
        })

    # Build markdown/full_text from navigation_text (primary) + shadow_dom_text (fallback)
    navigation_text = portal_data.get('navigation_text', '')
    shadow_text = portal_data.get('shadow_dom_text', '')

    # Combine and truncate to safe size (~10k chars)
    combined_text = navigation_text or shadow_text
    if len(combined_text) > 10000:
        combined_text = combined_text[:10000] + "... [truncated]"

    full_text = combined_text
    markdown = combined_text  # Portal extractor doesn't produce markdown, use text as-is

    # Union all network call sources: late_api_calls + cdp_data_urls + URL-like data_links
    network_calls = []
    network_calls.extend(portal_data.get('late_api_calls', []))
    network_calls.extend(portal_data.get('cdp_data_urls', []))

    # Add data_links that look like URLs (not local file paths)
    for data_link in portal_data.get('data_links', []):
        if isinstance(data_link, str) and (data_link.startswith('http://') or data_link.startswith('https://')):
            network_calls.append(data_link)

    # Deduplicate network calls
    network_calls = list(dict.fromkeys(network_calls))

    # Screenshot: portal extractor doesn't capture screenshots
    screenshot = portal_data.get('screenshot', None)

    logger.info(
        f"Adapted portal schema for {url}: "
        f"{len(navigation_links)} links, "
        f"{len(network_calls)} network calls, "
        f"{len(full_text)} chars text"
    )

    return {
        'full_text': full_text,
        'markdown': markdown,
        'navigation_links': navigation_links,
        'network_calls': network_calls,
        'expanded_sections': 0,  # Portal extractor doesn't track expansions
        'screenshot': screenshot,
        'extraction_error': None
    }


@tool
def render_page_with_js(url: str, wait_for: Optional[str] = None) -> dict:
    """Render a JavaScript-heavy page and extract comprehensive data.

    This tool performs full browser automation to:
    - Render JavaScript content completely
    - Expand all collapsible sections (reveals hidden endpoints)
    - Extract navigation/menu links
    - Monitor network calls (API discovery)
    - Capture full page text and markdown
    - Take screenshot for visual verification

    Automatically selects extraction strategy based on URL:
    - Portal sites (portal.*, /groups/, etc.): Uses comprehensive website extraction
    - API/docs sites: Uses standard comprehensive extraction

    Use this for:
    - API documentation portals (Swagger, OpenAPI, custom docs)
    - Developer portals with dynamic content
    - Sites with collapsible/tabbed endpoint listings

    Args:
        url: URL to render and analyze
        wait_for: Optional CSS selector to wait for before extraction

    Returns:
        Dictionary containing:
        - full_text: Complete page text content
        - markdown: HTML converted to markdown
        - navigation_links: List of {'text', 'href', 'className', 'source'}
        - network_calls: List of API URLs discovered
        - expanded_sections: Count of sections expanded
        - screenshot: Path to screenshot file (or None)
        - extraction_error: None if successful, error message otherwise

    Example:
        >>> data = render_page_with_js("https://api.example.com/docs")
        >>> if data['extraction_error']:
        ...     print(f"Error: {data['extraction_error']}")
        >>> else:
        ...     print(f"Found {len(data['navigation_links'])} links")
    """
    logger.info(f"Tool: render_page_with_js({url})")
    try:
        bot = BotasaurusTool()

        # Detect portal pattern and route to appropriate extractor
        if is_portal_url(url):
            logger.info(f"Portal pattern detected: using comprehensive website extraction for {url}")
            portal_result = bot.extract_comprehensive_website_data(url)

            # CRITICAL: Adapt portal schema to standard BA pipeline schema
            result = _adapt_portal_schema_to_standard(portal_result, url)
        else:
            logger.info(f"Standard pattern detected: using comprehensive data extraction for {url}")
            result = bot.extract_comprehensive_data(url)

        logger.info(f"Successfully extracted data from {url}")
        return result
    except Exception as e:
        logger.error(f"Failed to render page: {e}", exc_info=True)
        return {
            "full_text": "",
            "markdown": "",
            "navigation_links": [],
            "network_calls": [],
            "expanded_sections": 0,
            "screenshot": None,
            "extraction_error": str(e)
        }


@tool
def extract_links(url: str) -> list[dict]:
    """Extract and filter navigation links from a page.

    This tool extracts links then filters them with AI to return only
    the most relevant links for API/data source discovery.

    For large link lists (>50), applies 2-pass filtering:
    - Pass 1: Heuristic scoring (fast, deterministic)
    - Pass 2: LLM reranking (top 20 candidates)

    Returns top 20 filtered links to avoid context overflow.

    Use this for:
    - Quick link discovery
    - Following navigation paths
    - Building site map

    Args:
        url: URL to extract links from

    Returns:
        List of filtered link dictionaries (max 20) with keys:
        - text: Link text or label
        - href: Absolute URL
        - heuristic_score: AI relevance score
        - llm_score: LLM refinement score (if applied)
        - combined_score: Final relevance score
        - reason: Why this link is valuable

    Example:
        >>> links = extract_links("https://api.example.com")
        >>> for link in links:
        ...     print(f"{link['text']}: {link['href']} (score: {link['combined_score']})")
    """
    logger.info(f"Tool: extract_links({url})")
    try:
        bot = BotasaurusTool()
        # Use comprehensive extraction but only return links
        result = bot.extract_comprehensive_data(url)
        all_links = result.get("navigation_links", [])
        logger.info(f"Extracted {len(all_links)} raw links from {url}")

        # Apply AI filtering if link count is large
        if len(all_links) > 50:
            logger.info(f"Link count ({len(all_links)}) exceeds threshold, applying AI filtering...")

            from agentic_scraper.business_analyst.nodes.link_selector import filter_links_for_tool

            filtered_links = filter_links_for_tool(
                links=all_links,
                seed_url=url,
                goal="Find API documentation, endpoints, and data sources",
                max_results=20
            )

            logger.info(f"Filtered to {len(filtered_links)} high-value links")
            return filtered_links
        else:
            logger.info(f"Link count ({len(all_links)}) under threshold, returning all")
            return all_links

    except Exception as e:
        logger.error(f"Failed to extract links: {e}", exc_info=True)
        return []


@tool
def capture_network_calls(url: str) -> list[str]:
    """Capture XHR/Fetch network calls made during page load.

    This tool monitors network traffic to discover:
    - Hidden API endpoints
    - AJAX calls for dynamic content
    - GraphQL queries
    - WebSocket connections

    Use this for:
    - API endpoint discovery
    - Understanding data flow
    - Finding undocumented APIs

    Args:
        url: URL to monitor network calls for

    Returns:
        List of API endpoint URLs discovered during page load

    Example:
        >>> calls = capture_network_calls("https://portal.example.com")
        >>> api_calls = [c for c in calls if '/api/' in c]
        >>> print(f"Found {len(api_calls)} API calls")
    """
    logger.info(f"Tool: capture_network_calls({url})")
    try:
        bot = BotasaurusTool()
        network_calls = bot.extract_network_calls(url)
        logger.info(f"Captured {len(network_calls)} network calls from {url}")
        return network_calls
    except Exception as e:
        logger.error(f"Failed to capture network calls: {e}", exc_info=True)
        return []


@tool
def http_get_headers(url: str) -> dict:
    """Perform fast HEAD request to get HTTP headers and status code.

    This tool makes a lightweight HTTP request without fetching the body.
    Use this for:
    - Quick status checks (200, 401, 403, etc.)
    - Auth detection (WWW-Authenticate header)
    - Content-Type detection
    - Redirect detection

    Much faster than render_page_with_js when you only need metadata.

    Args:
        url: URL to check

    Returns:
        Dictionary containing:
        - status_code: HTTP status code
        - headers: Dict of HTTP headers (lowercase keys)
        - redirected_to: Final URL after redirects (or None)
        - error: Error message if request failed (or None)

    Example:
        >>> info = http_get_headers("https://api.example.com")
        >>> if info['status_code'] == 401:
        ...     print("Authentication required")
        >>> if 'www-authenticate' in info['headers']:
        ...     print(f"Auth method: {info['headers']['www-authenticate']}")
    """
    logger.info(f"Tool: http_get_headers({url})")
    try:
        with httpx.Client(follow_redirects=True, timeout=10.0) as client:
            # Use HEAD for fast metadata check
            response = client.head(url)

            # Get final URL after redirects
            redirected_to = str(response.url) if response.url != url else None

            result = {
                "status_code": response.status_code,
                "headers": {k.lower(): v for k, v in response.headers.items()},
                "redirected_to": redirected_to,
                "error": None
            }
            logger.info(f"Got headers from {url}: status={result['status_code']}")
            return result

    except Exception as e:
        logger.error(f"Failed to get headers: {e}", exc_info=True)
        return {
            "status_code": 0,
            "headers": {},
            "redirected_to": None,
            "error": str(e)
        }


@tool
def http_get_robots(url: str) -> dict:
    """Fetch and parse robots.txt file.

    This tool retrieves the robots.txt file from a domain to check:
    - Allowed/disallowed paths
    - Crawl-delay directives
    - Sitemap locations

    Use this for:
    - Respecting robots.txt directives (if config.respect_robots=True)
    - Finding sitemap.xml links
    - Understanding site structure

    Args:
        url: URL to fetch robots.txt for (scheme://domain used)

    Returns:
        Dictionary containing:
        - content: Raw robots.txt content
        - disallowed_paths: List of disallowed paths for User-agent: *
        - sitemaps: List of sitemap URLs
        - error: Error message if fetch failed (or None)

    Example:
        >>> robots = http_get_robots("https://api.example.com")
        >>> if '/admin/' in robots['disallowed_paths']:
        ...     print("Admin area is disallowed")
        >>> for sitemap in robots['sitemaps']:
        ...     print(f"Sitemap: {sitemap}")
    """
    logger.info(f"Tool: http_get_robots({url})")
    try:
        # Extract domain from URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        with httpx.Client(timeout=10.0) as client:
            response = client.get(robots_url)

            if response.status_code != 200:
                return {
                    "content": "",
                    "disallowed_paths": [],
                    "sitemaps": [],
                    "error": f"HTTP {response.status_code}"
                }

            content = response.text

            # Parse robots.txt
            disallowed_paths = []
            sitemaps = []
            for line in content.splitlines():
                line = line.strip()
                if line.lower().startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        disallowed_paths.append(path)
                elif line.lower().startswith("sitemap:"):
                    sitemap = line.split(":", 1)[1].strip()
                    if sitemap:
                        sitemaps.append(sitemap)

            result = {
                "content": content,
                "disallowed_paths": disallowed_paths,
                "sitemaps": sitemaps,
                "error": None
            }
            logger.info(f"Parsed robots.txt: {len(disallowed_paths)} disallowed, {len(sitemaps)} sitemaps")
            return result

    except Exception as e:
        logger.error(f"Failed to fetch robots.txt: {e}", exc_info=True)
        return {
            "content": "",
            "disallowed_paths": [],
            "sitemaps": [],
            "error": str(e)
        }


# Export all tools
__all__ = [
    "render_page_with_js",
    "extract_links",
    "capture_network_calls",
    "http_get_headers",
    "http_get_robots",
]
