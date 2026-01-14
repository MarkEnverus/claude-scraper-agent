"""Link scoring utilities for BA Analyst - Deterministic heuristic scoring.

This module provides rule-based link scoring for the Link Selector node.
The scoring is deterministic and unit-testable, prioritizing API-relevant
links while filtering out low-value pages.

The scoring system uses a 0-1 scale with the following rules:
- High value keywords (+0.4): api, data, docs, download, openapi, wadl, csv, json, xlsx
- Low value keywords (-0.5): about, careers, legal, social, contact, privacy
- Off-domain links (-0.3): Different domain from seed URL
- Already visited (-1.0): URL is in visited set
"""

import logging
from typing import Set
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# High-value keywords that indicate API-relevant content
HIGH_VALUE_KEYWORDS = {
    'api', 'data', 'docs', 'documentation', 'download', 'openapi', 'swagger',
    'wadl', 'csv', 'json', 'xlsx', 'xml', 'endpoint', 'reference', 'developer',
    'schema', 'spec', 'specification', 'rest', 'graphql', 'query', 'resource'
}

# Low-value keywords that indicate non-API pages
LOW_VALUE_KEYWORDS = {
    'about', 'careers', 'legal', 'social', 'contact', 'privacy', 'terms',
    'cookie', 'disclaimer', 'help', 'support', 'faq', 'blog', 'news',
    'press', 'media', 'team', 'company', 'pricing', 'login', 'signup'
}

# Junk link patterns that should be immediately filtered (hard filter)
JUNK_LINK_PATTERNS = {
    # Authentication/account pages
    'signin', 'sign-in', 'signup', 'sign-up', 'login', 'logout', 'register',

    # Legal/policy pages
    'terms', 'privacy', 'cookie', 'disclaimer', 'legal',

    # Support/help pages
    'help', 'faq', 'contact', 'support',

    # Company/marketing pages
    'about', 'careers', 'jobs', 'team', 'company',

    # OATI login (unless explicitly targeting OATI)
    'oati.com/login', 'oati.com/spp/login',
}

# URL schemes that should be filtered
INVALID_URL_SCHEMES = {
    'blob:', 'mailto:', 'javascript:', 'tel:', 'data:'
}


def is_junk_link(url: str, text: str) -> tuple[bool, str]:
    """Check if a link should be filtered as junk (hard filter).

    This is a hard filter applied before scoring. Links matching these
    patterns are considered navigation chrome/noise and should be dropped.

    Args:
        url: The URL to check
        text: The link text

    Returns:
        Tuple of (is_junk, reason) where:
        - is_junk: True if link should be filtered
        - reason: Explanation of why it's junk

    Example:
        >>> is_junk, reason = is_junk_link("https://example.com/signin", "Sign In")
        >>> print(f"Is junk: {is_junk}, Reason: {reason}")
        Is junk: True, Reason: Junk pattern: signin
    """
    # Check for invalid URL schemes
    url_lower = url.lower()
    for scheme in INVALID_URL_SCHEMES:
        if url_lower.startswith(scheme):
            return True, f"Invalid scheme: {scheme}"

    # Combine URL and text for pattern matching
    search_text = f"{url} {text}".lower()

    # Check for junk patterns
    for pattern in JUNK_LINK_PATTERNS:
        if pattern in search_text:
            logger.debug(f"Filtered junk link: {url[:60]}... (pattern: {pattern})")
            return True, f"Junk pattern: {pattern}"

    return False, ""


def score_link_deterministic(
    url: str,
    text: str,
    seed_url: str,
    visited: Set[str]
) -> tuple[float, str]:
    """Score a link using deterministic heuristic rules.

    This function applies rule-based scoring to prioritize API-relevant links
    and filter out low-value pages. The scoring is deterministic and unit-testable.

    Scoring rules (0-1 scale):
    - Base score: 0.5
    - High value keywords (+0.4): api, data, docs, download, openapi, wadl, csv, json, xlsx
    - Low value keywords (-0.5): about, careers, legal, social, contact, privacy
    - Off-domain links (-0.3): Different domain from seed URL
    - Already visited (-1.0): URL is in visited set

    Args:
        url: The URL to score (absolute)
        text: The link text or description
        seed_url: The original seed URL (for domain comparison)
        visited: Set of already visited URLs

    Returns:
        Tuple of (score, reason) where:
        - score: Float between -1.0 and 1.0
        - reason: String explaining the score

    Example:
        >>> score, reason = score_link_deterministic(
        ...     "https://api.example.com/docs",
        ...     "API Documentation",
        ...     "https://api.example.com",
        ...     set()
        ... )
        >>> print(f"Score: {score}, Reason: {reason}")
        Score: 0.9, Reason: High-value keywords: docs, api
    """
    # Start with base score
    score = 0.5
    reasons = []

    # Check if already visited
    if url in visited:
        logger.debug(f"Link already visited: {url}")
        return -1.0, "Already visited"

    # Combine URL and text for keyword matching
    search_text = f"{url} {text}".lower()

    # Check for high-value keywords
    high_value_matches = [kw for kw in HIGH_VALUE_KEYWORDS if kw in search_text]
    if high_value_matches:
        score += 0.4
        reasons.append(f"High-value keywords: {', '.join(high_value_matches[:3])}")
        logger.debug(f"High-value match for {url}: {high_value_matches}")

    # Check for low-value keywords
    low_value_matches = [kw for kw in LOW_VALUE_KEYWORDS if kw in search_text]
    if low_value_matches:
        score -= 0.5
        reasons.append(f"Low-value keywords: {', '.join(low_value_matches[:3])}")
        logger.debug(f"Low-value match for {url}: {low_value_matches}")

    # Check domain match
    seed_domain = urlparse(seed_url).netloc
    link_domain = urlparse(url).netloc

    if link_domain and seed_domain and link_domain != seed_domain:
        score -= 0.3
        reasons.append(f"Off-domain: {link_domain}")
        logger.debug(f"Off-domain link: {link_domain} vs {seed_domain}")
    else:
        reasons.append(f"Same domain: {seed_domain}")

    # Clamp score to valid range
    score = max(-1.0, min(1.0, score))

    # Build reason string
    reason = "; ".join(reasons) if reasons else "No special signals"

    logger.info(f"Scored link: {url[:60]}... = {score:.2f} ({reason})")
    return score, reason


def filter_links_by_domain(
    links: list[dict],
    allowed_domains: list[str],
    seed_url: str
) -> list[dict]:
    """Filter links to only allowed domains.

    If allowed_domains is empty, only the seed domain is allowed.

    Args:
        links: List of link dictionaries with 'url' key
        allowed_domains: List of allowed domain names (e.g., ['example.com', 'api.example.com'])
        seed_url: Seed URL to extract default domain from

    Returns:
        Filtered list of links

    Example:
        >>> links = [
        ...     {"url": "https://api.example.com/docs"},
        ...     {"url": "https://external.com/link"}
        ... ]
        >>> filtered = filter_links_by_domain(links, [], "https://api.example.com")
        >>> len(filtered)
        1
    """
    seed_domain = urlparse(seed_url).netloc

    # If no allowed domains specified, use seed domain only
    if not allowed_domains:
        allowed_domains = [seed_domain]
        logger.debug(f"No allowed domains specified, using seed domain: {seed_domain}")

    filtered = []
    for link in links:
        url = link.get('url', '')
        link_domain = urlparse(url).netloc

        if link_domain in allowed_domains:
            filtered.append(link)
        else:
            logger.debug(f"Filtered out off-domain link: {link_domain} not in {allowed_domains}")

    logger.info(f"Filtered {len(links)} links to {len(filtered)} within allowed domains")
    return filtered


def filter_visited_links(
    links: list[dict],
    visited: Set[str]
) -> list[dict]:
    """Filter out already visited links.

    Args:
        links: List of link dictionaries with 'url' key
        visited: Set of visited URLs

    Returns:
        Filtered list of unvisited links

    Example:
        >>> links = [
        ...     {"url": "https://api.example.com/docs"},
        ...     {"url": "https://api.example.com/reference"}
        ... ]
        >>> visited = {"https://api.example.com/docs"}
        >>> filtered = filter_visited_links(links, visited)
        >>> len(filtered)
        1
    """
    filtered = [link for link in links if link.get('url') not in visited]
    removed = len(links) - len(filtered)

    if removed > 0:
        logger.info(f"Filtered out {removed} already visited links")

    return filtered


def score_and_sort_links(
    links: list[dict],
    seed_url: str,
    visited: Set[str],
    min_score: float = 0.3,
    filter_junk: bool = True
) -> list[dict]:
    """Score all links and sort by score descending.

    This function applies heuristic scoring to all links, filters out
    low-scoring links and junk links, and returns a sorted list.

    Args:
        links: List of link dictionaries with 'url' and 'text' keys
        seed_url: Seed URL for domain comparison
        visited: Set of visited URLs
        min_score: Minimum score threshold (default: 0.3)
        filter_junk: Apply hard junk filter before scoring (default: True)

    Returns:
        Sorted list of links with added 'heuristic_score' and 'reason' keys

    Example:
        >>> links = [
        ...     {"url": "https://api.example.com/docs", "text": "API Docs"},
        ...     {"url": "https://api.example.com/about", "text": "About Us"}
        ... ]
        >>> scored = score_and_sort_links(links, "https://api.example.com", set())
        >>> scored[0]['heuristic_score'] > scored[1]['heuristic_score']
        True
    """
    scored_links = []
    junk_filtered = 0

    for link in links:
        url = link.get('url', '')
        text = link.get('text', '')

        if not url:
            logger.warning(f"Skipping link with missing URL: {link}")
            continue

        # Apply junk filter first (hard filter)
        if filter_junk:
            is_junk, junk_reason = is_junk_link(url, text)
            if is_junk:
                junk_filtered += 1
                logger.debug(f"Junk filtered: {url[:60]}... ({junk_reason})")
                continue

        # Score the link
        score, reason = score_link_deterministic(url, text, seed_url, visited)

        # Filter by minimum score
        if score < min_score:
            logger.debug(f"Filtered out low-scoring link: {url[:60]}... (score={score:.2f})")
            continue

        # Add scoring metadata to link
        scored_link = {
            **link,
            'heuristic_score': score,
            'reason': reason
        }
        scored_links.append(scored_link)

    # Sort by score descending
    scored_links.sort(key=lambda x: x['heuristic_score'], reverse=True)

    logger.info(
        f"Scored and sorted {len(scored_links)} links "
        f"(junk filtered: {junk_filtered}, low-score filtered: {len(links) - len(scored_links) - junk_filtered}, "
        f"original: {len(links)})"
    )
    return scored_links


# Export public API
__all__ = [
    'score_link_deterministic',
    'is_junk_link',
    'filter_links_by_domain',
    'filter_visited_links',
    'score_and_sort_links',
    'HIGH_VALUE_KEYWORDS',
    'LOW_VALUE_KEYWORDS',
    'JUNK_LINK_PATTERNS',
    'INVALID_URL_SCHEMES',
]
