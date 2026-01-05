"""HTML preprocessing module for extracting structured information.

This module processes raw HTML from Botasaurus and extracts only relevant
structured data for AI analysis, avoiding context flooding with raw HTML.
"""

import logging
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Comment

logger = logging.getLogger(__name__)


class HTMLPreprocessor:
    """Extract structured information from HTML for AI analysis.

    Instead of dumping raw HTML to AI prompts, this class extracts:
    - Links (especially API-related)
    - Clean text content
    - Code blocks
    - Headers (page structure)
    - Tables (often contain endpoint/parameter info)
    - Authentication keywords
    """

    # Patterns that suggest API endpoints
    API_PATTERNS = [
        r'/api/',
        r'/v\d+/',
        r'/rest/',
        r'/graphql',
        r'\.json',
        r'\.xml',
        r'/data/',
        r'/endpoints?',
    ]

    # Authentication-related keywords
    AUTH_KEYWORDS = [
        'api key',
        'api-key',
        'apikey',
        'authentication',
        'authorization',
        'bearer token',
        'oauth',
        'api token',
        'access token',
        'credentials',
        'login',
        'sign in',
    ]

    def __init__(self, base_url: str):
        """Initialize preprocessor.

        Args:
            base_url: Base URL for resolving relative links
        """
        self.base_url = base_url

    def extract_structured_data(self, html: str) -> dict[str, Any]:
        """Extract structured information from HTML.

        Args:
            html: Raw HTML content

        Returns:
            Dictionary with structured data:
            - links: All links (with API endpoints highlighted)
            - api_endpoints: Detected API endpoint patterns
            - text_summary: Clean text (first 3000 chars)
            - code_blocks: Code snippets (usually examples)
            - headers: Page structure (h1, h2, h3)
            - tables: Extracted table data
            - auth_indicators: Authentication-related text
        """
        if not html or not html.strip():
            logger.warning("Empty HTML provided to preprocessor")
            return self._empty_result()

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Remove script, style, and comment elements
            for element in soup(['script', 'style', 'noscript']):
                element.decompose()
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()

            return {
                'links': self._extract_links(soup),
                'api_endpoints': self._extract_api_endpoints(soup),
                'text_summary': self._extract_text_summary(soup),
                'code_blocks': self._extract_code_blocks(soup),
                'headers': self._extract_headers(soup),
                'tables': self._extract_tables(soup),
                'auth_indicators': self._extract_auth_indicators(soup),
            }

        except Exception as e:
            logger.error(f"HTML preprocessing failed: {e}", exc_info=True)
            return self._empty_result()

    def _extract_links(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract all links with categorization."""
        all_links = []
        api_links = []

        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)

            # Resolve relative URLs
            absolute_url = urljoin(self.base_url, href)

            link_info = {
                'url': absolute_url,
                'text': text,
                'is_api': self._is_api_link(absolute_url),
            }

            all_links.append(link_info)

            if link_info['is_api']:
                api_links.append(link_info)

        return {
            'total_count': len(all_links),
            'api_count': len(api_links),
            'all_links': all_links[:100],  # Limit to first 100
            'api_links': api_links,  # Show all API links
        }

    def _extract_api_endpoints(self, soup: BeautifulSoup) -> list[str]:
        """Extract text patterns that look like API endpoints."""
        endpoints = set()

        # Get all text content
        text = soup.get_text()

        # Look for endpoint patterns
        for pattern in self.API_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Get surrounding context (30 chars before/after)
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                endpoints.add(context)

        # Also look for HTTP method patterns (GET /api/...)
        http_methods = r'\b(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s]+)'
        for match in re.finditer(http_methods, text):
            endpoints.add(f"{match.group(1)} {match.group(2)}")

        return sorted(list(endpoints))[:50]  # Limit to 50 endpoints

    def _extract_text_summary(self, soup: BeautifulSoup) -> str:
        """Extract clean text content (no HTML tags) - minimal for context only."""
        # Get text from body if available, otherwise entire document
        body = soup.find('body')
        if body:
            text = body.get_text(separator=' ', strip=True)
        else:
            text = soup.get_text(separator=' ', strip=True)

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)

        # Return first 200 characters - just enough for context
        return text[:200]

    def _extract_code_blocks(self, soup: BeautifulSoup) -> list[str]:
        """Extract code blocks (usually API examples)."""
        code_blocks = []

        for tag in soup.find_all(['code', 'pre']):
            code_text = tag.get_text(strip=True)
            if code_text and len(code_text) > 10:  # Skip tiny snippets
                code_blocks.append(code_text[:500])  # Limit each block to 500 chars

        return code_blocks[:20]  # Limit to 20 code blocks

    def _extract_headers(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        """Extract page structure from headers."""
        headers = []

        for level in ['h1', 'h2', 'h3', 'h4']:
            for header in soup.find_all(level):
                text = header.get_text(strip=True)
                if text:
                    headers.append({
                        'level': level,
                        'text': text,
                    })

        return headers[:50]  # Limit to 50 headers

    def _extract_tables(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract table data (often contains endpoint/parameter info)."""
        tables = []

        for table in soup.find_all('table'):
            table_data = {
                'headers': [],
                'rows': [],
            }

            # Extract headers
            for th in table.find_all('th'):
                table_data['headers'].append(th.get_text(strip=True))

            # Extract rows
            for tr in table.find_all('tr'):
                row = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if row:
                    table_data['rows'].append(row)

            if table_data['headers'] or table_data['rows']:
                tables.append(table_data)

        return tables[:10]  # Limit to 10 tables

    def _extract_auth_indicators(self, soup: BeautifulSoup) -> list[str]:
        """Find authentication-related text snippets."""
        auth_snippets = []
        text = soup.get_text().lower()

        for keyword in self.AUTH_KEYWORDS:
            if keyword in text:
                # Find context around keyword
                pattern = re.compile(f'.{{0,50}}{re.escape(keyword)}.{{0,50}}', re.IGNORECASE)
                matches = pattern.finditer(soup.get_text())
                for match in matches:
                    snippet = match.group(0).strip()
                    if snippet:
                        auth_snippets.append(snippet)

        # Deduplicate and limit
        return list(set(auth_snippets))[:20]

    def _is_api_link(self, url: str) -> bool:
        """Check if URL looks like an API endpoint."""
        url_lower = url.lower()
        return any(re.search(pattern, url_lower) for pattern in self.API_PATTERNS)

    def _empty_result(self) -> dict[str, Any]:
        """Return empty structured data result."""
        return {
            'links': {'total_count': 0, 'api_count': 0, 'all_links': [], 'api_links': []},
            'api_endpoints': [],
            'text_summary': '',
            'code_blocks': [],
            'headers': [],
            'tables': [],
            'auth_indicators': [],
        }


def format_for_prompt(structured_data: dict[str, Any]) -> str:
    """Format structured data as COMPACT context for AI (500-1000 chars max).

    The AI is the "boss" giving directions, not extracting data.
    Show counts + top examples only.

    Args:
        structured_data: Output from HTMLPreprocessor.extract_structured_data()

    Returns:
        Compact formatted string (~500-1000 chars) for AI prompt
    """
    lines = []

    # Quick assessment line
    links = structured_data['links']
    endpoints = structured_data['api_endpoints']

    if links['api_count'] > 5 or len(endpoints) > 3:
        page_type = "API Documentation"
    elif links['total_count'] > 20:
        page_type = "Data Portal/Website"
    else:
        page_type = "Unknown"

    lines.append(f"PAGE TYPE: {page_type}")

    # API Signals (most important for Phase 0)
    if endpoints:
        lines.append(f"\nAPI SIGNALS: {len(endpoints)} endpoint patterns found (top 5):")
        for endpoint in endpoints[:5]:
            lines.append(f"  {endpoint[:80]}")  # Truncate long endpoints

    if links['api_links']:
        lines.append(f"\nAPI LINKS: {links['api_count']} found (top 5):")
        for link in links['api_links'][:5]:
            url_short = link['url'][-60:] if len(link['url']) > 60 else link['url']
            lines.append(f"  {link['text'][:30]}: ...{url_short}")

    # Page structure (minimal)
    headers = structured_data['headers']
    code_blocks = structured_data['code_blocks']
    tables = structured_data['tables']

    structure_parts = []
    if headers:
        structure_parts.append(f"{len(headers)} headers")
    if tables:
        structure_parts.append(f"{len(tables)} tables")
    if code_blocks:
        structure_parts.append(f"{len(code_blocks)} code examples")

    if structure_parts:
        lines.append(f"\nSTRUCTURE: {', '.join(structure_parts)}")

        # Show top 3 headers for context
        if headers:
            lines.append(f"  Top headers: {', '.join([h['text'][:30] for h in headers[:3]])}")

    # Auth indicators (critical for Phase 0)
    auth = structured_data['auth_indicators']
    if auth:
        lines.append(f"\nAUTH INDICATORS: {len(auth)} mentions (top 3):")
        for indicator in auth[:3]:
            lines.append(f"  {indicator[:60]}")  # Truncate long indicators

    # Context summary (last, minimal)
    text = structured_data['text_summary']
    if text:
        lines.append(f"\nCONTEXT: {text}")

    result = '\n'.join(lines)

    # Failsafe: if still too long, truncate
    if len(result) > 1500:
        result = result[:1500] + "\n... [truncated for brevity]"

    return result
