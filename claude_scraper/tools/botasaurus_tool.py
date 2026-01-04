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
from markdownify import markdownify as md

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
            logger.debug(f"Got page_html: {len(html_content)} bytes")

            if not html_content or len(html_content) < 100:
                logger.warning(f"Page source is empty or very small: {len(html_content)} bytes")

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

    def extract_comprehensive_data(self, url: str) -> dict:
        """Extract EVERYTHING needed for AI-based endpoint discovery.

        This method performs comprehensive extraction to support AI-first discovery:
        1. Renders JavaScript-heavy pages fully
        2. Expands ALL collapsible sections (reveals hidden endpoints)
        3. Extracts navigation/menu links
        4. Monitors network calls
        5. Gets full page text content
        6. Takes screenshot for visual verification

        Args:
            url: URL to analyze

        Returns:
            Dictionary containing:
            - full_text: Complete page text content (after expansion)
            - markdown: HTML converted to markdown (preserves structure)
            - navigation_links: All nav/menu links with text and href
            - network_calls: API URLs discovered during page load
            - expanded_sections: Count of sections expanded
            - screenshot: Path to screenshot file (or None)

        Example:
            >>> tool = BotasaurusTool()
            >>> data = tool.extract_comprehensive_data("https://api.example.com/docs")
            >>> print(f"Found {len(data['navigation_links'])} navigation links")
            >>> print(f"Page text: {len(data['full_text'])} characters")
        """
        logger.info(f"Extracting comprehensive data from {url}")

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
            logger.debug(f"Page loaded: {driver.current_url}")

            # Wait for initial JavaScript execution
            driver.sleep(5)
            logger.debug("Initial JS execution complete")

            # Step 1: Expand ALL collapsible sections
            expanded_count = self._expand_all_sections(driver)
            logger.info(f"Expanded {expanded_count} collapsible sections")

            # Step 2: Extract navigation links
            nav_links = self._extract_navigation_links(driver)
            logger.info(f"Found {len(nav_links)} navigation links")

            # Step 3: Extract network calls
            network_calls = self._extract_network_calls_internal(driver)
            logger.info(f"Found {len(network_calls)} network calls")

            # Step 4: Get FULL page text
            full_text = driver.run_js("return document.body.textContent;")
            logger.info(f"Extracted {len(full_text)} characters of page text")

            # Step 4.5: Extract HTML and convert to markdown (preserves structure)
            try:
                # Botasaurus uses page_html or run_js to get HTML
                html = driver.run_js("return document.documentElement.outerHTML;")
                markdown_content = md(
                    html,
                    heading_style="ATX",  # Use # headers
                    bullets="-",          # Use - for lists
                    strip=['script', 'style', 'meta', 'link']  # Remove non-content tags
                )
                logger.info(f"Converted HTML to markdown: {len(markdown_content)} characters")
            except Exception as e:
                logger.warning(f"Failed to convert HTML to markdown: {e}")
                markdown_content = full_text  # Fallback to plain text

            # Step 5: Take screenshot (optional)
            screenshot_path = None
            try:
                import os
                os.makedirs("datasource_analysis", exist_ok=True)
                screenshot_path = "datasource_analysis/page_screenshot.png"
                driver.save_screenshot(screenshot_path)
                logger.info(f"Screenshot saved: {screenshot_path}")

                # Compress screenshot if it exceeds size limit
                self._compress_screenshot(screenshot_path)
            except Exception as e:
                logger.warning(f"Could not save screenshot: {e}")

            return {
                "full_text": full_text,
                "markdown": markdown_content,
                "navigation_links": nav_links,
                "network_calls": network_calls,
                "expanded_sections": expanded_count,
                "screenshot": screenshot_path
            }

        except Exception as e:
            logger.error(f"Comprehensive extraction failed: {e}", exc_info=True)
            # Return empty structure instead of raising
            return {
                "full_text": "",
                "markdown": "",
                "navigation_links": [],
                "network_calls": [],
                "expanded_sections": 0,
                "screenshot": None
            }
        finally:
            if driver:
                try:
                    driver.close()
                    logger.debug("Driver closed")
                except Exception as e:
                    logger.warning(f"Failed to close driver: {e}")

    def _text_matches_operation(self, op_name: str, elem_text: str) -> bool:
        """Check if element text matches operation name (flexible matching).

        Args:
            op_name: Operation name to match (e.g., "Get Current Data")
            elem_text: Element text content

        Returns:
            True if text matches, False otherwise
        """
        if not elem_text:
            return False

        op_norm = op_name.lower().strip()
        text_norm = elem_text.lower().strip()

        # Exact match
        if op_norm == text_norm:
            return True

        # Substring match (bidirectional) with length constraint
        if len(elem_text) < 100:  # Avoid matching parent divs with long text
            if op_norm in text_norm or text_norm in op_norm:
                return True

        return False

    def _is_valid_data_url(self, url: str) -> bool:
        """Check if URL looks like a data endpoint/file (not navigation chrome).

        Args:
            url: URL to validate

        Returns:
            True if URL appears to be data-related, False otherwise
        """
        if not url or url.startswith('#'):
            return False

        url_lower = url.lower()

        # Exclude obvious navigation/UI chrome
        exclude_patterns = [
            '/about', '/contact', '/home', '/login', '/signup', '/logout',
            '/profile', '/settings', '/help', '/faq', '/terms', '/privacy',
            'javascript:', 'mailto:', '#'
        ]

        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False

        # Include data-related patterns
        data_patterns = [
            '/api/', '/v1/', '/v2/', '/v3/', '/data/', '/reports/', '/download/',
            '/files/', '/export/', '/feed/',
            '.csv', '.json', '.xml', '.xlsx', '.xls', '.zip', '.pdf', '.txt'
        ]

        for pattern in data_patterns:
            if pattern in url_lower:
                return True

        # If full URL with http/https and not excluded, consider valid
        # (Covers custom API paths that don't match common patterns)
        if url.startswith('http'):
            return True

        return False

    def _extract_endpoint_from_dom(self, driver: Driver, op_name: str) -> str | None:
        """Extract endpoint path from Swagger/OpenAPI operation details DOM.

        After clicking a Swagger operation, the details section shows the endpoint path.
        This method extracts it from the visible DOM elements.

        Args:
            driver: Botasaurus Driver instance
            op_name: Operation name for context

        Returns:
            Endpoint URL/path if found, None otherwise
        """
        try:
            import re

            # Swagger/OpenAPI-specific selectors where endpoint paths are displayed
            selectors = [
                '.opblock-summary-path',      # Swagger UI: Endpoint path display
                '[data-path]',                # Data attributes with path
                '.opblock-summary-description',  # Description section
                'code',                       # Code blocks often show paths
                '.endpoint-path',             # Generic endpoint path class
                '.api-path',                  # Alternative API path class
                '.path'                       # Generic path class
            ]

            for selector in selectors:
                try:
                    elements = driver.select_all(selector, wait=None)
                    for elem in elements:
                        text = elem.text.strip()

                        # Look for path patterns: /api/..., /v1/..., etc.
                        # Should start with / and be reasonably short
                        if text.startswith('/') and len(text) < 200:
                            # Extract path from text (might have method prefix like "GET /api/v1/data")
                            match = re.search(r'(/[a-zA-Z0-9/_\-{}.]+)', text)
                            if match:
                                path = match.group(1)
                                logger.debug(f"    Found endpoint path in DOM: {path}")
                                return path

                        # Also check data-path attribute
                        data_path = elem.get_attribute('data-path')
                        if data_path and data_path.startswith('/'):
                            logger.debug(f"    Found endpoint path in data attribute: {data_path}")
                            return data_path

                except Exception as e:
                    logger.debug(f"    Failed to check selector {selector}: {e}")
                    continue

            logger.debug(f"    No endpoint path found in DOM for {op_name}")
            return None

        except Exception as e:
            logger.debug(f"    DOM extraction error: {e}")
            return None

    def _expand_all_sections(self, driver: Driver) -> int:
        """Expand ALL collapsible sections to reveal hidden endpoints.

        Many API documentation sites hide endpoints in collapsible sections,
        accordions, tabs, etc. This method clicks all expandable elements
        to reveal hidden content.

        Args:
            driver: Botasaurus Driver instance

        Returns:
            Number of sections expanded
        """
        try:
            expanded_count = driver.run_js("""
                // Expand ALL collapsible sections
                const selectors = [
                    'button[aria-expanded="false"]',  // ARIA buttons
                    'summary',  // HTML <details> elements
                    '.opblock-summary',  // Swagger/OpenAPI
                    '[class*="collaps"]:not([class*="show"])',  // Bootstrap collapse
                    '[class*="accord"]:not([class*="open"])',  // Accordions
                    '[data-toggle]',  // Toggle buttons
                    '.operation.is-closed',  // Operation containers
                ];

                let expanded = 0;

                for (const selector of selectors) {
                    const elements = document.querySelectorAll(selector);
                    for (const el of elements) {
                        try {
                            el.click();
                            expanded++;
                        } catch (e) {
                            // Element not clickable, skip
                        }
                    }
                }

                return expanded;
            """)

            # Wait for content to load after expansion
            driver.sleep(2)

            return expanded_count if expanded_count else 0

        except Exception as e:
            logger.warning(f"Failed to expand sections: {e}")
            return 0

    def _extract_navigation_links(self, driver: Driver) -> list[dict]:
        """Extract ALL navigation and menu links from the page using enhanced selectors.

        FIX #1: Expanded selectors to include content area links (main, article) and
        data-specific patterns (.csv, .json, /download) to fix NYISO download link extraction.

        Args:
            driver: Botasaurus Driver instance

        Returns:
            List of dicts with 'text', 'href', 'className', and 'source' keys
        """
        try:
            result = driver.run_js("""
                const links = [];

                // Selector groups with source attribution
                const selectorGroups = [
                    {
                        source: 'nav',
                        selectors: [
                            'nav a', '.nav a', '.menu a',
                            '.sidebar a', '[role="navigation"] a'
                        ]
                    },
                    {
                        source: 'content',
                        selectors: [
                            'main a', 'article a', '.content a', '#content a'
                        ]
                    },
                    {
                        source: 'data',
                        selectors: [
                            'a[href$=".csv"]', 'a[href$=".json"]',
                            'a[href$=".xml"]', 'a[href$=".xlsx"]',
                            'a[href*="/download"]', 'a[href*="/data/"]'
                        ]
                    },
                    {
                        source: 'api',
                        selectors: [
                            '.opblock-summary', '[data-path]',
                            '.api-endpoint', '.endpoint'
                        ]
                    }
                ];

                // Extract links from all selector groups
                for (const group of selectorGroups) {
                    for (const selector of group.selectors) {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach(el => {
                            const text = el.textContent.trim();
                            const href = el.href || el.getAttribute('data-path');
                            if (text && href) {
                                links.push({
                                    text: text,
                                    href: href,
                                    className: el.className,
                                    source: group.source
                                });
                            }
                        });
                    }
                }

                // Deduplicate by href (keep first occurrence)
                const seen = new Set();
                const unique = [];
                for (const link of links) {
                    if (!seen.has(link.href)) {
                        seen.add(link.href);
                        unique.push(link);
                    }
                }

                // Calculate source breakdown for logging
                const breakdown = {
                    nav: unique.filter(l => l.source === 'nav').length,
                    content: unique.filter(l => l.source === 'content').length,
                    data: unique.filter(l => l.source === 'data').length,
                    api: unique.filter(l => l.source === 'api').length
                };

                return { links: unique, breakdown: breakdown };
            """)

            links = result['links'] if result and 'links' in result else []
            breakdown = result['breakdown'] if result and 'breakdown' in result else {}

            # Enhanced logging with breakdown
            if breakdown:
                logger.info(
                    f"Extracted {len(links)} links "
                    f"({breakdown.get('nav', 0)} from nav, "
                    f"{breakdown.get('content', 0)} from content, "
                    f"{breakdown.get('data', 0)} from data, "
                    f"{breakdown.get('api', 0)} from api)"
                )
            else:
                logger.info(f"Extracted {len(links)} links")

            return links

        except Exception as e:
            logger.warning(f"Failed to extract navigation links: {e}")
            return []

    def _extract_network_calls_internal(self, driver: Driver) -> list[str]:
        """Extract network calls (internal method for use with existing driver).

        Args:
            driver: Botasaurus Driver instance

        Returns:
            List of API endpoint URLs
        """
        try:
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
                     not url_str.endswith(('.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff2', '.woff2', '.ttf')))
                ):
                    if url_str not in api_calls:
                        api_calls.append(url_str)

            return api_calls

        except Exception as e:
            logger.warning(f"Failed to extract network calls: {e}")
            return []

    def _compress_screenshot(self, screenshot_path: str, max_size_mb: float = 3.5, max_dimension_px: int = 7000) -> bool:
        """Compress screenshot if it exceeds size or dimension limits.

        Args:
            screenshot_path: Path to screenshot file
            max_size_mb: Maximum size in MB (default 3.5MB for safe margin with base64 overhead)
            max_dimension_px: Maximum dimension in pixels (default 7000px, Anthropic limit is 8000px)

        Returns:
            True if compression successful or not needed, False if failed
        """
        try:
            import os
            from PIL import Image

            # Load image to check dimensions
            img = Image.open(screenshot_path)
            original_width, original_height = img.size
            file_size = os.path.getsize(screenshot_path)
            file_size_mb = file_size / (1024 * 1024)
            max_size_bytes = int(max_size_mb * 1024 * 1024)

            # Check if compression needed
            needs_dimension_compression = original_width > max_dimension_px or original_height > max_dimension_px
            needs_size_compression = file_size > max_size_bytes

            if not needs_dimension_compression and not needs_size_compression:
                logger.info(f"Screenshot OK: {file_size_mb:.2f}MB, {original_width}x{original_height}px")
                return True

            # Log compression reason
            if needs_dimension_compression:
                logger.warning(
                    f"Screenshot dimensions too large: {original_width}x{original_height}px "
                    f"(limit: {max_dimension_px}px per dimension). Compressing..."
                )
            if needs_size_compression:
                logger.warning(
                    f"Screenshot file too large: {file_size_mb:.2f}MB (limit: {max_size_mb}MB). Compressing..."
                )

            # Calculate scale factor to meet BOTH dimension and size requirements
            scale_factor = 1.0

            # Scale down for dimensions if needed
            if needs_dimension_compression:
                max_current_dimension = max(original_width, original_height)
                dimension_scale = max_dimension_px / max_current_dimension
                scale_factor = min(scale_factor, dimension_scale)

            # Be more aggressive if size is very large
            if file_size_mb > 5.0:
                scale_factor = min(scale_factor, 0.5)
            elif file_size_mb > 4.0:
                scale_factor = min(scale_factor, 0.7)

            # Apply compression
            quality = 85
            if scale_factor < 1.0:
                new_dimensions = (int(img.width * scale_factor), int(img.height * scale_factor))
                img_resized = img.resize(new_dimensions, Image.LANCZOS)
                img_resized.save(screenshot_path, format='PNG', optimize=True, quality=quality)
            else:
                img.save(screenshot_path, format='PNG', optimize=True, quality=quality)

            new_size = os.path.getsize(screenshot_path)
            new_size_mb = new_size / (1024 * 1024)
            new_img = Image.open(screenshot_path)
            new_width, new_height = new_img.size
            reduction_pct = ((file_size - new_size) / file_size) * 100

            logger.info(
                f"Compression successful: "
                f"{file_size_mb:.2f}MB {original_width}x{original_height}px → "
                f"{new_size_mb:.2f}MB {new_width}x{new_height}px "
                f"(scale={scale_factor:.2f}, quality={quality}%, {reduction_pct:.1f}% size reduction)"
            )

            # Verify both constraints met
            meets_size = new_size <= max_size_bytes
            meets_dimension = new_width <= max_dimension_px and new_height <= max_dimension_px

            if not meets_size or not meets_dimension:
                logger.error(
                    f"Compression insufficient: size_ok={meets_size}, dimension_ok={meets_dimension}"
                )

            return meets_size and meets_dimension

        except Exception as e:
            logger.error(f"Screenshot compression failed: {e}")
            return False

    def extract_operation_urls(self, url: str, operation_names: list[str]) -> dict[str, str]:
        """Extract actual operation URLs by clicking on operations.

        For JavaScript-driven API documentation sites, operation links may not
        have traditional href attributes. Instead, clicking them updates the URL
        hash via client-side routing. This method clicks each operation and
        captures the resulting URL.

        Args:
            url: Base API documentation URL (e.g., "https://api.example.com/docs#api=data-api")
            operation_names: List of operation names to click (e.g., ["Get Current Data", "Get Historical Data"])

        Returns:
            Dict mapping operation names to their actual URLs
            Example: {"Get Current Data": "https://api.example.com/docs#api=data-api&operation=get-current-data"}

        Example:
            >>> tool = BotasaurusTool()
            >>> ops = ["Get Current Data", "Get Historical Data"]
            >>> urls = tool.extract_operation_urls("https://api.example.com/docs#api=data-api", ops)
            >>> print(urls["Get Current Data"])
            "https://api.example.com/docs#api=data-api&operation=get-current-data"
        """
        logger.info(f"Extracting operation URLs for {len(operation_names)} operations from {url}")

        driver = None
        operation_urls = {}

        try:
            # Create Driver instance
            driver = Driver(
                headless=True,
                block_images=True,
                wait_for_complete_page_load=True
            )

            # Navigate to page
            driver.get(url)
            logger.debug(f"Page loaded: {driver.current_url}")

            # Wait for page to load
            driver.sleep(5)

            # FIX #9: Multi-strategy URL extraction
            # Priority 1: Extract href before clicking (BEST for download links)
            # Priority 2: Click and check URL change (for navigation)
            # Priority 3: Check hash routing (for SPAs)

            for op_name in operation_names:
                try:
                    logger.debug(f"Looking for operation: {op_name}")

                    # Strategy: Find link elements with matching text
                    # Use "a[href]" selector to target only links with href attributes
                    link_elements = driver.select_all("a[href]", wait=None)

                    found = False
                    for link in link_elements:
                        try:
                            link_text = link.text.strip()

                            # Flexible text matching
                            if self._text_matches_operation(op_name, link_text):
                                logger.debug(f"  Found matching link: {link_text[:50]}")

                                # Strategy 1: Extract href BEFORE clicking
                                href = link.get_attribute('href')

                                if href and self._is_valid_data_url(href):
                                    logger.debug(f"  ✅ Extracted href: {href}")
                                    operation_urls[op_name] = href
                                    found = True
                                    break

                                # Strategy 2: Try clicking to see if URL changes
                                original_url = driver.current_url
                                original_hash = driver.execute_script("return window.location.hash")

                                try:
                                    link.click()
                                    driver.sleep(2)  # Wait for navigation

                                    new_url = driver.current_url
                                    new_hash = driver.execute_script("return window.location.hash")

                                    if new_url != original_url:
                                        # URL changed - navigation occurred
                                        logger.debug(f"  ✅ URL changed: {new_url}")
                                        operation_urls[op_name] = new_url
                                        found = True
                                        break
                                    elif new_hash != original_hash:
                                        # Hash routing (SPA) - URL didn't change but hash did
                                        full_url = f"{original_url.split('#')[0]}{new_hash}"
                                        logger.debug(f"  ✅ Hash changed: {full_url}")
                                        operation_urls[op_name] = full_url
                                        found = True
                                        break
                                    else:
                                        # Strategy 3: Try extracting from Swagger DOM
                                        endpoint_path = self._extract_endpoint_from_dom(driver, op_name)
                                        if endpoint_path:
                                            logger.debug(f"  ✅ Extracted from DOM: {endpoint_path}")
                                            operation_urls[op_name] = endpoint_path
                                            found = True
                                            break
                                        # URL didn't change - might be download link
                                        # If href was valid but filtered out, use it anyway
                                        elif href and href.startswith('http'):
                                            logger.debug(f"  ✅ Using href (no URL change): {href}")
                                            operation_urls[op_name] = href
                                            found = True
                                            break

                                except Exception as click_error:
                                    logger.debug(f"  Click failed: {click_error}")
                                    # If clicking failed but we have href, use it
                                    if href and href.startswith('http'):
                                        logger.debug(f"  ✅ Using href (click failed): {href}")
                                        operation_urls[op_name] = href
                                        found = True
                                        break

                        except Exception as elem_error:
                            logger.debug(f"  Element error: {elem_error}")
                            pass  # Try next element

                    if not found:
                        logger.warning(f"  ❌ Could not extract URL for: {op_name}")

                except Exception as e:
                    logger.warning(f"  ❌ Error processing operation {op_name}: {e}")

            logger.info(f"✅ Extracted {len(operation_urls)}/{len(operation_names)} operation URLs")

            # Log summary for debugging
            if operation_urls:
                logger.debug("Extracted URLs:")
                for op_name, op_url in operation_urls.items():
                    logger.debug(f"  {op_name[:30]:30} -> {op_url[:80]}")

            return operation_urls

        except Exception as e:
            logger.error(f"Failed to extract operation URLs: {e}", exc_info=True)
            return {}
        finally:
            if driver:
                try:
                    driver.close()
                    logger.debug("Driver closed")
                except Exception as e:
                    logger.warning(f"Failed to close driver: {e}")

    def filter_bad_urls(self, urls: list[str]) -> tuple[list[str], dict]:
        """Filter out URLs that are clearly not API endpoints.

        FIX #14: Link filtering to exclude Wikipedia, login pages, spec URLs

        Filters out:
        - Wikipedia links
        - Login/signup/auth pages
        - Spec file URLs (swagger.json, openapi.json, WADL, etc.)
        - Generic website navigation (about, contact, privacy, etc.)
        - Hash-only fragments

        Args:
            urls: List of URLs to filter

        Returns:
            Tuple of (filtered_urls, metrics) where metrics contains:
              - original_count: Number of input URLs
              - filtered_count: Number of URLs after filtering
              - removed_count: Number of URLs removed
              - categories: Dict of removal reasons and counts

        Example:
            >>> urls = ['https://api.example.com/v1/data', 'https://en.wikipedia.org/wiki/API']
            >>> filtered, metrics = tool.filter_bad_urls(urls)
            >>> print(f"Kept {len(filtered)}/{len(urls)} URLs")
        """
        import re
        from urllib.parse import urlparse

        logger.info("=== FILTERING BAD URLS ===")

        filtered = []
        removal_reasons = {
            'wikipedia': 0,
            'login_auth': 0,
            'spec_files': 0,
            'website_nav': 0,
            'invalid': 0
        }

        # Bad patterns
        bad_domains = ['wikipedia.org', 'wikimedia.org']
        login_patterns = ['/login', '/signup', '/signin', '/auth', '/register', '/account', '/password']
        spec_patterns = ['swagger.json', 'openapi.json', 'openapi.yaml', '?_wadl', 'application.wadl']
        website_nav_patterns = [
            '/about', '/contact', '/privacy', '/terms', '/help', '/faq',
            '/blog', '/news', '/careers', '/team', '/company',
            '/products', '/services', '/solutions', '/resources',
            '/documentation', '/docs', '/guide', '/tutorial',  # Keep only if /api/ also present
            '/home', '/index', '/sitemap', '/search'
        ]

        for url in urls:
            try:
                parsed = urlparse(url)

                # Check for bad domains
                if any(bad_domain in parsed.netloc for bad_domain in bad_domains):
                    removal_reasons['wikipedia'] += 1
                    logger.debug(f"❌ Filtered (wikipedia): {url}")
                    continue

                # Check for login/auth pages
                if any(pattern in url.lower() for pattern in login_patterns):
                    removal_reasons['login_auth'] += 1
                    logger.debug(f"❌ Filtered (login/auth): {url}")
                    continue

                # Check for spec files
                if any(pattern in url.lower() for pattern in spec_patterns):
                    removal_reasons['spec_files'] += 1
                    logger.debug(f"❌ Filtered (spec file): {url}")
                    continue

                # Check for website navigation (unless it's an API path)
                is_website_nav = any(pattern in url.lower() for pattern in website_nav_patterns)
                has_api_indicator = '/api/' in url.lower() or url.endswith('.json') or url.endswith('.xml')

                if is_website_nav and not has_api_indicator:
                    removal_reasons['website_nav'] += 1
                    logger.debug(f"❌ Filtered (website nav): {url}")
                    continue

                # Check for invalid/empty URLs
                if not url or url.startswith('#') or url == 'javascript:void(0)':
                    removal_reasons['invalid'] += 1
                    logger.debug(f"❌ Filtered (invalid): {url}")
                    continue

                # Passed all filters
                filtered.append(url)

            except Exception as e:
                logger.warning(f"Error filtering URL {url}: {e}")
                removal_reasons['invalid'] += 1
                continue

        metrics = {
            'original_count': len(urls),
            'filtered_count': len(filtered),
            'removed_count': len(urls) - len(filtered),
            'categories': removal_reasons
        }

        logger.info(
            f"URL filtering complete: {metrics['original_count']} → {metrics['filtered_count']} URLs "
            f"({metrics['removed_count']} filtered out)"
        )

        if metrics['removed_count'] > 0:
            logger.info(f"Removal breakdown:")
            for category, count in removal_reasons.items():
                if count > 0:
                    logger.info(f"  - {category}: {count}")

        return filtered, metrics

    def detect_spa_hash_routing(self, url: str, driver: Driver = None) -> Optional[dict]:
        """Detect and parse SPA hash routing patterns for API operations.

        FIX #13: SPA hash routing detection for sites like MISO that use
        #api=pricing-api&operation=get-v1-day-ahead-date-lmp-expost patterns.

        Args:
            url: URL to analyze (may contain hash fragment)
            driver: Optional Botasaurus Driver for dynamic inspection

        Returns:
            Dict with:
              - pattern_type: "api_operation", "api_endpoint", "unknown"
              - operations: List of operation names/IDs found
              - base_api: Base API name if detected
            Or None if no SPA pattern detected

        Example:
            >>> url = "https://api.example.com/docs#api=pricing&operation=get-prices"
            >>> result = tool.detect_spa_hash_routing(url)
            >>> print(result['operations'])  # ['get-prices']
        """
        from urllib.parse import urlparse, parse_qs
        import re

        logger.info("=== CHECKING FOR SPA HASH ROUTING ===")

        try:
            parsed = urlparse(url)
            hash_fragment = parsed.fragment

            if not hash_fragment:
                logger.debug("No hash fragment in URL")
                return None

            logger.info(f"Found hash fragment: {hash_fragment}")

            # Pattern 1: MISO-style "api=X&operation=Y"
            if 'api=' in hash_fragment and 'operation=' in hash_fragment:
                parts = dict(param.split('=') for param in hash_fragment.split('&') if '=' in param)
                api_name = parts.get('api', '')
                operation_name = parts.get('operation', '')

                logger.info(f"✅ Detected SPA pattern: API={api_name}, Operation={operation_name}")

                # If we have a driver, try to extract all operations for this API
                operations = [operation_name] if operation_name else []

                if driver:
                    try:
                        # Try to find all operation links in the page
                        logger.info("Extracting all operations from SPA...")
                        result = driver.run_js("""
                            const operations = [];
                            // Look for links with operation= in href
                            const links = document.querySelectorAll('a[href*="operation="]');
                            links.forEach(link => {
                                const href = link.getAttribute('href');
                                const match = href.match(/operation=([^&]+)/);
                                if (match) {
                                    operations.push(match[1]);
                                }
                            });
                            return operations;
                        """)
                        if result and len(result) > 1:
                            operations = result
                            logger.info(f"✅ Found {len(operations)} operations from SPA")
                    except Exception as e:
                        logger.warning(f"Failed to extract operations from SPA: {e}")

                return {
                    "pattern_type": "api_operation",
                    "operations": operations,
                    "base_api": api_name,
                    "base_url": f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                }

            # Pattern 2: Simple hash routing like #/api/endpoint or #api-endpoint
            elif re.search(r'#/?api[/-]', hash_fragment):
                logger.info(f"✅ Detected simple API hash routing: {hash_fragment}")
                # Extract segments
                segments = re.split(r'[/-]', hash_fragment.strip('#'))
                return {
                    "pattern_type": "api_endpoint",
                    "operations": segments,
                    "base_api": None,
                    "base_url": f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                }

            else:
                logger.debug(f"Hash fragment doesn't match known SPA patterns: {hash_fragment}")
                return None

        except Exception as e:
            logger.error(f"Error detecting SPA hash routing: {e}")
            return None

    def try_fetch_api_spec(self, url: str) -> Optional[dict]:
        """Attempt to fetch and parse API specification.

        FIX #11: Phase 3 - Direct Swagger/OpenAPI/WADL spec parsing

        Tries multiple spec formats and locations to achieve 100% endpoint discovery.
        This is the most reliable method for API documentation sites.

        Args:
            url: Base URL of API documentation

        Returns:
            Dict with:
              - spec_type: "openapi3", "swagger2", "wadl"
              - endpoints: List of endpoint URLs
              - spec_url: URL where spec was found
            Or None if no spec found

        Example:
            >>> spec_data = tool.try_fetch_api_spec("https://api.example.com/docs")
            >>> if spec_data:
            >>>     print(f"Found {len(spec_data['endpoints'])} endpoints")
        """
        logger.info("=== PHASE 3: ATTEMPTING API SPEC PARSING ===")
        logger.info(f"Trying to fetch API specification from: {url}")

        try:
            # Step 1: Find candidate spec URLs
            candidates = self._find_spec_urls(url)
            logger.info(f"Found {len(candidates)} candidate spec URLs to try")

            # Step 2: Try fetching each candidate
            for spec_url in candidates:
                try:
                    logger.debug(f"Trying: {spec_url}")

                    # Fetch with requests (faster than browser)
                    import requests
                    response = requests.get(spec_url, timeout=10, allow_redirects=True)

                    if response.status_code != 200:
                        logger.debug(f"  ❌ HTTP {response.status_code}")
                        continue

                    # Determine format from content-type or URL
                    content_type = response.headers.get('content-type', '').lower()

                    if 'json' in content_type or spec_url.endswith('.json'):
                        # Parse JSON (OpenAPI/Swagger)
                        try:
                            spec_data = response.json()
                            endpoints = self._parse_openapi_spec(spec_data)

                            if not endpoints:
                                logger.debug(f"  ❌ No endpoints in spec")
                                continue

                            # Determine version
                            if "openapi" in spec_data:
                                spec_type = "openapi3"
                            elif "swagger" in spec_data:
                                spec_type = "swagger2"
                            else:
                                logger.debug(f"  ❌ Unknown JSON spec format")
                                continue

                            logger.info(f"✅ Found {spec_type} spec with {len(endpoints)} endpoints at: {spec_url}")

                            return {
                                "spec_type": spec_type,
                                "endpoints": endpoints,
                                "spec_url": spec_url
                            }

                        except Exception as json_error:
                            logger.debug(f"  ❌ JSON parse error: {json_error}")
                            continue

                    elif 'xml' in content_type or 'wadl' in spec_url.lower() or spec_url.endswith('.wadl'):
                        # Parse WADL
                        try:
                            endpoints = self._parse_wadl_spec(response.text)

                            if not endpoints:
                                logger.debug(f"  ❌ No endpoints in WADL")
                                continue

                            logger.info(f"✅ Found WADL spec with {len(endpoints)} endpoints at: {spec_url}")

                            return {
                                "spec_type": "wadl",
                                "endpoints": endpoints,
                                "spec_url": spec_url
                            }

                        except Exception as wadl_error:
                            logger.debug(f"  ❌ WADL parse error: {wadl_error}")
                            continue

                except Exception as e:
                    logger.debug(f"  ❌ Failed to fetch {spec_url}: {e}")
                    continue

            logger.info("❌ No API specification found")
            return None

        except Exception as e:
            logger.error(f"Error in spec parsing: {e}", exc_info=True)
            return None

    def _find_spec_urls(self, base_url: str) -> list[str]:
        """Find possible spec file URLs.

        Args:
            base_url: Base URL of API documentation

        Returns:
            List of URLs to try, in priority order
        """
        from urllib.parse import urljoin, urlparse

        candidates = []
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        # OpenAPI 3.0 common paths
        candidates.extend([
            urljoin(base_url, "/openapi.json"),
            urljoin(base_url, "/openapi.yaml"),
            urljoin(base_url, "/api-docs"),
            urljoin(base, "/openapi.json"),
            urljoin(base, "/api/openapi.json"),
        ])

        # Swagger 2.0 common paths
        candidates.extend([
            urljoin(base_url, "/swagger.json"),
            urljoin(base_url, "/v2/api-docs"),
            urljoin(base, "/api/swagger.json"),
            urljoin(base, "/swagger.json"),
        ])

        # WADL common patterns
        candidates.extend([
            base_url + "?_wadl",
            base_url + "?_wadl&_type=xml",
            urljoin(base, "/application.wadl"),
        ])

        # For URLs with /docs or /api paths, try spec at parent level
        if '/docs' in base_url or '/api' in base_url:
            parent_url = '/'.join(base_url.rstrip('/').split('/')[:-1])
            candidates.extend([
                parent_url + "?_wadl",
                urljoin(parent_url, "/openapi.json"),
                urljoin(parent_url, "/swagger.json"),
            ])

        # If URL has /api/v1.1 pattern, try at /api level
        if '/api/v' in base_url:
            api_base = base_url.split('/api/')[0] + '/api'
            candidates.extend([
                api_base + "?_wadl",
                urljoin(api_base, "/openapi.json"),
            ])

        # Remove duplicates while preserving order
        seen = set()
        unique_candidates = []
        for url in candidates:
            if url not in seen:
                seen.add(url)
                unique_candidates.append(url)

        return unique_candidates

    def _parse_openapi_spec(self, spec_data: dict) -> list[str]:
        """Parse OpenAPI 3.0 or Swagger 2.0 spec.

        Args:
            spec_data: Parsed JSON spec

        Returns:
            List of full endpoint URLs
        """
        endpoints = []

        try:
            # Determine spec version
            is_openapi3 = "openapi" in spec_data

            # Get base URL
            if is_openapi3:
                # OpenAPI 3.0: servers array
                servers = spec_data.get("servers", [])
                base_url = servers[0]["url"] if servers else ""
            else:
                # Swagger 2.0: host + basePath
                scheme = spec_data.get("schemes", ["https"])[0]
                host = spec_data.get("host", "")
                base_path = spec_data.get("basePath", "")
                base_url = f"{scheme}://{host}{base_path}"

            # Extract paths
            paths = spec_data.get("paths", {})
            for path in paths.keys():
                # Construct full URL
                full_url = base_url.rstrip('/') + path
                endpoints.append(full_url)

            logger.debug(f"Parsed {len(endpoints)} endpoints from OpenAPI spec")

        except Exception as e:
            logger.error(f"Failed to parse OpenAPI spec: {e}")
            return []

        return endpoints

    def _parse_wadl_spec(self, wadl_xml: str) -> list[str]:
        """Parse WADL XML specification with lenient error handling.

        FIX #12: Lenient XML parsing to handle malformed WADLs

        Tries multiple parsing strategies:
        1. Standard ET.fromstring (strict)
        2. Lenient parsing up to error point
        3. Regex extraction as fallback

        Args:
            wadl_xml: Raw WADL XML string

        Returns:
            List of full endpoint URLs
        """
        endpoints = []

        try:
            import xml.etree.ElementTree as ET
            import re

            # Strategy 1: Try standard parsing first
            try:
                root = ET.fromstring(wadl_xml)
                endpoints = self._extract_wadl_endpoints(root)
                if endpoints:
                    logger.debug(f"Parsed {len(endpoints)} endpoints from WADL (strict parsing)")
                    return endpoints
            except ET.ParseError as e:
                logger.warning(f"Strict XML parsing failed: {e}")
                # Continue to lenient strategies

            # Strategy 2: Try lenient parsing - extract partial XML up to error
            try:
                # Extract the error position from ParseError message
                error_msg = str(e)
                line_match = re.search(r'line (\d+)', error_msg)
                if line_match:
                    error_line = int(line_match.group(1))
                    # Take lines up to error point
                    lines = wadl_xml.split('\n')
                    partial_xml = '\n'.join(lines[:error_line-1])

                    # Try to close any open tags
                    partial_xml += '\n</resources>\n</application>'

                    try:
                        root = ET.fromstring(partial_xml)
                        endpoints = self._extract_wadl_endpoints(root)
                        if endpoints:
                            logger.info(f"✅ Extracted {len(endpoints)} endpoints from partial WADL (lenient parsing)")
                            return endpoints
                    except:
                        pass  # Continue to regex fallback

            except Exception:
                pass  # Continue to regex fallback

            # Strategy 3: Regex fallback - extract resource paths directly
            logger.info("Trying regex extraction from malformed WADL...")

            # Extract base URL
            base_url = ''
            base_match = re.search(r'<resources[^>]+base="([^"]+)"', wadl_xml)
            if base_match:
                base_url = base_match.group(1)
                logger.debug(f"Found base URL: {base_url}")

            # Extract resource paths
            # Pattern: <resource path="/some/path" ...> or <wadl:resource path="/some/path" ...>
            path_pattern = r'<(?:wadl:)?resource[^>]+path="([^"]+)"'
            paths = re.findall(path_pattern, wadl_xml)

            for path in paths:
                if path and path.startswith('/'):
                    full_url = base_url.rstrip('/') + path
                    endpoints.append(full_url)

            if endpoints:
                logger.info(f"✅ Extracted {len(endpoints)} endpoints using regex (fallback)")
                return endpoints

            logger.warning("No endpoints extracted from WADL using any strategy")

        except Exception as e:
            logger.error(f"Failed to parse WADL: {e}")
            return []

        return endpoints

    def _extract_wadl_endpoints(self, root) -> list[str]:
        """Extract endpoints from parsed WADL XML root.

        Args:
            root: ET.Element root of parsed XML

        Returns:
            List of full endpoint URLs
        """
        endpoints = []

        # WADL namespace
        ns = {'wadl': 'http://wadl.dev.java.net/2009/02'}

        # Find resources element with base URL
        resources = root.find('.//wadl:resources', ns)
        base_url = resources.get('base', '') if resources is not None else ''

        # If no namespace match, try without namespace
        if not resources:
            resources = root.find('.//resources')
            base_url = resources.get('base', '') if resources is not None else ''

        # Find all resource elements
        for resource in root.findall('.//wadl:resource', ns):
            path = resource.get('path', '')
            if path:
                full_url = base_url.rstrip('/') + path
                endpoints.append(full_url)

        # If namespace didn't work, try without
        if not endpoints:
            for resource in root.findall('.//resource'):
                path = resource.get('path', '')
                if path:
                    full_url = base_url.rstrip('/') + path
                    endpoints.append(full_url)

        return endpoints
