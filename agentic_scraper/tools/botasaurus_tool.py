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
from botasaurus_driver.cdp import network
from markdownify import markdownify as md

from agentic_scraper.utils.profiling import profile_time

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
        >>> events = tool.extract_network_events("https://portal.example.com")
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

    def extract_network_events(self, url: str) -> list[dict]:
        """Extract network events from page load.

        Args:
            url: URL to navigate to and monitor

        Returns:
            List of network event dicts with at least:
            - url: resource URL
            - initiator_type: Performance API initiatorType (e.g., fetch, xmlhttprequest)
            - trigger: capture context (currently always "page_load")
        """
        logger.info(f"Extracting network events from {url}")

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

            # Filter for likely API/data calls and return event dicts
            events: list[dict] = []
            seen_urls = set()
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
                    if url_str in seen_urls:
                        continue
                    seen_urls.add(url_str)
                    events.append(
                        {
                            "url": url_str,
                            "initiator_type": log.get("type", "unknown"),
                            "trigger": "page_load",
                        }
                    )

            logger.info(f"Extracted {len(events)} network events")
            return events

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

    @profile_time("Botasaurus: Extract comprehensive data")
    def extract_comprehensive_data(self, url: str) -> dict:
        """Extract EVERYTHING needed for AI-based endpoint discovery.

        This method performs comprehensive extraction to support AI-first discovery:
        1. Renders JavaScript-heavy pages fully
        2. Expands ALL collapsible sections (reveals hidden endpoints)
        3. Extracts navigation/menu links
        4. Captures network events
        5. Gets full page text content
        6. Takes screenshot for visual verification

        Args:
            url: URL to analyze

        Returns:
            Dictionary containing:
            - full_text: Complete page text content (after expansion)
            - markdown: HTML converted to markdown (preserves structure)
            - navigation_links: All nav/menu links with text and href
            - network_events: Captured network events (dicts with at least `url`)
            - expanded_sections: Count of sections expanded
            - screenshot: Path to screenshot file (or None)
            - extraction_error: None if successful, error message if failed (FIX: Issue #2)

        Example:
            >>> tool = BotasaurusTool()
            >>> data = tool.extract_comprehensive_data("https://api.example.com/docs")
            >>> if data.get('extraction_error'):
            >>>     print(f"Extraction failed: {data['extraction_error']}")
            >>> else:
            >>>     print(f"Found {len(data['navigation_links'])} navigation links")
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

            # Step 3: Extract network events
            network_events = self._extract_network_events_internal(driver)
            logger.info(f"Found {len(network_events)} network events")

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

            # Step 5: Take full-page screenshot with scrolling
            screenshot_path = None
            try:
                import os
                import hashlib
                from datetime import datetime

                # Generate unique filename using URL hash + timestamp
                url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{url_hash}_{timestamp}.png"

                os.makedirs("datasource_analysis", exist_ok=True)
                screenshot_path = os.path.join("datasource_analysis", filename)

                # Capture full-page screenshot (not just viewport)
                try:
                    # Get full page dimensions
                    total_width = driver.execute_script("return document.body.scrollWidth")
                    total_height = driver.execute_script("return document.body.scrollHeight")

                    # Set window size to full page dimensions
                    # Note: This works better than scrolling + stitching for most pages
                    original_size = driver.get_window_size()
                    driver.set_window_size(max(total_width, 1920), total_height)

                    # Small delay for rendering at new size
                    time.sleep(0.5)

                    # Capture full page
                    driver.save_screenshot(screenshot_path)

                    # Restore original window size
                    driver.set_window_size(original_size['width'], original_size['height'])

                    logger.info(f"Full-page screenshot saved: {screenshot_path} ({total_width}x{total_height}px)")
                except Exception as e:
                    logger.warning(f"Full-page capture failed, falling back to viewport: {e}")
                    # Fallback: viewport-only screenshot
                    driver.save_screenshot(screenshot_path)
                    logger.info(f"Viewport screenshot saved: {screenshot_path}")

                # Compress screenshot if it exceeds size limit
                self._compress_screenshot(screenshot_path)
            except Exception as e:
                logger.warning(f"Could not save screenshot: {e}")

            # Step 6: Extract website-specific data (shadow DOM, late calls, buttons, hints)
            # This enhances prompts with additional context for better classification
            shadow_dom_text = ""
            custom_element_hints = []
            late_api_calls = []
            download_buttons = []

            try:
                logger.debug("Extracting shadow DOM data...")
                shadow_data = self._extract_shadow_dom_data(driver)
                shadow_dom_text = shadow_data['text']
                custom_element_hints = shadow_data['hints']
                logger.debug(f"Found {len(shadow_data['hints'])} custom element hints, {len(shadow_dom_text)} chars shadow DOM text")

                logger.debug("Capturing late network calls...")
                late_api_calls = self._capture_late_network_calls(driver, wait_seconds=5)  # Shorter wait for regular extraction
                logger.debug(f"Captured {len(late_api_calls)} late API calls")

                logger.debug("Extracting download buttons...")
                download_buttons = self._extract_download_buttons(driver, url)
                logger.debug(f"Found {len(download_buttons)} download buttons")

            except Exception as e:
                logger.warning(f"Website-specific extraction failed (non-critical): {e}")

            return {
                "full_text": full_text,
                "markdown": markdown_content,
                "navigation_links": nav_links,
                "network_events": network_events,
                "expanded_sections": expanded_count,
                "screenshot": screenshot_path,
                "extraction_error": None,  # FIX: Issue #2 - No error
                # Website-specific data for enhanced prompt context
                "shadow_dom_text": shadow_dom_text,
                "custom_element_hints": custom_element_hints,
                "late_api_calls": late_api_calls,
                "download_buttons": download_buttons
            }

        except Exception as e:
            # FIX: Issue #2 - Use WARNING instead of ERROR (graceful degradation, not crash)
            # Provide specific error message for actionable debugging
            error_msg = f"{type(e).__name__}: {str(e)[:200]}"
            logger.warning(f"❌ Comprehensive extraction FAILED - Analysis will be unreliable!")
            logger.warning(f"Error type: {type(e).__name__}")
            logger.warning(f"Error message: {str(e)[:200]}")
            logger.warning("⚠️  Returning empty data - Phase 0 analysis should detect this and abort")
            logger.debug(f"Full traceback:", exc_info=True)  # Full trace at DEBUG level

            # Return empty structure with error indicator
            return {
                "full_text": "",
                "markdown": "",
                "navigation_links": [],
                "network_events": [],
                "expanded_sections": 0,
                "screenshot": None,
                "extraction_error": error_msg  # FIX: Issue #2 - Error indicator for caller
            }
        finally:
            if driver:
                try:
                    driver.close()
                    logger.debug("Driver closed")
                except Exception as e:
                    logger.warning(f"Failed to close driver: {e}")

    @profile_time("Botasaurus: Interact and capture")
    def interact_and_capture(self, url: str, actions: list[dict]) -> dict:
        """Execute UI interactions and capture resulting network events (E1).

        Performs deterministic UI actions (click, type, select, scroll) while
        monitoring network traffic. This enables discovery of endpoints triggered
        by user interactions (filters, pagination, exports, etc.).

        Supported action types:
        - click: Click element by CSS selector or text content
        - type: Type text into an input field
        - select: Select option from dropdown
        - scroll: Scroll to element or by offset
        - wait: Wait for specified milliseconds

        Args:
            url: URL to navigate to before executing actions
            actions: List of action dicts, each with:
                - action: "click" | "type" | "select" | "scroll" | "wait"
                - selector: CSS selector (optional for text-based click)
                - text: Text to type or text content to click on
                - value: Value to select or scroll offset
                - wait_after: Milliseconds to wait after action (default: 500)

        Returns:
            Dictionary containing:
            - network_events: List of network events captured during interactions
            - actions_executed: Count of successfully executed actions
            - errors: List of action errors (non-fatal)
            - markdown: Page markdown content after interactions

        Example:
            >>> tool = BotasaurusTool()
            >>> result = tool.interact_and_capture(
            ...     "https://portal.example.com/data",
            ...     [
            ...         {"action": "click", "selector": "#search-btn"},
            ...         {"action": "type", "selector": "#date-input", "text": "2024-01-15"},
            ...         {"action": "click", "selector": ".submit-btn"},
            ...         {"action": "wait", "value": 2000}
            ...     ]
            ... )
            >>> print(f"Captured {len(result['network_events'])} new API calls")
        """
        logger.info(f"Interact and capture: {url} with {len(actions)} actions")

        driver = None
        captured_events: list[dict] = []
        actions_executed = 0
        errors: list[str] = []

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

            # Wait for initial load
            driver.sleep(3)

            # Capture baseline network events
            baseline_urls = set()
            try:
                baseline_logs = driver.run_js("""
                    const entries = performance.getEntriesByType('resource');
                    return entries.map(e => e.name);
                """)
                baseline_urls = set(baseline_logs)
                logger.debug(f"Baseline: {len(baseline_urls)} network requests")
            except Exception as e:
                logger.warning(f"Could not capture baseline: {e}")

            # Execute each action
            for i, action_def in enumerate(actions):
                action_type = action_def.get('action', 'unknown')
                selector = action_def.get('selector', '')
                text = action_def.get('text', '')
                value = action_def.get('value', '')
                wait_after = action_def.get('wait_after', 500)

                logger.debug(f"Action {i+1}: {action_type} selector={selector} text={text[:20] if text else ''}")

                try:
                    if action_type == 'click':
                        if selector:
                            # Click by CSS selector
                            driver.run_js(f"""
                                const el = document.querySelector('{selector}');
                                if (el) {{ el.click(); return true; }}
                                return false;
                            """)
                        elif text:
                            # Click by text content
                            escaped_text = text.replace("'", "\\'")
                            driver.run_js(f"""
                                const elements = Array.from(document.querySelectorAll('button, a, [role="button"], input[type="submit"]'));
                                const target = elements.find(el => el.textContent.includes('{escaped_text}'));
                                if (target) {{ target.click(); return true; }}
                                return false;
                            """)
                        actions_executed += 1

                    elif action_type == 'type':
                        if selector and text:
                            escaped_text = text.replace("'", "\\'")
                            driver.run_js(f"""
                                const el = document.querySelector('{selector}');
                                if (el) {{
                                    el.focus();
                                    el.value = '{escaped_text}';
                                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    return true;
                                }}
                                return false;
                            """)
                            actions_executed += 1

                    elif action_type == 'select':
                        if selector and value:
                            escaped_value = value.replace("'", "\\'")
                            driver.run_js(f"""
                                const el = document.querySelector('{selector}');
                                if (el) {{
                                    el.value = '{escaped_value}';
                                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    return true;
                                }}
                                return false;
                            """)
                            actions_executed += 1

                    elif action_type == 'scroll':
                        if selector:
                            driver.run_js(f"""
                                const el = document.querySelector('{selector}');
                                if (el) {{ el.scrollIntoView({{ behavior: 'smooth' }}); return true; }}
                                return false;
                            """)
                        elif value:
                            driver.run_js(f"window.scrollBy(0, {value});")
                        actions_executed += 1

                    elif action_type == 'wait':
                        wait_ms = int(value) if value else 1000
                        driver.sleep(wait_ms / 1000)
                        actions_executed += 1

                    # Wait after action for network requests to complete
                    if wait_after > 0:
                        driver.sleep(wait_after / 1000)

                except Exception as e:
                    error_msg = f"Action {i+1} ({action_type}) failed: {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            # Capture new network events after interactions
            try:
                current_logs = driver.run_js("""
                    const entries = performance.getEntriesByType('resource');
                    return entries.map(e => ({
                        url: e.name,
                        type: e.initiatorType
                    }));
                """)

                seen_urls = set()
                for log in current_logs:
                    url_str = log['url']
                    if url_str in baseline_urls or url_str in seen_urls:
                        continue  # Skip baseline and duplicates

                    # Filter for likely API/data calls
                    if (
                        '/api/' in url_str or
                        url_str.endswith('.json') or
                        url_str.endswith('.xml') or
                        (log['type'] in ['fetch', 'xmlhttprequest']) or
                        ('http' in url_str and
                         not url_str.endswith(('.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf')))
                    ):
                        seen_urls.add(url_str)
                        captured_events.append({
                            "url": url_str,
                            "initiator_type": log.get("type", "unknown"),
                            "trigger": "interaction_script",
                        })

                logger.info(f"Captured {len(captured_events)} new network events after interactions")

            except Exception as e:
                logger.warning(f"Could not capture network events: {e}")

            # Get page content after interactions
            markdown_content = ""
            try:
                html = driver.run_js("return document.documentElement.outerHTML;")
                markdown_content = md(
                    html,
                    heading_style="ATX",
                    bullets="-",
                    strip=['script', 'style', 'meta', 'link']
                )
            except Exception as e:
                logger.warning(f"Could not extract markdown: {e}")

            return {
                "network_events": captured_events,
                "actions_executed": actions_executed,
                "errors": errors,
                "markdown": markdown_content[:50000] if markdown_content else "",  # Cap at 50K
            }

        except Exception as e:
            logger.error(f"Interact and capture failed: {e}", exc_info=True)
            return {
                "network_events": [],
                "actions_executed": 0,
                "errors": [str(e)],
                "markdown": "",
            }
        finally:
            if driver:
                try:
                    driver.close()
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

    def _is_valid_data_url(self, url: str, base_url: str | None = None) -> bool:
        """Check if URL looks like a data endpoint/file (not navigation chrome).

        Args:
            url: URL to validate
            base_url: Base URL of the site (for domain checking)

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

        # FIX Phase 2: Check domain for external URLs (block Wikipedia, MDN, etc.)
        if url.startswith('http') and base_url:
            from urllib.parse import urlparse
            base_domain = urlparse(base_url).netloc
            url_domain = urlparse(url).netloc

            # Reject external domains
            if url_domain != base_domain:
                logger.debug(f"Rejecting external domain: {url_domain} != {base_domain}")
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

        # If full URL with http/https, require API indicators
        # (Prevents accepting generic external URLs)
        if url.startswith('http'):
            return any(indicator in url_lower for indicator in
                      ['/api/', '/v1/', '/v2/', '/v3/', '/rest/', '/data/'])

        return False

    def _score_url_quality(self, url: str, operation_name: str) -> float:
        """Score URL quality for being an actual API endpoint (0-1).

        FIX Phase 4: URL quality scoring to filter out low-quality URLs

        Higher scores = more likely to be a real API endpoint.
        Used to filter out garbage URLs (Wikipedia, documentation, etc.)

        Args:
            url: URL to score
            operation_name: Operation name associated with the URL

        Returns:
            Quality score from 0.0 (definitely not an endpoint) to 1.0 (definitely an endpoint)
        """
        score = 0.5  # Base score
        url_lower = url.lower()
        op_name_lower = operation_name.lower()

        # Strong positive indicators
        if '/api/' in url_lower:
            score += 0.3
        if any(v in url_lower for v in ['/v1/', '/v2/', '/v3/']):
            score += 0.2
        if '/rest/' in url_lower:
            score += 0.2
        if 'operation=' in url_lower:
            score += 0.3
        if any(url_lower.endswith(ext) for ext in ['.json', '.xml']):
            score += 0.2

        # Positive indicators
        if '/data/' in url_lower:
            score += 0.1
        if len(operation_name.split()) >= 3:  # Multi-word = descriptive
            score += 0.1

        # Negative indicators (red flags)
        if 'wikipedia.org' in url_lower:
            score -= 1.0
        if '/docs/' in url_lower or '/documentation/' in url_lower:
            score -= 0.3
        if any(term in op_name_lower for term in ['wadl', 'json', 'xml', 'rest', 'swagger', 'openapi']):
            score -= 0.5
        if any(pattern in url_lower for pattern in ['/about', '/help', '/guide', '/tutorial']):
            score -= 0.4

        return max(0.0, min(1.0, score))

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
        # FIX: Issue #4 - Track diagnostics for better error reporting
        diagnostics = {
            'selectors_tried': 0,
            'elements_found': 0,
            'elements_checked': 0
        }

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
                diagnostics['selectors_tried'] += 1
                try:
                    elements = driver.select_all(selector, wait=None)
                    if elements:
                        diagnostics['elements_found'] += len(elements)

                    for elem in elements:
                        diagnostics['elements_checked'] += 1
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

            # FIX: Issue #4 - Provide diagnostic info at INFO level when nothing found
            logger.info(f"    ❌ Could not extract endpoint URL from Swagger DOM for '{op_name}'")
            logger.info(f"    Diagnostics:")
            logger.info(f"      - Selectors tried: {diagnostics['selectors_tried']}")
            logger.info(f"      - Elements found: {diagnostics['elements_found']}")
            logger.info(f"      - Elements checked: {diagnostics['elements_checked']}")
            logger.info(f"    Troubleshooting:")
            logger.info(f"      - Page may not be Swagger/OpenAPI UI")
            logger.info(f"      - Operation details may not be visible yet (wait longer)")
            logger.info(f"      - DOM structure may have changed (update selectors)")
            return None

        except Exception as e:
            # FIX: Issue #4 - Log failures at INFO level with context
            logger.info(f"    ❌ DOM extraction failed for '{op_name}': {type(e).__name__}")
            logger.info(f"    Error: {str(e)[:100]}")
            logger.debug(f"    Full traceback:", exc_info=True)
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

    def _extract_network_events_internal(self, driver: Driver) -> list[dict]:
        """Extract network events (internal method for use with existing driver).

        Args:
            driver: Botasaurus Driver instance

        Returns:
            List of network event dicts with at least {url, initiator_type, trigger}.
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

            # Filter for likely API/data calls
            events: list[dict] = []
            seen_urls = set()
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
                    if url_str in seen_urls:
                        continue
                    seen_urls.add(url_str)
                    events.append(
                        {
                            "url": url_str,
                            "initiator_type": log.get("type", "unknown"),
                            "trigger": "page_load",
                        }
                    )

            return events

        except Exception as e:
            logger.warning(f"Failed to extract network events: {e}")
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

    def _safe_get_hash(self, driver: Driver) -> str:
        """Safely get window.location.hash with error handling.

        FIX: Issue #5 - JavaScript execute_script can fail due to:
        - CORS restrictions
        - Security policies
        - Page not fully loaded
        - Browser context issues

        Args:
            driver: Botasaurus Driver instance

        Returns:
            Hash string (e.g., "#/api/endpoint") or empty string on error
        """
        try:
            hash_value = driver.execute_script("return window.location.hash")
            return hash_value if hash_value else ""
        except Exception as e:
            # Log at INFO level - this is expected on some pages
            logger.info(f"    ⚠️  Could not access window.location.hash: {type(e).__name__}")
            logger.debug(f"    Error details: {str(e)[:100]}")
            return ""

    @profile_time("Botasaurus: Extract operation URLs")
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

                                # FIX Phase 2: Pass base_url for domain validation
                                # FIX Phase 4: Add quality scoring to filter garbage URLs
                                if href and self._is_valid_data_url(href, url):
                                    quality = self._score_url_quality(href, op_name)
                                    logger.debug(f"  URL quality score: {quality:.2f} for {href}")

                                    if quality >= 0.5:  # Quality threshold
                                        logger.debug(f"  ✅ Extracted href (quality={quality:.2f}): {href}")
                                        operation_urls[op_name] = href
                                        found = True
                                        break
                                    else:
                                        logger.debug(f"  ❌ Rejected low-quality URL (quality={quality:.2f}): {href}")

                                # Strategy 2: Try clicking to see if URL changes
                                original_url = driver.current_url
                                # FIX: Issue #5 - Use safe wrapper to avoid JavaScript errors
                                original_hash = self._safe_get_hash(driver)

                                try:
                                    link.click()
                                    driver.sleep(2)  # Wait for navigation

                                    new_url = driver.current_url
                                    # FIX: Issue #5 - Use safe wrapper to avoid JavaScript errors
                                    new_hash = self._safe_get_hash(driver)

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

    @profile_time("Botasaurus: Fetch API spec")
    def try_fetch_api_spec(
        self,
        url: str,
        auth_username: str | None = None,
        auth_password: str | None = None,
        discovered_spec_links: list | None = None
    ) -> Optional[dict]:
        """Attempt to fetch and parse API specification with optional authentication.

        FIX #11: Phase 3 - Direct Swagger/OpenAPI/WADL spec parsing
        FIX Phase 3a: Add HTTP Basic Auth support for protected specs
        FIX: Try actual spec links found on page FIRST before constructing URLs

        Tries multiple spec formats and locations to achieve 100% endpoint discovery.
        This is the most reliable method for API documentation sites.

        Args:
            url: Base URL of API documentation
            auth_username: Optional HTTP Basic Auth username
            auth_password: Optional HTTP Basic Auth password
            discovered_spec_links: List of (spec_type, href, text) tuples found on page

        Returns:
            Dict with:
              - spec_type: "openapi3", "swagger2", "wadl", or "auth_required"
              - endpoints: List of endpoint URLs (or empty if auth_required)
              - spec_url: URL where spec was found
              - requires_auth: True if 401 detected
            Or None if no spec found

        Example:
            >>> spec_data = tool.try_fetch_api_spec("https://api.example.com/docs")
            >>> if spec_data:
            >>>     print(f"Found {len(spec_data['endpoints'])} endpoints")

            >>> # With authentication
            >>> spec_data = tool.try_fetch_api_spec(
            ...     "https://api.example.com/docs",
            ...     auth_username="user",
            ...     auth_password="pass"
            ... )
        """
        logger.info("=== PHASE 3: ATTEMPTING API SPEC PARSING ===")
        logger.info(f"Trying to fetch API specification from: {url}")

        # FIX: Track failure categories for actionable error reporting
        failure_categories = {
            'auth': [],      # 401, 403 errors
            'network': [],   # Connection, timeout errors
            'parse': [],     # Malformed JSON/XML
            'empty': [],     # Valid format but no endpoints
            'http': []       # Other HTTP errors (404, 500, etc.)
        }

        try:
            # Step 1: Find candidate spec URLs
            # FIX: Try discovered spec links FIRST before constructing URLs
            if discovered_spec_links:
                logger.info(f"=== TRYING {len(discovered_spec_links)} SPEC LINKS FOUND ON PAGE ===")
                from urllib.parse import urljoin
                candidates = []
                for spec_type, href, text in discovered_spec_links:
                    full_url = urljoin(url, href)
                    candidates.append(full_url)
                    logger.info(f"  Found {spec_type} link: {full_url} (text: '{text}')")

                # Add constructed URLs as fallback
                constructed_urls = self._find_spec_urls(url)
                logger.info(f"  Plus {len(constructed_urls)} constructed fallback URLs")
                candidates.extend(constructed_urls)
            else:
                # No discovered links, use constructed URLs
                candidates = self._find_spec_urls(url)
                logger.info(f"Found {len(candidates)} candidate spec URLs to try")

            # Step 2: Try fetching each candidate
            for spec_url in candidates:
                try:
                    logger.debug(f"Trying: {spec_url}")

                    # FIX Phase 3a: Use HTTP Basic Auth if provided
                    import requests
                    from requests.auth import HTTPBasicAuth

                    auth = None
                    if auth_username and auth_password:
                        auth = HTTPBasicAuth(auth_username, auth_password)
                        logger.debug(f"  Using HTTP Basic Auth for: {auth_username}")

                    response = requests.get(spec_url, auth=auth, timeout=10, allow_redirects=True)

                    if response.status_code != 200:
                        logger.debug(f"  ❌ HTTP {response.status_code}")
                        # Categorize HTTP errors
                        if response.status_code in [401, 403]:
                            failure_categories['auth'].append((spec_url, response.status_code))
                            if response.status_code == 401 and not auth:
                                logger.error(f"🚫 STOPPING: API requires authentication")
                                logger.error(f"   Spec URL returned 401: {spec_url}")
                                logger.error(f"   Cannot proceed without credentials")
                                logger.error(f"   Set API_SPEC_AUTH_USER and API_SPEC_AUTH_PASS to retry")
                                # Return early - don't waste time clicking operations that will also 401
                                return {
                                    "spec_type": "auth_required",
                                    "endpoints": [],
                                    "spec_url": spec_url,
                                    "requires_auth": True
                                }
                            elif response.status_code == 403:
                                logger.info(f"📋 Access forbidden: {spec_url}")
                                logger.info(f"   HTTP 403 Forbidden - May require different credentials or permissions")
                        else:
                            failure_categories['http'].append((spec_url, response.status_code))
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
                                failure_categories['empty'].append((spec_url, 'JSON spec has no endpoints'))
                                continue

                            # Determine version
                            if "openapi" in spec_data:
                                spec_type = "openapi3"
                            elif "swagger" in spec_data:
                                spec_type = "swagger2"
                            else:
                                logger.debug(f"  ❌ Unknown JSON spec format")
                                failure_categories['parse'].append((spec_url, 'Unknown JSON format (not OpenAPI/Swagger)'))
                                continue

                            logger.info(f"✅ Found {spec_type} spec with {len(endpoints)} endpoints at: {spec_url}")

                            return {
                                "spec_type": spec_type,
                                "endpoints": endpoints,
                                "spec_url": spec_url
                            }

                        except Exception as json_error:
                            logger.debug(f"  ❌ JSON parse error: {json_error}")
                            failure_categories['parse'].append((spec_url, f'JSON parse: {str(json_error)[:100]}'))
                            continue

                    elif 'xml' in content_type or 'wadl' in spec_url.lower() or spec_url.endswith('.wadl'):
                        # Parse WADL
                        try:
                            endpoints = self._parse_wadl_spec(response.text)

                            if not endpoints:
                                logger.debug(f"  ❌ No endpoints in WADL")
                                failure_categories['empty'].append((spec_url, 'WADL has no endpoints'))
                                continue

                            logger.info(f"✅ Found WADL spec with {len(endpoints)} endpoints at: {spec_url}")

                            return {
                                "spec_type": "wadl",
                                "endpoints": endpoints,
                                "spec_url": spec_url
                            }

                        except Exception as wadl_error:
                            logger.debug(f"  ❌ WADL parse error: {wadl_error}")
                            failure_categories['parse'].append((spec_url, f'WADL parse: {str(wadl_error)[:100]}'))
                            continue

                except requests.exceptions.Timeout:
                    logger.debug(f"  ❌ Timeout fetching {spec_url}")
                    failure_categories['network'].append((spec_url, 'Timeout (>10s)'))
                    continue
                except requests.exceptions.ConnectionError as e:
                    logger.debug(f"  ❌ Connection error: {e}")
                    failure_categories['network'].append((spec_url, f'Connection error: {str(e)[:50]}'))
                    continue
                except Exception as e:
                    logger.debug(f"  ❌ Failed to fetch {spec_url}: {e}")
                    failure_categories['network'].append((spec_url, str(e)[:100]))
                    continue

            # FIX: Provide categorized failure summary at WARNING level
            logger.warning("❌ No valid API specification found after trying all candidates")
            logger.warning(f"Failure summary:")

            if failure_categories['auth']:
                logger.warning(f"  - {len(failure_categories['auth'])} auth-protected (401/403) - specs require authentication")
                for url, code in failure_categories['auth'][:3]:  # Show first 3
                    logger.warning(f"    • {url} (HTTP {code})")
                if not auth_username:
                    logger.info(f"💡 To enable authenticated spec parsing:")
                    logger.info(f"   export API_SPEC_AUTH_USER='your_username'")
                    logger.info(f"   export API_SPEC_AUTH_PASS='your_password'")
                    logger.info(f"   Then re-run the analysis")
                logger.info(f"   Continuing with REST documentation link extraction as fallback")

            if failure_categories['parse']:
                logger.warning(f"  - {len(failure_categories['parse'])} parse errors - specs may be malformed")
                for url, error in failure_categories['parse'][:3]:
                    logger.warning(f"    • {url}: {error}")

            if failure_categories['empty']:
                logger.warning(f"  - {len(failure_categories['empty'])} empty specs - valid format but no endpoints")
                for url, reason in failure_categories['empty'][:3]:
                    logger.warning(f"    • {url}: {reason}")

            if failure_categories['http']:
                logger.warning(f"  - {len(failure_categories['http'])} HTTP errors - specs not found at standard locations")
                for url, code in failure_categories['http'][:3]:
                    logger.warning(f"    • {url} (HTTP {code})")

            if failure_categories['network']:
                logger.warning(f"  - {len(failure_categories['network'])} network errors - connection/timeout issues")
                for url, error in failure_categories['network'][:3]:
                    logger.warning(f"    • {url}: {error}")

            logger.warning("Will fall back to operation clicking for endpoint discovery")
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

    def _extract_urls_from_json(self, data) -> list[str]:
        """Recursively extract data file URLs from JSON response.

        Searches JSON for URL-like strings in common keys (csv, json, xml, url, href, etc.)
        and recursively processes nested objects and arrays.

        Args:
            data: JSON data (dict, list, or primitive)

        Returns:
            List of discovered URLs
        """
        urls = []

        if isinstance(data, dict):
            # Check for URL fields
            for key in ['csv', 'json', 'xml', 'pdf', 'htm', 'txt', 'xlsx', 'xls',
                       'url', 'href', 'link', 'file', 'path', 'download']:
                if key in data and isinstance(data[key], str):
                    url = data[key]
                    if url and ('.' in url or 'http' in url):
                        urls.append(url)

            # Recursively check nested objects
            for value in data.values():
                urls.extend(self._extract_urls_from_json(value))

        elif isinstance(data, list):
            for item in data:
                urls.extend(self._extract_urls_from_json(item))

        return urls

    def _capture_network_responses_cdp(self, driver) -> list[str]:
        """Use CDP to capture XHR/Fetch response bodies and extract data URLs.

        This is a FAST SHORTCUT for sites like NYISO that pre-cache data in XHR JSON.
        If this returns 0 URLs, fallback to DOM text extraction.

        CDP (Chrome DevTools Protocol) operates at browser engine level, capturing
        network responses BEFORE JavaScript processes them. This allows us to extract
        data URLs from JSON responses that would otherwise require clicking through
        the UI to discover.

        Args:
            driver: Botasaurus Driver instance (must be created, may or may not have navigated yet)

        Returns:
            List of discovered data URLs from XHR/Fetch JSON responses
        """
        captured_responses = []

        def response_handler(request_id, response, event):
            """Callback when network response is received."""
            url = response.url
            # Only capture JSON responses (skip images, CSS, HTML, etc.)
            if response.mime_type and 'json' in response.mime_type.lower():
                captured_responses.append({
                    'request_id': request_id,
                    'url': url,
                    'status': response.status
                })

        try:
            # Enable CDP Network domain
            driver.run_cdp_command(network.enable())

            # Register response handler BEFORE navigation
            driver.after_response_received(response_handler)

            # Wait for page to load and make XHR calls
            driver.sleep(5)

            logger.info(f"CDP captured {len(captured_responses)} JSON responses")

            # Fetch response bodies and extract URLs
            discovered_urls = []
            for item in captured_responses:
                request_id = item['request_id']
                url = item['url']

                try:
                    # Get response body using CDP
                    body, base64_encoded = driver.run_cdp_command(
                        network.get_response_body(request_id)
                    )

                    if not body:
                        continue

                    # Handle base64 encoding
                    if base64_encoded:
                        import base64
                        body = base64.b64decode(body).decode('utf-8')

                    # Parse JSON and extract URLs
                    import json
                    data = json.loads(body)
                    urls = self._extract_urls_from_json(data)
                    discovered_urls.extend(urls)

                    logger.debug(f"Extracted {len(urls)} URLs from {url[:80]}")

                except Exception as e:
                    logger.debug(f"Failed to process response body from {url[:80]}: {e}")

            return list(set(discovered_urls))  # Deduplicate

        except Exception as e:
            logger.warning(f"CDP network capture failed: {e}")
            return []

    def _extract_files_from_dom(self, driver) -> list[str]:
        """Extract data file names/URLs from DOM text using regex patterns.

        This is the FALLBACK method for custom file browsers (SPP pattern) where:
        - Files are NOT standard <a href> links
        - File names appear in <span>, <div>, or other custom elements
        - Pattern: RTBM-BC-latestInterval.csv, data-2024-01-05.json, etc.

        This method searches the entire page text (document.body.textContent) for
        file patterns and also checks for standard anchor links with data file extensions.

        Args:
            driver: Botasaurus Driver instance (must have navigated to page)

        Returns:
            List of file names (prefixed with "FILE:") and full URLs
        """
        try:
            logger.info("Extracting file names from DOM text patterns...")

            # Extract file patterns from page text
            file_data = driver.run_js("""
                const bodyText = document.body.textContent || document.body.innerText || '';

                // Regex patterns for common data file extensions
                const patterns = [
                    /[\\w\\-\\.]+\\.csv/gi,
                    /[\\w\\-\\.]+\\.json/gi,
                    /[\\w\\-\\.]+\\.xml/gi,
                    /[\\w\\-\\.]+\\.xlsx?/gi,
                    /[\\w\\-\\.]+\\.pdf/gi,
                    /[\\w\\-\\.]+\\.txt/gi,
                    /[\\w\\-\\.]+\\.zip/gi
                ];

                const foundFiles = [];

                // Extract file names using regex
                for (const pattern of patterns) {
                    const matches = bodyText.match(pattern);
                    if (matches) {
                        foundFiles.push(...matches);
                    }
                }

                // Also check for standard <a href> links (NYISO pattern after clicking)
                const links = Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(href =>
                        href.includes('.csv') ||
                        href.includes('.json') ||
                        href.includes('.xml') ||
                        href.includes('.xlsx') ||
                        href.includes('.xls') ||
                        href.includes('.pdf') ||
                        href.includes('.txt')
                    );

                return {
                    file_names: [...new Set(foundFiles)],  // Deduplicate
                    file_urls: [...new Set(links)]         // Deduplicate
                };
            """)

            file_names = file_data.get('file_names', [])
            file_urls = file_data.get('file_urls', [])

            logger.info(f"Found {len(file_names)} file names and {len(file_urls)} file URLs in DOM")

            # Combine file names and URLs
            # File URLs are already complete (e.g., https://mis.nyiso.com/public/csv/...csv)
            # File names might need URL reconstruction (e.g., RTBM-BC-latestInterval.csv)
            all_files = file_urls.copy()

            # For file names without full URLs, store them as-is
            # AI filtering will later determine if they're relevant
            for filename in file_names:
                if not filename.startswith('http'):
                    # Mark as filename-only (AI can decide if relevant)
                    all_files.append(f"FILE:{filename}")

            return list(set(all_files))  # Deduplicate

        except Exception as e:
            logger.warning(f"DOM text extraction failed: {e}")
            return []

    def extract_comprehensive_website_data(self, url: str) -> dict:
        """Extract comprehensive data from JavaScript-heavy website portals.

        Designed for WEBSITE-type sources (not API documentation) where:
        - Links may be hidden in dropdowns, shadow DOM, or custom elements
        - Data files (.csv, .json) are direct download links
        - No need for operation clicking (just extract hrefs)

        This method implements a multi-strategy extraction approach:
        1. Extract ALL anchors (visible + hidden) with full metadata
        2. Traverse Shadow DOM and custom elements recursively
        3. Capture late network calls (fetch/XHR) for 5-10s
        4. Extract buttons/tiles with download handlers
        5. Collect custom element hints (attributes like liferaywebdavurl)

        Args:
            url: Website URL to extract from

        Returns:
            Dict with keys:
            - all_links: List of {href, text, aria_label, title, dataset, role, source}
            - data_links: Filtered list of data file download links
            - shadow_dom_text: Text extracted from shadow roots (truncated ~1-2k)
            - custom_element_hints: List of custom element attributes/metadata
            - late_api_calls: URLs captured via fetch/XHR hooks
            - download_buttons: Buttons/tiles with download handlers
            - navigation_text: Combined text for LLM context

        Example:
            >>> tool = BotasaurusTool()
            >>> data = tool.extract_comprehensive_website_data("https://www.nyiso.com/energy-market-operational-data")
            >>> print(len(data['data_links']))  # CSV/JSON download links
            >>> print(data['shadow_dom_text'][:500])  # Shadow root content
        """
        logger.info(f"=== COMPREHENSIVE WEBSITE DATA EXTRACTION ===")
        logger.info(f"Extracting from: {url}")

        driver = None
        result = {
            'all_links': [],
            'data_links': [],
            'shadow_dom_text': '',
            'custom_element_hints': [],
            'late_api_calls': [],
            'download_buttons': [],
            'navigation_text': '',
            'cdp_data_urls': [],  # NEW: URLs from CDP XHR capture
            'dom_files': []       # NEW: Files from DOM text extraction
        }

        # Track CDP responses for extraction later
        captured_responses = []

        def response_handler(request_id, response, event):
            """Callback when network response is received."""
            url_str = response.url
            # Only capture JSON responses (skip images, CSS, HTML, etc.)
            if response.mime_type and 'json' in response.mime_type.lower():
                captured_responses.append({
                    'request_id': request_id,
                    'url': url_str,
                    'status': response.status
                })

        try:
            # Create Driver instance
            driver = Driver(
                headless=True,
                block_images=True,
                wait_for_complete_page_load=True
            )

            # Enable CDP Network domain BEFORE navigation to capture initial XHR calls
            logger.info("Enabling CDP to capture XHR/Fetch responses...")
            try:
                driver.run_cdp_command(network.enable())
                driver.after_response_received(response_handler)
                logger.debug("CDP enabled and response handler registered")
            except Exception as e:
                logger.warning(f"Failed to enable CDP: {e}")

            # Navigate to page
            driver.get(url)
            logger.debug(f"Page loaded: {driver.current_url}")

            # Wait for initial page load and XHR calls
            driver.sleep(5)

            # STEP 1: Extract ALL anchors (visible + hidden) with full metadata
            logger.info("STEP 1: Extracting all anchor links (visible + hidden)...")
            all_links = self._extract_all_links_with_metadata(driver, url)
            result['all_links'] = all_links
            logger.info(f"  ✅ Found {len(all_links)} total links")

            # STEP 2: Traverse Shadow DOM and custom elements
            logger.info("STEP 2: Traversing Shadow DOM and custom elements...")
            shadow_data = self._extract_shadow_dom_data(driver)
            result['shadow_dom_text'] = shadow_data['text']
            result['custom_element_hints'] = shadow_data['hints']
            # Merge shadow DOM links into all_links
            result['all_links'].extend(shadow_data['links'])
            logger.info(f"  ✅ Found {len(shadow_data['links'])} shadow DOM links")
            logger.info(f"  ✅ Found {len(shadow_data['hints'])} custom element hints")
            logger.info(f"  ✅ Extracted {len(shadow_data['text'])} chars of shadow DOM text")

            # STEP 3: Extract URLs from CDP-captured XHR/Fetch responses (NYISO fast path)
            logger.info("STEP 3: Extracting data URLs from CDP-captured XHR responses...")
            cdp_data_urls = []
            if captured_responses:
                logger.info(f"  CDP captured {len(captured_responses)} JSON responses")
                for item in captured_responses:
                    request_id = item['request_id']
                    url_str = item['url']
                    try:
                        # Get response body using CDP
                        body, base64_encoded = driver.run_cdp_command(
                            network.get_response_body(request_id)
                        )
                        if not body:
                            continue
                        # Handle base64 encoding
                        if base64_encoded:
                            import base64
                            body = base64.b64decode(body).decode('utf-8')
                        # Parse JSON and extract URLs
                        import json
                        data = json.loads(body)
                        urls = self._extract_urls_from_json(data)
                        cdp_data_urls.extend(urls)
                        logger.debug(f"  Extracted {len(urls)} URLs from {url_str[:80]}")
                    except Exception as e:
                        logger.debug(f"  Failed to process response body from {url_str[:80]}: {e}")
                cdp_data_urls = list(set(cdp_data_urls))  # Deduplicate
                result['cdp_data_urls'] = cdp_data_urls
                logger.info(f"  ✅ CDP extracted {len(cdp_data_urls)} data URLs from XHR JSON")
            else:
                logger.info(f"  ℹ️  CDP captured 0 JSON responses")

            # STEP 4: If CDP found 0 URLs, fallback to DOM text extraction (SPP fallback)
            if len(cdp_data_urls) == 0:
                logger.info("STEP 4: CDP found 0 URLs, extracting from DOM text patterns...")
                dom_files = self._extract_files_from_dom(driver)
                result['dom_files'] = dom_files
                logger.info(f"  ✅ DOM extraction found {len(dom_files)} files")
            else:
                logger.info("STEP 4: Skipping DOM extraction (CDP already found URLs)")
                result['dom_files'] = []

            # STEP 5: Also capture late API calls (legacy method, still useful)
            logger.info("STEP 5: Capturing late network calls (fetch/XHR URLs)...")
            late_calls = self._capture_late_network_calls(driver, wait_seconds=7)
            result['late_api_calls'] = late_calls
            logger.info(f"  ✅ Captured {len(late_calls)} late network calls")

            # STEP 6: Extract buttons/tiles with download handlers
            logger.info("STEP 6: Extracting download buttons/tiles...")
            download_buttons = self._extract_download_buttons(driver, url)
            result['download_buttons'] = download_buttons
            logger.info(f"  ✅ Found {len(download_buttons)} download buttons")

            # STEP 7: Perform generic click pass to reveal hidden navigation
            logger.info("STEP 7: Performing generic click pass to reveal hidden links...")
            new_links = self._generic_click_pass(driver, url, max_clicks=20)
            if new_links:
                # Merge new links into all_links (avoiding duplicates)
                existing_hrefs = {link['href'] for link in result['all_links']}
                unique_new_links = [link for link in new_links if link['href'] not in existing_hrefs]
                result['all_links'].extend(unique_new_links)
                logger.info(f"  ✅ Click pass discovered {len(unique_new_links)} unique new links")
            else:
                logger.info(f"  ℹ️  Click pass discovered 0 new links")

            # STEP 8: Filter data links from all collected sources
            logger.info("STEP 8: Filtering data links from all sources...")
            # Combine all sources including NEW CDP and DOM sources
            all_source_data = {
                'all_links': result['all_links'],
                'late_api_calls': result.get('late_api_calls', []),
                'cdp_data_urls': result.get('cdp_data_urls', []),
                'dom_files': result.get('dom_files', []),
                'download_buttons': result.get('download_buttons', [])
            }
            data_links = self._filter_data_links(all_source_data, url)
            result['data_links'] = data_links
            logger.info(f"  ✅ Filtered {len(data_links)} data links from all sources")

            # STEP 9: Build navigation text for LLM context
            result['navigation_text'] = self._build_navigation_text(result)

            logger.info(f"=== EXTRACTION COMPLETE ===")
            logger.info(f"Summary:")
            logger.info(f"  - Total links: {len(result['all_links'])}")
            logger.info(f"  - CDP data URLs: {len(result.get('cdp_data_urls', []))}")
            logger.info(f"  - DOM files: {len(result.get('dom_files', []))}")
            logger.info(f"  - Data links (filtered): {len(result['data_links'])}")
            logger.info(f"  - Late API calls: {len(result['late_api_calls'])}")
            logger.info(f"  - Download buttons: {len(result['download_buttons'])}")
            logger.info(f"  - Custom hints: {len(result['custom_element_hints'])}")

            return result

        except Exception as e:
            logger.error(f"Failed to extract comprehensive website data: {e}", exc_info=True)
            return result

        finally:
            if driver:
                try:
                    driver.close()
                    logger.debug("Driver closed")
                except Exception as e:
                    logger.warning(f"Failed to close driver: {e}")

    def _extract_all_links_with_metadata(self, driver, base_url: str) -> list[dict]:
        """Extract ALL anchors from page including hidden ones with full metadata.

        Uses JavaScript to query ALL <a> tags regardless of visibility.
        Collects: href, text, aria-label, title, dataset, role, plus source location.

        Args:
            driver: Botasaurus Driver instance
            base_url: Base URL for resolving relative links

        Returns:
            List of link metadata dicts
        """
        try:
            links = driver.run_js("""
                return Array.from(document.querySelectorAll('a[href]')).map(a => {
                    // Get all dataset attributes
                    const dataset = {};
                    for (let key in a.dataset) {
                        dataset[key] = a.dataset[key];
                    }

                    return {
                        href: a.href,
                        text: a.textContent.trim(),
                        aria_label: a.getAttribute('aria-label') || '',
                        title: a.title || '',
                        dataset: dataset,
                        role: a.getAttribute('role') || '',
                        class_list: Array.from(a.classList),
                        source: 'main_dom'
                    };
                });
            """)

            # Add fallback labels for links with empty text
            for link in links:
                if not link['text']:
                    # Try fallback: aria-label, title, or last path segment
                    if link['aria_label']:
                        link['text'] = link['aria_label']
                    elif link['title']:
                        link['text'] = link['title']
                    else:
                        # Extract last path segment from href
                        try:
                            from urllib.parse import urlparse
                            path = urlparse(link['href']).path
                            segments = [s for s in path.split('/') if s]
                            if segments:
                                link['text'] = segments[-1]
                        except:
                            link['text'] = 'unknown'

            return links

        except Exception as e:
            logger.warning(f"Failed to extract links with metadata: {e}")
            return []

    def _extract_shadow_dom_data(self, driver) -> dict:
        """Recursively traverse Shadow DOM and custom elements.

        Many modern web portals use Shadow DOM for encapsulation.
        This walker recursively traverses shadowRoots and extracts:
        - Links from shadow DOM trees
        - Text content for LLM context
        - Custom element attributes (hints)

        Args:
            driver: Botasaurus Driver instance

        Returns:
            Dict with keys: links, text, hints
        """
        try:
            shadow_data = driver.run_js("""
                const result = {
                    links: [],
                    text: '',
                    hints: []
                };

                // Recursive walker for shadow roots
                function walkShadowDOM(root, depth = 0) {
                    if (depth > 10) return;  // Prevent infinite recursion

                    // Find all elements in this root
                    const elements = root.querySelectorAll('*');

                    for (let elem of elements) {
                        // Extract links
                        if (elem.tagName === 'A' && elem.href) {
                            result.links.push({
                                href: elem.href,
                                text: elem.textContent.trim(),
                                aria_label: elem.getAttribute('aria-label') || '',
                                title: elem.title || '',
                                dataset: {...elem.dataset},
                                role: elem.getAttribute('role') || '',
                                class_list: Array.from(elem.classList),
                                source: 'shadow_dom'
                            });
                        }

                        // Collect text content
                        if (elem.textContent && elem.textContent.trim()) {
                            result.text += elem.textContent.trim() + ' ';
                        }

                        // Collect custom element hints
                        if (elem.tagName.includes('-')) {  // Custom element
                            const attrs = {};
                            for (let attr of elem.attributes) {
                                attrs[attr.name] = attr.value;
                            }
                            result.hints.push({
                                tag: elem.tagName.toLowerCase(),
                                attributes: attrs
                            });
                        }

                        // Traverse shadow root if present
                        if (elem.shadowRoot) {
                            walkShadowDOM(elem.shadowRoot, depth + 1);
                        }
                    }
                }

                // Start walking from document root
                walkShadowDOM(document);

                // Truncate text to ~2000 chars
                if (result.text.length > 2000) {
                    result.text = result.text.substring(0, 2000) + '...';
                }

                return result;
            """)

            return shadow_data

        except Exception as e:
            logger.warning(f"Failed to extract shadow DOM data: {e}")
            return {'links': [], 'text': '', 'hints': []}

    def _generic_click_pass(self, driver, base_url: str, max_clicks: int = 20) -> list[dict]:
        """Perform generic click pass to reveal hidden navigation and data links.

        This method uses ONLY generic interactive element selectors (no site-specific patterns).
        It clicks dropdowns, buttons, tabs, and other interactive elements to reveal hidden links.

        Strategy:
        - Use generic ARIA/role/HTML patterns that work across sites
        - Click interactive elements likely to reveal navigation/links
        - Extract NEW links after each click
        - Limit to max_clicks budget to avoid infinite loops

        Generic selectors used:
        - [aria-haspopup]: Dropdown triggers (ARIA standard)
        - [role=button]: ARIA button roles
        - [role=tab]: Tab navigation (ARIA standard)
        - .dropdown-toggle: Common Bootstrap/CSS framework class
        - [data-toggle]: Common data attribute for toggles
        - summary: Native HTML5 details/summary disclosure
        - button:not([type=submit]): Generic buttons (exclude forms)

        Args:
            driver: Botasaurus Driver instance
            base_url: Base URL for resolving relative links
            max_clicks: Maximum clicks to perform (default 20)

        Returns:
            List of NEW link metadata dicts discovered from clicks
        """
        logger.info(f"=== GENERIC CLICK PASS (max {max_clicks} clicks) ===")

        # Capture links BEFORE clicking
        links_before = self._extract_all_links_with_metadata(driver, base_url)
        hrefs_before = {link['href'] for link in links_before}
        logger.info(f"Links before click pass: {len(hrefs_before)}")

        # Generic interactive element selectors (NO site-specific patterns)
        click_selectors = [
            '[aria-haspopup="true"]',       # ARIA dropdown triggers
            '[role="button"]',              # ARIA button roles
            '[role="tab"]',                 # ARIA tab navigation
            '.dropdown-toggle',             # Bootstrap/common CSS frameworks
            '[data-toggle]',                # Common data-toggle attributes
            'summary',                      # Native HTML5 details/summary
            'button:not([type="submit"])'   # Generic buttons (exclude form submits)
        ]

        clicks_performed = 0
        for selector in click_selectors:
            if clicks_performed >= max_clicks:
                logger.info(f"Reached max clicks budget ({max_clicks}), stopping")
                break

            try:
                # Find all clickable elements matching selector
                elements = driver.run_js(f"""
                    return Array.from(document.querySelectorAll('{selector}')).map((el, idx) => {{
                        return {{
                            index: idx,
                            text: el.textContent.trim().substring(0, 50),
                            tag: el.tagName.toLowerCase(),
                            visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
                        }};
                    }});
                """)

                if not elements:
                    continue

                logger.debug(f"Selector '{selector}': found {len(elements)} elements")

                # Click each visible element (up to budget)
                for elem in elements:
                    if clicks_performed >= max_clicks:
                        break

                    if not elem['visible']:
                        continue  # Skip invisible elements

                    try:
                        # Click element by index
                        clicked = driver.run_js(f"""
                            const el = document.querySelectorAll('{selector}')[{elem['index']}];
                            if (el && typeof el.click === 'function') {{
                                el.click();
                                return true;
                            }}
                            return false;
                        """)

                        if clicked:
                            clicks_performed += 1
                            logger.debug(f"  Clicked [{clicks_performed}/{max_clicks}]: {elem['tag']} '{elem['text']}'")
                            # Wait for any animations/AJAX
                            driver.sleep(0.5)

                    except Exception as e:
                        logger.debug(f"  Failed to click element: {e}")
                        continue

            except Exception as e:
                logger.warning(f"Selector '{selector}' failed: {e}")
                continue

        # Capture links AFTER clicking
        links_after = self._extract_all_links_with_metadata(driver, base_url)
        hrefs_after = {link['href'] for link in links_after}

        # Calculate NEW links discovered
        new_hrefs = hrefs_after - hrefs_before
        new_links = [link for link in links_after if link['href'] in new_hrefs]

        logger.info(f"=== CLICK PASS COMPLETE ===")
        logger.info(f"  Clicks performed: {clicks_performed}/{max_clicks}")
        logger.info(f"  Links before: {len(hrefs_before)}")
        logger.info(f"  Links after: {len(hrefs_after)}")
        logger.info(f"  NEW links discovered: {len(new_links)}")

        return new_links

    def _capture_late_network_calls(self, driver, wait_seconds: int = 7) -> list[str]:
        """Hook fetch/XMLHttpRequest to capture late API calls.

        Many JavaScript portals make API calls after initial page load.
        This hooks into fetch() and XMLHttpRequest to capture these URLs.

        Args:
            driver: Botasaurus Driver instance
            wait_seconds: How long to wait for network calls (5-10s)

        Returns:
            List of captured API call URLs
        """
        try:
            # Install network hooks
            driver.run_js("""
                window.__captured_network_calls = [];

                // Hook fetch()
                const originalFetch = window.fetch;
                window.fetch = function(...args) {
                    const url = args[0];
                    if (typeof url === 'string') {
                        window.__captured_network_calls.push(url);
                    } else if (url && url.url) {
                        window.__captured_network_calls.push(url.url);
                    }
                    return originalFetch.apply(this, args);
                };

                // Hook XMLHttpRequest
                const originalOpen = XMLHttpRequest.prototype.open;
                XMLHttpRequest.prototype.open = function(method, url) {
                    window.__captured_network_calls.push(url);
                    return originalOpen.apply(this, arguments);
                };
            """)

            # Wait for custom elements to be defined and network calls to occur
            logger.debug(f"Waiting {wait_seconds}s for late network calls...")
            driver.sleep(wait_seconds)

            # Retrieve captured calls
            captured_calls = driver.run_js("""
                return window.__captured_network_calls || [];
            """)

            # Filter to unique, valid URLs
            unique_calls = list(set([
                call for call in captured_calls
                if call and isinstance(call, str) and call.startswith('http')
            ]))

            return unique_calls

        except Exception as e:
            logger.warning(f"Failed to capture late network calls: {e}")
            return []

    def _extract_download_buttons(self, driver, base_url: str) -> list[dict]:
        """Extract buttons/tiles with download handlers.

        Some portals use buttons instead of links for downloads.
        Look for: role="button", data-url, onclick handlers with download/export.

        Args:
            driver: Botasaurus Driver instance
            base_url: Base URL for context

        Returns:
            List of button metadata dicts
        """
        try:
            buttons = driver.run_js("""
                const buttons = [];

                // Find all potential download buttons
                const selectors = [
                    'button[role="button"]',
                    'div[role="button"]',
                    '[data-url]',
                    '[data-href]',
                    '[data-download]',
                    '[onclick*="download"]',
                    '[onclick*="export"]',
                    'button[class*="download"]',
                    'button[class*="export"]'
                ];

                for (let selector of selectors) {
                    const elements = document.querySelectorAll(selector);
                    for (let elem of elements) {
                        const dataset = {};
                        for (let key in elem.dataset) {
                            dataset[key] = elem.dataset[key];
                        }

                        buttons.push({
                            tag: elem.tagName.toLowerCase(),
                            text: elem.textContent.trim(),
                            aria_label: elem.getAttribute('aria-label') || '',
                            dataset: dataset,
                            onclick: elem.getAttribute('onclick') || '',
                            role: elem.getAttribute('role') || '',
                            class_list: Array.from(elem.classList)
                        });
                    }
                }

                return buttons;
            """)

            return buttons

        except Exception as e:
            logger.warning(f"Failed to extract download buttons: {e}")
            return []

    def _filter_data_links(self, all_source_data: dict, base_url: str) -> list[str]:
        """Filter data file download links from all collected sources.

        NEW: Now accepts multiple sources including CDP URLs and DOM files.

        Filters by patterns:
        - Extensions: .csv, .json, .xml, .xlsx, .zip, .pdf
        - Substrings: /download, /data/, /report, /export, feed, webdav, document_library

        Args:
            all_source_data: Dict with keys:
                - all_links: List of link metadata dicts
                - late_api_calls: List of late API call URLs
                - cdp_data_urls: List of URLs from CDP XHR capture (NEW)
                - dom_files: List of files from DOM text extraction (NEW)
                - download_buttons: List of download button metadata
            base_url: Base URL for validation

        Returns:
            List of data link URLs (deduplicated)
        """
        data_links = []

        # Data patterns to match
        extension_patterns = ['.csv', '.json', '.xml', '.xlsx', '.xls', '.zip', '.pdf', '.tsv', '.parquet']
        substring_patterns = [
            '/download', '/data/', '/report', '/export', '/feed',
            'webdav', 'document_library', '/files/', '/archive'
        ]

        # Process regular link metadata (all_links, download_buttons)
        all_links = all_source_data.get('all_links', [])
        for link in all_links:
            href = link.get('href', '').lower()

            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue

            # Check extension patterns
            if any(ext in href for ext in extension_patterns):
                data_links.append(link['href'])
                continue

            # Check substring patterns
            if any(pattern in href for pattern in substring_patterns):
                data_links.append(link['href'])
                continue

            # Check for data-related keywords in path (e.g., /pricing-data, /load-data)
            # This catches URLs like https://www.nyiso.com/pricing-data
            path_keywords = [
                'pricing', 'load', 'market', 'ancillary', 'capacity',
                'generation', 'forecast', 'historical', 'realtime', 'real-time'
            ]
            if any(keyword in href for keyword in path_keywords):
                # Must be on same domain
                try:
                    from urllib.parse import urlparse
                    base_domain = urlparse(base_url).netloc
                    link_domain = urlparse(link['href']).netloc
                    if base_domain == link_domain:
                        data_links.append(link['href'])
                except:
                    pass

        # Process string URLs (late_api_calls, cdp_data_urls, dom_files)
        string_sources = (
            all_source_data.get('late_api_calls', []) +
            all_source_data.get('cdp_data_urls', []) +  # NEW: CDP URLs
            all_source_data.get('dom_files', [])        # NEW: DOM files
        )

        for url_or_file in string_sources:
            if not url_or_file or not isinstance(url_or_file, str):
                continue

            # Handle FILE: prefix from DOM extraction
            if url_or_file.startswith('FILE:'):
                # Strip prefix and check if it matches data file patterns
                filename = url_or_file[5:].lower()  # Remove "FILE:" prefix
                if any(ext in filename for ext in extension_patterns):
                    data_links.append(url_or_file)  # Keep FILE: prefix for AI filtering
                continue

            # Regular URL
            url_lower = url_or_file.lower()

            if url_lower.startswith('#') or url_lower.startswith('javascript:'):
                continue

            # Check extension patterns
            if any(ext in url_lower for ext in extension_patterns):
                data_links.append(url_or_file)
                continue

            # Check substring patterns
            if any(pattern in url_lower for pattern in substring_patterns):
                data_links.append(url_or_file)
                continue

        # Deduplicate
        return list(set(data_links))

    def _build_navigation_text(self, result: dict) -> str:
        """Build navigation text for LLM context.

        When page text/nav is sparse, include:
        - Shadow root text (truncated ~1-2k)
        - Network URLs
        - Custom element hints

        Args:
            result: Extraction result dict

        Returns:
            Combined navigation text
        """
        parts = []

        # Add link text
        link_texts = [link.get('text', '') for link in result['all_links'] if link.get('text')]
        if link_texts:
            parts.append("Navigation Links:\n" + "\n".join(link_texts[:100]))  # First 100 links

        # Add shadow DOM text if present
        if result['shadow_dom_text']:
            parts.append(f"\nShadow DOM Content:\n{result['shadow_dom_text']}")

        # Add custom element hints
        if result['custom_element_hints']:
            hints_text = "\n".join([
                f"  - <{h['tag']}> with attributes: {', '.join(h['attributes'].keys())}"
                for h in result['custom_element_hints'][:20]  # First 20 hints
            ])
            parts.append(f"\nCustom Elements Found:\n{hints_text}")

        # Add late API calls
        if result['late_api_calls']:
            parts.append(f"\nLate API Calls:\n" + "\n".join(result['late_api_calls'][:20]))

        return "\n\n".join(parts)
