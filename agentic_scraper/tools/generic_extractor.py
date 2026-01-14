"""Generic operation extractor guided by vision analysis.

Interprets natural language guidance from Claude to extract operations
without hard-coded patterns or portal-specific logic.
"""

from typing import List, Dict, Optional
import logging
from botasaurus.browser import Driver

logger = logging.getLogger(__name__)


class GenericOperationExtractor:
    """Extract operations using vision-guided natural language instructions."""

    def extract_operations(
        self,
        url: str,
        driver: Driver,
        guidance: str,
        recommended_selectors: List[str],
        requires_interaction: bool,
        interaction_type: Optional[str],
        url_pattern: Optional[str]
    ) -> List[Dict[str, str]]:
        """Extract operations following Claude's guidance.

        Args:
            url: Base URL
            driver: Browser driver
            guidance: Natural language extraction guidance from vision
            recommended_selectors: CSS selectors from vision analysis
            requires_interaction: Whether page needs interaction
            interaction_type: Type of interaction if needed
            url_pattern: URL pattern if detected

        Returns:
            List of {name, url} dicts for each operation
        """
        logger.info("=== GENERIC OPERATION EXTRACTION ===")
        logger.info(f"Following vision guidance: {guidance[:200]}...")

        operations = []

        try:
            # Step 1: Handle interaction if needed
            if requires_interaction and interaction_type:
                logger.info(f"Interaction required: {interaction_type}")
                self._perform_interaction(driver, interaction_type)
                driver.sleep(2)  # Wait for content to load

            # Step 2: Try recommended selectors from vision
            logger.info(f"Trying {len(recommended_selectors)} vision-recommended selectors")
            for selector in recommended_selectors:
                try:
                    elements = driver.run_js(f"""
                        const elements = document.querySelectorAll('{selector}');
                        return Array.from(elements).map(el => ({{
                            text: el.textContent.trim(),
                            href: el.href || el.getAttribute('data-url') || el.getAttribute('data-path'),
                            className: el.className,
                            id: el.id
                        }}));
                    """)

                    if elements and len(elements) > 0:
                        logger.info(f"✅ Selector '{selector}' found {len(elements)} elements")
                        operations.extend(elements)
                    else:
                        logger.debug(f"Selector '{selector}' found no elements")

                except Exception as e:
                    logger.debug(f"Selector '{selector}' failed: {e}")
                    continue

            # Step 3: If selectors failed, interpret guidance for fallback
            if not operations:
                logger.info("Vision selectors found nothing, interpreting guidance for fallback")
                operations = self._interpret_guidance_fallback(driver, guidance, url_pattern)

            # Step 4: Clean and deduplicate
            operations = self._clean_operations(operations, url)

            logger.info(f"✅ Extracted {len(operations)} operations using generic guidance")

            return operations

        except Exception as e:
            logger.error(f"Generic extraction failed: {e}", exc_info=True)
            return []

    def _perform_interaction(self, driver: Driver, interaction_type: str):
        """Perform interaction based on natural language description.

        Args:
            driver: Browser driver
            interaction_type: Natural language description of interaction needed
        """
        interaction_lower = interaction_type.lower()

        logger.info(f"Performing interaction: {interaction_type}")

        try:
            # Expand/accordion/collapse
            if any(word in interaction_lower for word in ['expand', 'accordion', 'collapse']):
                logger.info("  Strategy: Expanding collapsible sections")
                driver.run_js("""
                    // Find and click all expand buttons
                    const expandButtons = document.querySelectorAll('[aria-expanded="false"], .collapsed, .expand-button, button[aria-label*="expand" i]');
                    expandButtons.forEach(btn => {
                        try { btn.click(); } catch(e) {}
                    });

                    // Find and expand details/summary
                    const details = document.querySelectorAll('details:not([open])');
                    details.forEach(d => d.setAttribute('open', ''));
                """)

            # Dropdown/select
            elif any(word in interaction_lower for word in ['dropdown', 'select', 'menu']):
                logger.info("  Strategy: Opening dropdowns")
                driver.run_js("""
                    const dropdowns = document.querySelectorAll('select, .dropdown, [role="combobox"]');
                    dropdowns.forEach(dd => {
                        try {
                            dd.click();
                            // Trigger change/open events
                            dd.dispatchEvent(new Event('mousedown'));
                            dd.dispatchEvent(new Event('click'));
                        } catch(e) {}
                    });
                """)

            # Click buttons
            elif 'button' in interaction_lower or 'click' in interaction_lower:
                logger.info("  Strategy: Clicking interactive buttons")
                driver.run_js("""
                    const buttons = document.querySelectorAll('button, .btn, [role="button"]');
                    buttons.forEach(btn => {
                        const text = btn.textContent.toLowerCase();
                        if (text.includes('show') || text.includes('more') || text.includes('all')) {
                            try { btn.click(); } catch(e) {}
                        }
                    });
                """)

            # Scroll
            elif 'scroll' in interaction_lower:
                logger.info("  Strategy: Scrolling to load content")
                driver.run_js("""
                    window.scrollTo(0, document.body.scrollHeight);
                """)
                driver.sleep(2)

            # Generic fallback: try clicking anything that looks interactive
            else:
                logger.info("  Strategy: Generic interaction attempt")
                driver.run_js("""
                    const interactive = document.querySelectorAll('[aria-expanded="false"], details:not([open]), .collapsed');
                    interactive.forEach(el => {
                        try { el.click(); } catch(e) {}
                        try { el.setAttribute('open', ''); } catch(e) {}
                    });
                """)

        except Exception as e:
            logger.warning(f"Interaction failed: {e}")

    def _interpret_guidance_fallback(
        self,
        driver: Driver,
        guidance: str,
        url_pattern: Optional[str]
    ) -> List[Dict]:
        """Interpret natural language guidance to extract operations.

        Args:
            driver: Browser driver
            guidance: Natural language extraction guidance
            url_pattern: URL pattern if known

        Returns:
            List of operation dicts
        """
        guidance_lower = guidance.lower()
        operations = []

        logger.info("Interpreting guidance for extraction strategy")

        # Strategy 1: Look for keywords in guidance about WHERE to find operations
        location_hints = []
        if 'sidebar' in guidance_lower:
            location_hints.extend(['sidebar', 'aside', '[role="navigation"]', 'nav'])
        if 'list' in guidance_lower or 'menu' in guidance_lower:
            location_hints.extend(['ul li', 'menu', 'list'])
        if 'table' in guidance_lower:
            location_hints.extend(['table', 'tr', 'tbody'])
        if 'link' in guidance_lower or 'anchor' in guidance_lower:
            location_hints.extend(['a'])

        # Strategy 2: Build selector from location hints
        if location_hints:
            for hint in location_hints:
                selector = f"{hint} a" if hint not in ['a'] else 'a'
                try:
                    elements = driver.run_js(f"""
                        const els = document.querySelectorAll('{selector}');
                        return Array.from(els).map(el => ({{
                            text: el.textContent.trim(),
                            href: el.href,
                            className: el.className
                        }}));
                    """)
                    if elements:
                        operations.extend(elements)
                        logger.info(f"  Fallback selector '{selector}' found {len(elements)} elements")
                except Exception as e:
                    continue

        # Strategy 3: If URL pattern mentioned, find elements matching that pattern
        if url_pattern and not operations:
            logger.info(f"  Using URL pattern: {url_pattern}")

            # Extract pattern characteristics
            if '#' in url_pattern:
                # Hash routing
                operations = self._extract_by_pattern(driver, 'hash')
            elif '?' in url_pattern or '&' in url_pattern:
                # Query params
                operations = self._extract_by_pattern(driver, 'query')
            elif '/api/' in url_pattern:
                # API path
                operations = self._extract_by_pattern(driver, 'api_path')

        # Strategy 4: Generic fallback - all links that look like API operations
        if not operations:
            logger.info("  Using generic fallback: all potential API links")
            operations = self._extract_by_pattern(driver, 'generic')

        return operations

    def _extract_by_pattern(self, driver: Driver, pattern_type: str) -> List[Dict]:
        """Extract elements matching a pattern type.

        Args:
            driver: Browser driver
            pattern_type: 'hash', 'query', 'api_path', or 'generic'

        Returns:
            List of operation dicts
        """
        if pattern_type == 'hash':
            # Hash routing
            js = """
                const links = document.querySelectorAll('a[href*="#"]');
                return Array.from(links).map(el => ({
                    text: el.textContent.trim(),
                    href: el.href,
                    className: el.className
                }));
            """
        elif pattern_type == 'query':
            # Query parameters
            js = """
                const links = document.querySelectorAll('a[href*="?"], a[href*="&"]');
                return Array.from(links).map(el => ({
                    text: el.textContent.trim(),
                    href: el.href,
                    className: el.className
                }));
            """
        elif pattern_type == 'api_path':
            # API paths
            js = """
                const links = document.querySelectorAll('a[href*="/api/"], a[href*="/v1/"], a[href*="/v2/"], a[href*="endpoint"]');
                return Array.from(links).map(el => ({
                    text: el.textContent.trim(),
                    href: el.href,
                    className: el.className
                }));
            """
        else:
            # Generic: anything that looks like it could be an operation
            js = """
                const links = document.querySelectorAll('a');
                return Array.from(links)
                    .filter(el => {
                        const text = el.textContent.toLowerCase();
                        const href = (el.href || '').toLowerCase();
                        // Filter for operation-like links
                        return href && (
                            href.includes('api') ||
                            href.includes('endpoint') ||
                            href.includes('operation') ||
                            text.includes('get') ||
                            text.includes('post') ||
                            text.includes('put') ||
                            text.includes('delete')
                        );
                    })
                    .map(el => ({
                        text: el.textContent.trim(),
                        href: el.href,
                        className: el.className
                    }));
            """

        try:
            return driver.run_js(js) or []
        except Exception as e:
            logger.warning(f"Pattern extraction failed: {e}")
            return []

    def _clean_operations(self, operations: List[Dict], base_url: str) -> List[Dict]:
        """Clean and deduplicate operations.

        Args:
            operations: Raw operation dicts
            base_url: Base URL for context

        Returns:
            Cleaned operation list
        """
        seen_urls = set()
        cleaned = []

        for op in operations:
            # Skip if missing required fields
            if not op.get('text') or not op.get('href'):
                continue

            # Skip if duplicate URL
            url = op['href']
            if url in seen_urls:
                continue

            # Skip if text is too generic or empty
            text = op['text'].strip()
            if not text or len(text) < 2:
                continue

            seen_urls.add(url)
            cleaned.append({
                'name': text,
                'url': url
            })

        logger.info(f"Cleaned: {len(operations)} → {len(cleaned)} operations")
        return cleaned
