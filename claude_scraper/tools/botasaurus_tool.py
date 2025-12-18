"""Botasaurus tool wrapper for browser automation.

This module provides browser automation using Botasaurus for:
- Fetching JavaScript-rendered pages
- Network traffic monitoring
- Anti-bot detection handling

NO WebFetch is used - all network calls go through Botasaurus.
"""

import logging
from typing import Optional
from botasaurus.browser import Driver

logger = logging.getLogger(__name__)


class BotasaurusTool:
    """Browser automation tool using Botasaurus.

    Provides:
    - JavaScript-rendered page content extraction
    - Network traffic monitoring for API discovery
    - Anti-bot detection (Cloudflare, reCAPTCHA, etc.)
    - Pure Python - no Node.js required

    Example:
        >>> tool = BotasaurusTool()
        >>> html = tool.get_page_content("https://api.example.com/docs")
        >>> api_calls = tool.extract_network_calls("https://portal.example.com")
    """

    def __init__(self) -> None:
        """Initialize Botasaurus tool."""
        logger.info("Initializing BotasaurusTool (browser automation)")

    def get_page_content(self, url: str, wait_for_selector: Optional[str] = None) -> str:
        """Fetch page content after JavaScript execution.

        Args:
            url: URL to fetch
            wait_for_selector: Optional CSS selector to wait for

        Returns:
            HTML content after JavaScript execution

        Raises:
            RuntimeError: If page fetch fails
        """
        logger.info(f"Fetching page content with Botasaurus: {url}")

        driver = None
        try:
            # Create Driver instance
            logger.debug("Initializing Botasaurus Driver...")
            driver = Driver(
                headless=True,
                block_images=True,
                wait_for_complete_page_load=True
            )
            logger.debug(f"Driver initialized, navigating to {url}")

            # Navigate to URL
            driver.get(url)
            logger.debug(f"Page loaded, current URL: {driver.current_url}")

            # Wait for specific selector if provided
            if wait_for_selector:
                logger.debug(f"Waiting for selector: {wait_for_selector}")
                driver.wait_for_element(wait_for_selector, timeout=10)

            # Additional wait for dynamic content to load
            logger.debug("Waiting 2 seconds for dynamic content...")
            driver.sleep(2)

            # Get page HTML
            html_content = driver.page_html
            logger.debug(f"Got page_html: {len(html_content)} bytes, first 100 chars: {html_content[:100]}")

            if not html_content or len(html_content) < 100:
                logger.warning(f"Page source is empty or very small: {len(html_content)} bytes")
                logger.debug(f"Full page source: {html_content}")

            logger.info(f"Successfully fetched page content ({len(html_content)} bytes)")
            return html_content

        except Exception as e:
            logger.error(f"Botasaurus execution failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to fetch page with Botasaurus: {e}")
        finally:
            # Always close the driver
            if driver:
                try:
                    driver.close()
                    logger.debug("Driver closed")
                except Exception as e:
                    logger.warning(f"Failed to close driver: {e}")

    def extract_network_calls(self, url: str) -> list[str]:
        """Extract network API calls from page load.

        Args:
            url: URL to navigate to and monitor

        Returns:
            List of API endpoint URLs discovered
        """
        logger.info(f"Extracting network calls from {url}")

        driver = None
        try:
            # Create Driver instance
            driver = Driver(
                headless=True,
                block_images=True,
                wait_for_complete_page_load=True
            )

            # Navigate to page
            driver.get(url)

            # Wait for network activity to settle
            driver.sleep(3)

            # Get network logs from Performance API
            logs = driver.run_js("""
                const entries = performance.getEntriesByType('resource');
                return entries.map(e => ({
                    url: e.name,
                    type: e.initiatorType
                }));
            """)

            # Filter for API calls
            api_calls = []
            for log in logs:
                url_str = log['url']
                if (
                    '/api/' in url_str or
                    url_str.endswith('.json') or
                    url_str.endswith('.xml') or
                    (log['type'] in ['fetch', 'xmlhttprequest']) or
                    ('http' in url_str and
                     not url_str.endswith(('.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf')))
                ):
                    if url_str not in api_calls:
                        api_calls.append(url_str)

            logger.info(f"Extracted {len(api_calls)} network calls")
            return api_calls

        except Exception as e:
            logger.error(f"Network extraction failed: {e}")
            return []
        finally:
            # Always close the driver
            if driver:
                try:
                    driver.close()
                except Exception as e:
                    logger.warning(f"Failed to close driver: {e}")

    def navigate(self, url: str) -> None:
        """Navigate to URL (compatibility method).

        For backward compatibility. Use get_page_content() instead.
        """
        self.get_page_content(url)

    def screenshot(self, path: Optional[str] = None) -> bytes:
        """Take screenshot (not implemented).

        Placeholder for future screenshot functionality.
        """
        raise NotImplementedError("Screenshot functionality not yet implemented")

    def evaluate(self, script: str) -> str:
        """Evaluate JavaScript (not implemented).

        Placeholder for future JavaScript evaluation.
        """
        raise NotImplementedError("JavaScript evaluation not yet implemented")
