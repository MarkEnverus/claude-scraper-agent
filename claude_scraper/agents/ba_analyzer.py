"""Business Analyst Agent for data source analysis.

This module implements the BA analyzer that performs 4-phase analysis of
data sources (APIs, FTP, websites, email) using BAML-generated types.

Example:
    >>> from claude_scraper.agents.ba_analyzer import BAAnalyzer
    >>> from claude_scraper.tools.botasaurus_tool import BotasaurusTool
    >>>
    >>> analyzer = BAAnalyzer(botasaurus=BotasaurusTool())
    >>> spec = await analyzer.run_full_analysis("https://api.example.com")
"""

import logging
from datetime import datetime
from typing import Optional

from claude_scraper.llm.base import LLMProvider
from claude_scraper.types import (
    EndpointAnalysis,
    Phase0Detection,
    Phase1Documentation,
    Phase2Tests,
    ValidatedSpec,
)
from claude_scraper.prompts.ba_analyzer import (
    phase0_prompt,
    analyze_endpoint_prompt,
    phase1_prompt,
    phase2_prompt,
    phase3_prompt,
)
from claude_scraper.storage.repository import AnalysisRepository
from claude_scraper.tools.botasaurus_tool import BotasaurusTool
from claude_scraper.tools.html_preprocessor import HTMLPreprocessor, format_for_prompt

logger = logging.getLogger(__name__)


class BAAnalyzer:
    """Business Analyst Agent for data source analysis.

    Performs 4-phase analysis of data sources:
    - Phase 0: Detect data source type (API, FTP, Website, Email)
    - Phase 1: Extract documentation/metadata
    - Phase 2: Live testing and validation
    - Phase 3: Generate validated specification with cross-checks

    Attributes:
        botasaurus: Botasaurus tool for browser automation (handles all network calls)
        repository: Repository for saving/loading analysis artifacts

    Example:
        >>> analyzer = BAAnalyzer(botasaurus=BotasaurusTool())
        >>> spec = await analyzer.run_full_analysis("https://api.example.com")
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        botasaurus: Optional[BotasaurusTool] = None,
        repository: Optional[AnalysisRepository] = None,
    ) -> None:
        """Initialize BA analyzer.

        Args:
            llm_provider: LLM provider for structured LLM calls (Bedrock or Anthropic)
            botasaurus: Botasaurus tool for browser automation (handles all network calls)
            repository: Optional repository for saving artifacts (default: datasource_analysis/)
        """
        self.llm = llm_provider
        self.botasaurus = botasaurus or BotasaurusTool()  # Create default if not provided
        self.repository = repository or AnalysisRepository("datasource_analysis")

        logger.info(
            "Initialized BAAnalyzer",
            extra={
                "has_llm_provider": self.llm is not None,
                "has_botasaurus": self.botasaurus is not None,
                "repository_path": self.repository.base_dir,
            },
        )

    async def analyze_phase0(self, url: str) -> Phase0Detection:
        """Phase 0: AI-driven iterative data source detection.

        Uses iterative discovery where AI analyzes pages and requests additional
        pages to visit until complete endpoint discovery is achieved.

        Args:
            url: Starting URL to analyze

        Returns:
            Phase0Detection with type, confidence, indicators, and ALL discovered endpoints

        Raises:
            ValueError: If URL is empty
            Exception: If analysis fails

        Example:
            >>> phase0 = await analyzer.analyze_phase0("https://api.example.com")
            >>> print(phase0.detected_type)
            DataSourceType.API
            >>> print(f"Found {len(phase0.discovered_endpoint_urls)} endpoints")
        """
        if not url or not url.strip():
            raise ValueError("url cannot be empty")

        logger.info(f"=== PHASE 0: AI-DRIVEN ITERATIVE DISCOVERY ===")
        logger.info(f"Starting URL: {url}")

        # Extract primary API name from starting URL for focus
        # e.g., "api-details#api=pricing-api" -> "pricing-api"
        primary_api_name = None
        if "#api=" in url or "api=" in url:
            import re
            match = re.search(r'api=([^&]+)', url)
            if match:
                primary_api_name = match.group(1)
                logger.info(f"Primary API detected: {primary_api_name}")

        # Iteration state
        pages_to_visit = [url]  # Queue of URLs to visit
        visited = set()  # Track visited URLs
        all_pages_data = []  # Collect data from all pages
        max_pages = 20  # Safety limit
        analysis = None  # Final analysis result

        # Iteration loop: AI-driven page navigation
        while pages_to_visit and len(visited) < max_pages:
            current_url = pages_to_visit.pop(0)

            # Skip if already visited
            if current_url in visited:
                logger.info(f"Skipping already visited URL: {current_url}")
                continue

            logger.info(f"[Page {len(visited)+1}/{max_pages}] Extracting: {current_url}")

            # Step 1: Botasaurus extracts page data
            try:
                botasaurus_data = self.botasaurus.extract_comprehensive_data(current_url)

                # FIX: Issue #3 - Fail fast if extraction failed
                if botasaurus_data.get('extraction_error'):
                    error_msg = botasaurus_data['extraction_error']
                    logger.error(f"❌ EXTRACTION FAILED - Cannot continue analysis")
                    logger.error(f"URL: {current_url}")
                    logger.error(f"Error: {error_msg}")
                    logger.error("⚠️  Aborting Phase 0 - analysis would be based on NO actual data")
                    raise RuntimeError(f"Extraction failed for {current_url}: {error_msg}")

                logger.info(f"✅ Extraction complete:")
                logger.info(f"  - Markdown: {len(botasaurus_data.get('markdown', ''))} chars")
                logger.info(f"  - Navigation links: {len(botasaurus_data.get('navigation_links', []))}")
                logger.info(f"  - Network calls: {len(botasaurus_data.get('network_calls', []))}")
            except RuntimeError:
                # Re-raise extraction failures (fail fast)
                raise
            except Exception as e:
                logger.error(f"❌ Unexpected error during extraction for {current_url}: {e}")
                logger.error("⚠️  Aborting Phase 0 - cannot continue with failed extraction")
                raise

            # Mark as visited and store data
            visited.add(current_url)
            all_pages_data.append({
                'url': current_url,
                'markdown': botasaurus_data.get('markdown', ''),
                'screenshot': botasaurus_data.get('screenshot'),
                'navigation_links': botasaurus_data.get('navigation_links', []),
                'network_calls': botasaurus_data.get('network_calls', [])
            })

            # Step 2: AI analyzes all pages seen so far (with vision)
            logger.info("AI analyzing all pages with vision and deciding next steps...")
            try:
                # Import needed for iterative prompt
                from claude_scraper.prompts.ba_analyzer import phase0_iterative_prompt
                from claude_scraper.types import Phase0IterativeAnalysis

                # Create iterative prompt
                prompt = phase0_iterative_prompt(
                    all_pages_data=all_pages_data,
                    visited_urls=list(visited),
                    primary_api_name=primary_api_name
                )

                # Extract screenshots for vision analysis
                screenshots = [
                    page['screenshot']
                    for page in all_pages_data
                    if page.get('screenshot') is not None
                ]

                # Call AI with vision if screenshots available, otherwise fallback to text-only
                if screenshots:
                    logger.info(f"Using vision analysis with {len(screenshots)} screenshots")
                    analysis = self.llm.invoke_structured_with_vision(
                        prompt=prompt,
                        images=screenshots,
                        response_model=Phase0IterativeAnalysis,
                        system="You are an expert data source analyst who navigates documentation like a human would. Analyze the screenshots visually to identify ALL operations, endpoints, or data access methods visible on the page."
                    )
                else:
                    logger.warning("No screenshots available, falling back to text-only analysis")
                    analysis = self.llm.invoke_structured(
                        prompt=prompt,
                        response_model=Phase0IterativeAnalysis,
                        system="You are an expert data source analyst who navigates documentation like a human would."
                    )

                logger.info(f"AI decision:")
                logger.info(f"  - Needs more pages: {analysis.needs_more_pages}")
                logger.info(f"  - URLs to visit: {len(analysis.urls_to_visit)}")
                logger.info(f"  - Endpoints found so far: {len(analysis.discovered_endpoint_urls)}")
                logger.info(f"  - Reasoning: {analysis.reasoning[:100]}...")

                # Step 3: Check if AI wants to continue
                if not analysis.needs_more_pages:
                    logger.info(f"✅ AI completed discovery after {len(visited)} pages")
                    break

                # Step 4: Add AI-requested URLs to visit queue
                new_urls = [u for u in analysis.urls_to_visit if u not in visited]
                if new_urls:
                    pages_to_visit.extend(new_urls)
                    logger.info(f"AI requested {len(new_urls)} new URLs to visit")
                else:
                    logger.info("AI didn't request new URLs, stopping iteration")
                    break

            except Exception as e:
                logger.error(f"AI analysis failed on iteration {len(visited)}: {e}")
                # If we have some data, try to continue; otherwise raise
                if not all_pages_data:
                    raise
                # Use last successful analysis or create minimal one
                if analysis is None:
                    logger.warning("Creating fallback Phase0Detection from partial data")
                    # We'll handle this below
                break

        # Final step: Convert iterative analysis to Phase0Detection
        logger.info(f"=== ITERATION COMPLETE ===")
        logger.info(f"Pages visited: {len(visited)}")

        if analysis is None:
            raise RuntimeError("No successful analysis completed")

        # CRITICAL FIX: Extract ACTUAL operation URLs by clicking on them
        # The AI-constructed URLs may have wrong format (missing prefixes, wrong naming)
        # So we click on each operation and capture the actual URL
        logger.info("=== EXTRACTING ACTUAL OPERATION URLS ===")
        discovered_endpoint_urls = analysis.discovered_endpoint_urls

        # Try to extract operation names from navigation links
        # Use navigation link text as operation names (generic approach)
        import re
        operation_names = []

        # FIX #3: Extract operation names from ALL pages (not just first page)
        # FIX #5: Reduce skip_terms to only true UI chrome (remove 'documentation', etc.)
        if all_pages_data:
            # Aggregate navigation links from ALL pages
            all_nav_links = []
            for page_data in all_pages_data:
                nav_links = page_data.get('navigation_links', [])
                all_nav_links.extend(nav_links)

            logger.info(f"Collected {len(all_nav_links)} total navigation links from {len(all_pages_data)} pages")

            # Deduplicate by link text using Set (O(1) lookup)
            seen_texts = set()
            for link in all_nav_links:
                link_text = link.get('text', '').strip()

                # Include links that look like operations (not too long, not navigation UI elements)
                if link_text and len(link_text) < 100 and len(link_text.split()) <= 8:
                    # Skip ONLY true UI chrome elements (not documentation/reference)
                    skip_terms = ['home', 'about', 'contact', 'login', 'sign up', 'logout']

                    if not any(term in link_text.lower() for term in skip_terms):
                        if link_text not in seen_texts:
                            seen_texts.add(link_text)
                            operation_names.append(link_text)

            logger.info(f"Found {len(operation_names)} potential operation names from navigation: {operation_names[:10]}")

        # FIX #11: Phase 3 - Try Swagger/OpenAPI/WADL spec parsing FIRST (most reliable)
        logger.info("=== ATTEMPTING PHASE 3: SWAGGER/OPENAPI/WADL SPEC PARSING ===")
        spec_data = self.botasaurus.try_fetch_api_spec(url)

        if spec_data:
            logger.info(f"✅ Found {spec_data['spec_type']} specification:")
            logger.info(f"  - Spec URL: {spec_data['spec_url']}")
            logger.info(f"  - Endpoints: {len(spec_data['endpoints'])}")

            # Use spec endpoints as discovered URLs (100% accurate!)
            discovered_endpoint_urls = spec_data['endpoints']

            # Skip operation clicking - we have authoritative spec
            logger.info("✅ Using spec as authoritative source - skipping operation clicking")
            logger.info(f"Discovered {len(discovered_endpoint_urls)} endpoints from spec:")
            for i, endpoint in enumerate(discovered_endpoint_urls[:10], 1):
                logger.info(f"  {i}. {endpoint}")
            if len(discovered_endpoint_urls) > 10:
                logger.info(f"  ... and {len(discovered_endpoint_urls) - 10} more")

        else:
            logger.info("❌ No spec found")

            # FIX #15: GENERIC VISION-BASED PORTAL ANALYSIS
            # Use Claude vision to understand ANY portal type without hard-coded patterns
            logger.info("=== ATTEMPTING GENERIC VISION-BASED PORTAL ANALYSIS ===")

            vision_extracted_operations = []
            if all_pages_data and all_pages_data[0].get('screenshot'):
                try:
                    from claude_scraper.tools.vision_portal_analyzer import VisionPortalAnalyzer
                    from claude_scraper.tools.generic_extractor import GenericOperationExtractor

                    # Analyze first page with vision (usually the main portal page)
                    first_page = all_pages_data[0]
                    vision_analyzer = VisionPortalAnalyzer(self.llm)

                    portal_analysis = vision_analyzer.analyze_portal(
                        url=first_page['url'],
                        screenshot_path=first_page['screenshot'],
                        page_text=first_page.get('markdown', '')[:2000]  # First 2000 chars
                    )

                    # If vision has high confidence it's API docs, use its guidance
                    if portal_analysis and portal_analysis.confidence > 0.7:
                        logger.info(f"✅ Vision identified API portal (confidence: {portal_analysis.confidence:.2f})")
                        logger.info(f"  Description: {portal_analysis.visual_description}")
                        logger.info(f"  Operations location: {portal_analysis.operations_location}")
                        logger.info(f"  Presentation: {portal_analysis.operations_presentation}")
                        logger.info(f"  Visible operations: {len(portal_analysis.operations_visible)}")

                        # Extract operations using vision guidance
                        extractor = GenericOperationExtractor()
                        # Need to create a new driver for extraction
                        from botasaurus.browser import Driver

                        driver = None
                        try:
                            driver = Driver(headless=True, block_images=True, wait_for_complete_page_load=True)
                            driver.get(first_page['url'])
                            driver.sleep(3)  # Wait for page load

                            vision_extracted_operations = extractor.extract_operations(
                                url=first_page['url'],
                                driver=driver,
                                guidance=portal_analysis.extraction_guidance,
                                recommended_selectors=portal_analysis.recommended_selectors if hasattr(portal_analysis, 'recommended_selectors') else [],
                                requires_interaction=portal_analysis.appears_to_be_interactive,
                                interaction_type=getattr(portal_analysis, 'interaction_type', None),
                                url_pattern=portal_analysis.url_pattern
                            )

                            if vision_extracted_operations:
                                logger.info(f"✅ Vision-guided extraction: {len(vision_extracted_operations)} operations")
                                logger.info(f"  Sample operations: {[op['name'][:50] for op in vision_extracted_operations[:5]]}")

                                # Use vision-extracted operations
                                operation_names = [op['name'] for op in vision_extracted_operations]
                                discovered_endpoint_urls = [op['url'] for op in vision_extracted_operations]

                                logger.info(f"✅ Using vision-extracted operations, skipping fallback methods")

                        finally:
                            if driver:
                                try:
                                    driver.close()
                                except:
                                    pass

                    else:
                        if portal_analysis:
                            logger.info(f"Vision analyzed but low confidence ({portal_analysis.confidence:.2f}) or not API docs")
                        else:
                            logger.info("Vision analysis returned no result")

                except Exception as e:
                    logger.warning(f"Vision-based analysis failed: {e}", exc_info=True)
                    logger.info("Falling back to pattern-based methods")

            # Initialize spa_data to None to avoid UnboundLocalError
            spa_data = None

            # If vision didn't extract operations, try other methods
            if not vision_extracted_operations:
                logger.info("Vision extraction did not produce results, trying fallback methods")

                # FIX #13: Check for SPA hash routing before falling back to operation clicking
                spa_data = self.botasaurus.detect_spa_hash_routing(url)

            if spa_data and spa_data.get('operations'):
                logger.info(f"✅ Detected SPA hash routing:")
                logger.info(f"  - Pattern: {spa_data['pattern_type']}")
                logger.info(f"  - Base API: {spa_data.get('base_api', 'N/A')}")
                logger.info(f"  - Operations: {len(spa_data['operations'])}")

                # Use SPA operations as operation names for clicking
                operation_names = spa_data['operations']
                logger.info(f"Using {len(operation_names)} SPA operations for URL extraction")

            logger.info("Falling back to operation clicking")

            # FIX #8: ALWAYS try clicking if we have operation names - clicking captures browser truth
            # and prevents AI hallucination of incorrect URL structures
            if operation_names:
                try:
                    logger.info(f"Found {len(operation_names)} operation names, attempting to click and extract actual URLs...")
                    logger.info(f"AI constructed {len(discovered_endpoint_urls)} URLs, will verify by clicking...")
                    actual_urls_map = self.botasaurus.extract_operation_urls(url, operation_names)

                    if actual_urls_map:
                        # Replace AI-constructed URLs with actual clicked URLs
                        discovered_endpoint_urls = list(actual_urls_map.values())
                        logger.info(f"✅ Extracted {len(discovered_endpoint_urls)} actual operation URLs by clicking:")
                        for op_name, op_url in actual_urls_map.items():
                            # Extract just the operation identifier for logging (generic)
                            # Could be operation=..., could be a path segment, depends on API structure
                            match = re.search(r'operation=([^&]+)', op_url)
                            if match:
                                op_id = match.group(1)
                                logger.info(f"  {op_name:30} -> operation={op_id}")
                            else:
                                # Just log the full URL if no operation= parameter
                                logger.info(f"  {op_name:30} -> {op_url}")
                    else:
                        logger.warning("Failed to extract operation URLs by clicking, falling back to AI-constructed URLs")
                except Exception as e:
                    logger.warning(f"Failed to extract actual operation URLs: {e}, falling back to AI-constructed URLs")
            else:
                logger.info("No operation names found from navigation, using AI-constructed URLs")

        # FIX #14: Filter out bad URLs (Wikipedia, login pages, spec URLs, etc.)
        logger.info("=== FILTERING DISCOVERED URLS ===")
        filtered_urls, filter_metrics = self.botasaurus.filter_bad_urls(discovered_endpoint_urls)

        if filter_metrics['removed_count'] > 0:
            logger.info(f"✅ Removed {filter_metrics['removed_count']} bad URLs:")
            for category, count in filter_metrics['categories'].items():
                if count > 0:
                    logger.info(f"  - {category}: {count} URLs")

        # Use filtered URLs
        discovered_endpoint_urls = filtered_urls

        # FIX #4: Deduplicate URLs before creating Phase0Detection
        logger.info("=== DEDUPLICATING ENDPOINT URLS ===")
        deduplicated_urls, dedup_metrics = self._deduplicate_urls(discovered_endpoint_urls)

        # Log deduplication results
        logger.info(
            f"URL deduplication complete: {dedup_metrics['original_count']} → "
            f"{dedup_metrics['deduplicated_count']} URLs "
            f"({dedup_metrics['duplicates_removed']} duplicates removed, "
            f"{dedup_metrics['duplication_rate']:.1%} duplication rate)"
        )

        # Warn if duplication rate is high (indicates extraction issue)
        if dedup_metrics['duplication_rate'] > 0.5:
            logger.warning(
                f"High URL duplication rate detected: {dedup_metrics['duplication_rate']:.1%} "
                f"({dedup_metrics['duplicates_removed']}/{dedup_metrics['original_count']} URLs were duplicates). "
                f"This may indicate an issue with the endpoint extraction logic."
            )

        # Use deduplicated URLs for Phase0Detection
        discovered_endpoint_urls = deduplicated_urls

        # Convert Phase0IterativeAnalysis → Phase0Detection
        final_result = Phase0Detection(
            detected_type=analysis.detected_type,
            confidence=analysis.confidence,
            indicators=analysis.indicators,
            discovered_api_calls=analysis.discovered_api_calls,
            discovered_endpoint_urls=discovered_endpoint_urls,  # Use actual clicked URLs
            auth_method=analysis.auth_method,
            base_url=analysis.base_url,
            url=url,  # Original starting URL
            fallback_strategy=f"Iterative discovery completed after visiting {len(visited)} pages"
        )

        # QA Validation: Independently verify Phase 0 results using vision
        if all_pages_data and all_pages_data[0].get('screenshot') is not None:
            try:
                from claude_scraper.agents.phase0_qa_validator import Phase0QAValidator

                logger.info("Running Phase 0 QA validation...")
                validator = Phase0QAValidator(llm_provider=self.llm)

                validation_report = validator.validate(
                    main_screenshot=all_pages_data[0]['screenshot'],
                    discovered_endpoint_urls=final_result.discovered_endpoint_urls,
                    primary_api_name=primary_api_name
                )

                if not validation_report.is_complete:
                    logger.warning(
                        f"⚠️  Phase 0 QA validation found discrepancy:\n"
                        f"   Operations visible in screenshot: {validation_report.operations_visible_in_screenshot}\n"
                        f"   Operations discovered: {validation_report.operations_discovered}\n"
                        f"   Missing operations: {validation_report.missing_operations}\n"
                        f"   Confidence: {validation_report.confidence:.2f}\n"
                        f"   Notes: {validation_report.validation_notes}"
                    )
                else:
                    logger.info(
                        f"✅ Phase 0 QA validation PASSED - "
                        f"All {validation_report.operations_visible_in_screenshot} operations discovered "
                        f"(confidence: {validation_report.confidence:.2f})"
                    )

            except Exception as e:
                logger.warning(
                    f"Phase 0 QA validation failed (non-fatal): {e}",
                    exc_info=True
                )
                # Continue with saving results - QA validation failure is non-fatal
        else:
            logger.info("Skipping Phase 0 QA validation (no screenshots available)")

        # Save result
        self.repository.save("phase0_detection.json", final_result)

        # Verify file was created
        try:
            self.repository.load("phase0_detection.json", Phase0Detection)
            logger.info("Phase 0 result saved and verified")
        except Exception as e:
            raise RuntimeError(f"Failed to save phase0_detection.json: {e}")

        logger.info(f"✅ Phase 0 complete:")
        logger.info(f"  - Type detected: {final_result.detected_type}")
        logger.info(f"  - Confidence: {final_result.confidence:.2f}")
        logger.info(f"  - Endpoints discovered: {len(final_result.discovered_endpoint_urls)}")
        logger.info(f"  - Pages visited: {len(visited)}")

        return final_result

    def _deduplicate_urls(self, urls: list[str]) -> tuple[list[str], dict]:
        """Deduplicate URL list while preserving order (first occurrence).

        FIX #4: Add deduplication to prevent same URL appearing 36x, 62x, 7x in results.

        Args:
            urls: List of URLs (may contain duplicates)

        Returns:
            Tuple of (deduplicated_urls, metrics_dict)
        """
        original_count = len(urls)

        # Use dict.fromkeys() to preserve order (Python 3.7+ guarantees dict order)
        deduplicated_urls = list(dict.fromkeys(urls))

        deduplicated_count = len(deduplicated_urls)
        duplicates_removed = original_count - deduplicated_count
        duplication_rate = duplicates_removed / original_count if original_count > 0 else 0.0

        metrics = {
            'original_count': original_count,
            'deduplicated_count': deduplicated_count,
            'duplicates_removed': duplicates_removed,
            'duplication_rate': duplication_rate
        }

        return deduplicated_urls, metrics

    async def _analyze_phase0_legacy(self, url: str) -> Phase0Detection:
        """Legacy Phase 0: Single-pass detection (kept for reference).

        This is the original single-pass implementation before iterative discovery.
        Kept for reference but not used in production.
        """
        if not url or not url.strip():
            raise ValueError("url cannot be empty")

        logger.info(f"=== PHASE 0: DATA SOURCE DETECTION (LEGACY) ===")
        logger.info(f"Analyzing: {url}")

        # Step 1: Botasaurus extracts EVERYTHING (comprehensive extraction)
        logger.info("Using Botasaurus to render JavaScript and extract comprehensive data...")
        try:
            botasaurus_data = self.botasaurus.extract_comprehensive_data(url)

            logger.info(f"✅ Botasaurus extraction complete:")
            logger.info(f"  - Page text: {len(botasaurus_data['full_text'])} chars")
            logger.info(f"  - Navigation links: {len(botasaurus_data['navigation_links'])}")
            logger.info(f"  - Network calls: {len(botasaurus_data['network_calls'])}")
            logger.info(f"  - Expanded sections: {botasaurus_data['expanded_sections']}")

        except Exception as e:
            logger.warning(f"Botasaurus comprehensive extraction failed: {e}")
            # Fallback to empty data
            botasaurus_data = {
                "full_text": "",
                "markdown": "",
                "navigation_links": [],
                "network_calls": [],
                "expanded_sections": 0,
                "screenshot": None
            }

        # Step 2: Format for AI (intelligently truncate if needed)
        max_chars = 15000
        full_text = botasaurus_data['full_text']
        page_content_for_ai = full_text[:max_chars] if len(full_text) > max_chars else full_text

        if len(full_text) > max_chars:
            logger.warning(f"Page text truncated from {len(full_text)} to {max_chars} chars")

        # Format navigation links as strings for AI
        navigation_links_str = [
            f"{link['text']}: {link['href']}"
            for link in botasaurus_data['navigation_links']
        ]

        logger.info(
            f"Prepared data for AI analysis",
            extra={
                "url": url,
                "page_content_chars": len(page_content_for_ai),
                "navigation_links_count": len(navigation_links_str),
                "network_calls_count": len(botasaurus_data['network_calls']),
            }
        )

        # Step 3: Pass FULL DATA to AI for discovery
        logger.info("Passing comprehensive data to AI for endpoint discovery...")
        try:
            from claude_scraper.prompts.ba_analyzer import phase0_prompt

            # Create prompt for Phase 0 detection
            prompt = phase0_prompt(
                url=url,
                page_content=page_content_for_ai,
                network_calls=botasaurus_data['network_calls'],
                navigation_links=navigation_links_str,
            )

            # Call LLM with structured output
            result = self.llm.invoke_structured(
                prompt=prompt,
                response_model=Phase0Detection,
                system="You are an expert data source analyst specializing in API discovery and endpoint detection."
            )

            # Save result
            self.repository.save("phase0_detection.json", result)

            # CRITICAL: Verify file was actually created
            try:
                self.repository.load("phase0_detection.json", Phase0Detection)
                logger.info("Phase 0 result saved and verified")
            except Exception as e:
                raise RuntimeError(f"Failed to save phase0_detection.json - file verification failed: {e}")

            logger.info(f"✅ Phase 0 complete:")
            logger.info(f"  - Type detected: {result.detected_type}")
            logger.info(f"  - Confidence: {result.confidence:.2f}")
            logger.info(f"  - Endpoint URLs discovered: {len(result.discovered_endpoint_urls) if hasattr(result, 'discovered_endpoint_urls') else 0}")

            return result

        except Exception as e:
            # Provide readable error message with context
            content_size = len(page_content_for_ai)
            error_msg = (
                f"\n{'='*80}\n"
                f"PHASE 0 ANALYSIS FAILED\n"
                f"{'='*80}\n"
                f"URL: {url}\n"
                f"Content size sent to AI: {content_size} chars\n"
                f"Error type: {type(e).__name__}\n"
                f"Error message: {str(e)[:500]}\n"  # Truncate long error messages
                f"\nPossible causes:\n"
                f"  - Content size too large (reduce preprocessing limits)\n"
                f"  - Bedrock/API rate limits or errors\n"
                f"  - Invalid response format from AI\n"
                f"{'='*80}\n"
            )
            logger.error(error_msg)
            raise Exception(f"Phase 0 analysis failed - see error above for details") from e

    async def analyze_endpoints(
        self,
        endpoint_urls: list[str],
        page_context: str,
        auth_method: str,
        base_url: str
    ) -> list[EndpointAnalysis]:
        """Analyze individual endpoints one at a time.

        This method processes each endpoint URL individually to avoid token exhaustion
        that occurred when trying to analyze all endpoints in a single AI call.

        Args:
            endpoint_urls: List of endpoint URLs to analyze
            page_context: Structured page context for reference
            auth_method: Authentication method detected in Phase 0
            base_url: Base URL of the API

        Returns:
            List of EndpointAnalysis objects, one per endpoint

        Example:
            >>> endpoints = await analyzer.analyze_endpoints(
            ...     ["https://api.example.com/v1/users"],
            ...     page_context,
            ...     "bearer_token",
            ...     "https://api.example.com"
            ... )
        """
        logger.info(
            f"Starting individual endpoint analysis for {len(endpoint_urls)} endpoints",
            extra={"endpoint_count": len(endpoint_urls)}
        )

        results = []

        for idx, endpoint_url in enumerate(endpoint_urls):
            logger.info(
                f"Analyzing endpoint {idx + 1}/{len(endpoint_urls)}: {endpoint_url}",
                extra={"endpoint_url": endpoint_url}
            )

            try:
                # Create prompt for endpoint analysis
                prompt = analyze_endpoint_prompt(
                    endpoint_url=endpoint_url,
                    page_context=page_context,
                    auth_method=auth_method,
                    base_url=base_url,
                )

                # Call LLM with structured output
                result = self.llm.invoke_structured(
                    prompt=prompt,
                    response_model=EndpointAnalysis,
                    system="You are an expert API analyst specializing in endpoint specification extraction."
                )

                results.append(result)

                logger.info(
                    f"Endpoint analysis complete: {endpoint_url}",
                    extra={
                        "endpoint_url": endpoint_url,
                        "method": result.method,
                        "parameters": len(result.parameters),
                    }
                )

            except Exception as e:
                logger.error(
                    f"Failed to analyze endpoint {endpoint_url}: {e}",
                    extra={"endpoint_url": endpoint_url},
                    exc_info=True
                )
                # Continue with other endpoints even if one fails
                continue

        logger.info(
            f"Completed individual endpoint analysis: {len(results)}/{len(endpoint_urls)} successful",
            extra={
                "successful": len(results),
                "total": len(endpoint_urls),
                "failed": len(endpoint_urls) - len(results)
            }
        )

        return results

    async def analyze_phase1(
        self,
        url: str,
        phase0: Phase0Detection,
        endpoint_analyses: list[EndpointAnalysis] | None = None
    ) -> Phase1Documentation:
        """Phase 1: Analyze documentation/metadata.

        Extracts detailed information about the data source:
        - For APIs: Endpoints, parameters, authentication requirements
        - For websites: Download links, file formats, access requirements
        - For FTP/Email: Connection details, data formats

        Args:
            url: URL to analyze
            phase0: Phase 0 detection results
            endpoint_analyses: Optional pre-analyzed individual endpoints from analyze_endpoints()

        Returns:
            Phase1Documentation with extracted metadata

        Raises:
            ValueError: If URL is empty
            Exception: If analysis fails

        Example:
            >>> phase1 = await analyzer.analyze_phase1(url, phase0)
            >>> print(f"Found {len(phase1.endpoints)} endpoints")
            >>> # Or with pre-analyzed endpoints:
            >>> endpoint_analyses = await analyzer.analyze_endpoints(...)
            >>> phase1 = await analyzer.analyze_phase1(url, phase0, endpoint_analyses)
        """
        if not url or not url.strip():
            raise ValueError("url cannot be empty")

        logger.info(
            f"Starting Phase 1 analysis for {url}",
            extra={"detected_type": phase0.detected_type},
        )

        # Fetch documentation content using Botasaurus (handles JavaScript)
        # For APIs: Extract endpoint details, parameters, auth requirements
        # For websites: Extract download links, file catalogs
        raw_html = ""

        try:
            logger.info("Using Botasaurus to fetch documentation content")
            raw_html = self.botasaurus.get_page_content(url)
            logger.info(
                f"Botasaurus fetched documentation content",
                extra={"url": url, "html_bytes": len(raw_html)},
            )
        except Exception as e:
            logger.warning(
                f"Botasaurus failed for Phase 1: {e}",
                extra={"url": url},
            )
            raw_html = ""

        # Extract structured data from HTML (no raw HTML dumping!)
        logger.info("Preprocessing documentation HTML to extract structured data")
        preprocessor = HTMLPreprocessor(base_url=url)
        structured_data = preprocessor.extract_structured_data(raw_html)
        formatted_content = format_for_prompt(structured_data)

        logger.info(
            f"Extracted structured documentation data",
            extra={
                "url": url,
                "links_found": structured_data['links']['total_count'],
                "api_links_found": structured_data['links']['api_count'],
                "endpoints_found": len(structured_data['api_endpoints']),
                "tables_found": len(structured_data['tables']),
                "formatted_size": len(formatted_content),
            }
        )

        # Call LLM for Phase 1 analysis
        try:
            # Create prompt for Phase 1 documentation
            prompt = phase1_prompt(
                url=url,
                page_content=formatted_content,  # Structured data, not raw HTML!
                phase0_result=phase0,
            )

            # Call LLM with structured output
            result = self.llm.invoke_structured(
                prompt=prompt,
                response_model=Phase1Documentation,
                system="You are an expert documentation analyst specializing in API specification extraction."
            )

            # Merge individual endpoint analyses if provided
            if endpoint_analyses:
                logger.info(
                    f"Merging {len(endpoint_analyses)} pre-analyzed endpoints into Phase 1 results"
                )

                # Convert EndpointAnalysis to EndpointSpec
                from claude_scraper.types import EndpointSpec
                import re

                merged_endpoints = []
                for idx, endpoint_analysis in enumerate(endpoint_analyses, 1):
                    # Extract operation identifier from URL for endpoint_id (generic approach)
                    # Try operation= parameter first, otherwise use sequential numbering
                    endpoint_id = f"endpoint_{idx:03d}"
                    if "operation=" in endpoint_analysis.endpoint_url:
                        operation = endpoint_analysis.endpoint_url.split("operation=")[-1]
                        # Clean operation name - remove URL fragments and query params
                        operation = re.sub(r'[&#].*$', '', operation)  # Remove fragments
                        endpoint_id = operation
                    elif "/api/" in endpoint_analysis.endpoint_url:
                        # Try to extract from path if no operation= parameter
                        path_parts = endpoint_analysis.endpoint_url.split("/api/")[-1].split("/")
                        if path_parts:
                            endpoint_id = "_".join(path_parts[:3])  # Use first 3 path segments

                    endpoint_spec = EndpointSpec(
                        endpoint_id=endpoint_id,
                        path=endpoint_analysis.path,
                        method=endpoint_analysis.method,
                        description=endpoint_analysis.description,
                        parameters=endpoint_analysis.parameters,
                        response_format=endpoint_analysis.response_format,
                        authentication_mentioned=endpoint_analysis.auth_required
                    )
                    merged_endpoints.append(endpoint_spec)

                # Replace LLM-discovered endpoints with pre-analyzed ones
                result.endpoints = merged_endpoints

                logger.info(
                    f"Successfully merged {len(merged_endpoints)} endpoints into Phase 1"
                )

            # Save result
            self.repository.save("phase1_documentation.json", result)

            # CRITICAL: Verify file was actually created
            try:
                self.repository.load("phase1_documentation.json", Phase1Documentation)
                logger.info("Phase 1 result saved and verified")
            except Exception as e:
                raise RuntimeError(f"Failed to save phase1_documentation.json - file verification failed: {e}")

            logger.info(
                f"Phase 1 complete: {len(result.endpoints)} endpoints documented",
                extra={
                    "url": url,
                    "endpoints_count": len(result.endpoints),
                    "source_type": result.source_type,
                },
            )

            return result

        except Exception as e:
            logger.error(
                f"Phase 1 analysis failed: {e}",
                extra={"url": url},
                exc_info=True,
            )
            raise Exception(f"Phase 1 analysis failed for {url}: {e}") from e

    async def analyze_phase2(
        self, url: str, phase0: Phase0Detection, phase1: Phase1Documentation
    ) -> Phase2Tests:
        """Phase 2: Live testing and validation.

        Tests the actual data source to verify documentation claims:
        - For APIs: Test endpoints with/without authentication
        - For websites: Test download link accessibility
        - Determine actual authentication requirements

        Args:
            url: URL to analyze
            phase0: Phase 0 detection results
            phase1: Phase 1 documentation results

        Returns:
            Phase2Tests with test results and validation

        Raises:
            ValueError: If URL is empty
            Exception: If analysis fails

        Example:
            >>> phase2 = await analyzer.analyze_phase2(url, phase1)
            >>> print(f"Auth required: {phase2.conclusion.auth_required}")
        """
        if not url or not url.strip():
            raise ValueError("url cannot be empty")

        logger.info(
            f"Starting Phase 2 testing for {url}",
            extra={"endpoints_to_test": len(phase1.endpoints)},
        )

        # Import requests for HTTP testing
        import requests
        import time
        from pathlib import Path

        # Create test directory
        test_dir = Path("api_validation_tests")
        test_dir.mkdir(exist_ok=True)
        logger.info(f"Created test directory: {test_dir}")

        # Rate limit: 1 request per second
        test_results = []

        for idx, endpoint in enumerate(phase1.endpoints):
            # Build full URL
            if endpoint.path.startswith("http"):
                endpoint_url = endpoint.path
            else:
                # Extract base URL from phase0 or construct from phase1
                base_url = phase0.url if hasattr(phase0, 'url') else url
                endpoint_url = f"{base_url.rstrip('/')}/{endpoint.path.lstrip('/')}"

            logger.info(f"Testing endpoint {idx+1}/{len(phase1.endpoints)}: {endpoint_url}")

            # Test without authentication
            try:
                response = requests.get(
                    endpoint_url,
                    timeout=10,
                    allow_redirects=False
                )

                status_code = response.status_code
                headers = dict(response.headers)

                # Get response body (truncate if too large)
                try:
                    body = response.text[:1000]
                except:
                    body = "<binary content>"

                test_result = {
                    "endpoint": endpoint_url,
                    "method": endpoint.method,
                    "status_code": status_code,
                    "status_text": response.reason,
                    "headers": headers,
                    "body_preview": body,
                    "test_type": "no_auth"
                }

                test_results.append(test_result)

                # Save to file
                test_file = test_dir / f"test_{idx+1}_{endpoint.method.lower()}_no_auth.txt"
                with open(test_file, "w") as f:
                    f.write(f"Endpoint: {endpoint_url}\n")
                    f.write(f"Method: {endpoint.method}\n")
                    f.write(f"Status: {status_code} {response.reason}\n")
                    f.write(f"\nHeaders:\n")
                    for key, value in headers.items():
                        f.write(f"  {key}: {value}\n")
                    f.write(f"\nBody Preview:\n{body}\n")

                logger.info(
                    f"Endpoint test complete: {status_code} {response.reason}",
                    extra={"endpoint": endpoint_url, "status": status_code}
                )

            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed for {endpoint_url}: {e}")
                test_results.append({
                    "endpoint": endpoint_url,
                    "method": endpoint.method,
                    "status_code": 0,
                    "status_text": "Request Failed",
                    "headers": {},
                    "body_preview": str(e),
                    "test_type": "no_auth"
                })

            # Rate limiting: wait 1 second between requests
            if idx < len(phase1.endpoints) - 1:
                time.sleep(1)

        # Compile test results into COMPACT summary (counts + examples only)
        # The AI just needs to know: auth required? endpoints work? status codes?
        status_codes = {}
        successful = []
        failed = []

        for result in test_results:
            status_code = result['status_code']
            status_codes[status_code] = status_codes.get(status_code, 0) + 1

            if 200 <= status_code < 300:
                successful.append(result)
            else:
                failed.append(result)

        test_results_content = f"# API Endpoint Testing Results (Compact Summary)\n\n"
        test_results_content += f"Total endpoints tested: {len(test_results)}\n"
        test_results_content += f"Successful (2xx): {len(successful)}\n"
        test_results_content += f"Failed/Auth Required: {len(failed)}\n"
        test_results_content += f"Status codes seen: {', '.join([f'{code} ({count}x)' for code, count in sorted(status_codes.items())])}\n\n"

        # Show 2 successful examples (truncated)
        if successful:
            test_results_content += f"=== Successful Responses (showing 2 examples) ===\n"
            for result in successful[:2]:
                test_results_content += f"  {result['method']} {result['endpoint']}: {result['status_code']}\n"
                test_results_content += f"    Response: {result['body_preview'][:200]}\n"

        # Show 2 failed examples (truncated)
        if failed:
            test_results_content += f"\n=== Failed/Auth Required (showing 2 examples) ===\n"
            for result in failed[:2]:
                test_results_content += f"  {result['method']} {result['endpoint']}: {result['status_code']} {result['status_text']}\n"
                test_results_content += f"    Response: {result['body_preview'][:200]}\n"

        logger.info(f"Compiled compact test results: {len(test_results)} endpoints tested, {len(test_results_content)} chars")

        # Call LLM for Phase 2 analysis
        try:
            # Create prompt for Phase 2 testing
            prompt = phase2_prompt(
                url=url,
                test_results_content=test_results_content,
                phase0_result=phase0,
                phase1_result=phase1,
            )

            # Call LLM with structured output
            result = self.llm.invoke_structured(
                prompt=prompt,
                response_model=Phase2Tests,
                system="You are an expert API testing analyst specializing in authentication detection and endpoint validation."
            )

            # Save result
            self.repository.save("phase2_tests.json", result)

            # CRITICAL: Verify file was actually created
            try:
                self.repository.load("phase2_tests.json", Phase2Tests)
                logger.info("Phase 2 result saved and verified")
            except Exception as e:
                raise RuntimeError(f"Failed to save phase2_tests.json - file verification failed: {e}")

            logger.info(
                f"Phase 2 complete: testing analysis generated",
                extra={
                    "url": url,
                    "endpoints_tested": len(test_results),
                },
            )

            return result

        except Exception as e:
            logger.error(
                f"Phase 2 analysis failed: {e}",
                extra={"url": url},
                exc_info=True,
            )
            raise Exception(f"Phase 2 analysis failed for {url}: {e}") from e

    async def analyze_phase3(
        self,
        url: str,
        phase0: Phase0Detection,
        phase1: Phase1Documentation,
        phase2: Phase2Tests,
    ) -> ValidatedSpec:
        """Phase 3: Generate validated specification.

        Cross-checks all phases to produce a validated specification:
        - Compares documentation claims vs test results
        - Identifies discrepancies
        - Calculates confidence score
        - Generates scraper recommendations

        Args:
            url: URL analyzed
            phase0: Phase 0 detection results
            phase1: Phase 1 documentation results
            phase2: Phase 2 test results

        Returns:
            ValidatedSpec with final validated specification

        Raises:
            ValueError: If URL is empty
            Exception: If analysis fails

        Example:
            >>> spec = await analyzer.analyze_phase3(url, phase0, phase1, phase2)
            >>> print(f"Confidence: {spec.validation_summary.confidence_score:.2f}")
        """
        if not url or not url.strip():
            raise ValueError("url cannot be empty")

        logger.info(
            f"Starting Phase 3 validation for {url}",
            extra={
                "phase0_confidence": phase0.confidence,
                "phase1_endpoints": len(phase1.endpoints),
                "phase2_files_saved": len(phase2.files_saved),
            },
        )

        # Call LLM for Phase 3 analysis
        try:
            # Create prompt for Phase 3 validation
            prompt = phase3_prompt(
                url=url,
                phase0=phase0,
                phase1=phase1,
                phase2=phase2,
            )

            # Call LLM with structured output
            result = self.llm.invoke_structured(
                prompt=prompt,
                response_model=ValidatedSpec,
                system="You are an expert data source validation analyst specializing in cross-phase validation and scraper recommendations."
            )

            # Save result
            self.repository.save("validated_datasource_spec.json", result)

            # CRITICAL: Verify file was actually created
            try:
                self.repository.load("validated_datasource_spec.json", ValidatedSpec)
                logger.info("Phase 3 result saved and verified")
            except Exception as e:
                raise RuntimeError(f"Failed to save validated_datasource_spec.json - file verification failed: {e}")

            logger.info(
                f"Phase 3 complete: validated spec generated",
                extra={
                    "url": url,
                    "confidence_score": result.validation_summary.confidence_score,
                    "discrepancies_found": len(result.discrepancies),
                    "endpoints_validated": len(result.endpoints),
                },
            )

            return result

        except Exception as e:
            logger.error(
                f"Phase 3 validation failed: {e}",
                extra={"url": url},
                exc_info=True,
            )
            raise Exception(f"Phase 3 validation failed for {url}: {e}") from e

    async def run_full_analysis(self, url: str) -> ValidatedSpec:
        """Run complete 4-phase analysis.

        Executes all phases sequentially:
        1. Phase 0: Detect data source type
        2. Phase 1: Extract documentation/metadata
        3. Phase 2: Live testing and validation
        4. Phase 3: Generate validated specification

        Args:
            url: URL to analyze

        Returns:
            ValidatedSpec with complete analysis results

        Raises:
            ValueError: If URL is empty
            Exception: If any phase fails

        Example:
            >>> spec = await analyzer.run_full_analysis("https://api.example.com")
            >>> print(f"Analysis complete: {spec.source_type}")
            >>> print(f"Confidence: {spec.validation_summary.confidence_score:.2f}")
            >>> print(f"Ready for scraper: {spec.scraper_recommendation.type}")
        """
        if not url or not url.strip():
            raise ValueError("url cannot be empty")

        logger.info(
            f"Starting full 4-phase analysis for {url}",
            extra={"url": url, "timestamp": datetime.utcnow().isoformat()},
        )

        try:
            # Phase 0: Detection
            phase0 = await self.analyze_phase0(url)
            logger.info(f"Phase 0 complete: {phase0.detected_type}")

            # Phase 1: Documentation
            phase1 = await self.analyze_phase1(url, phase0)
            logger.info(f"Phase 1 complete: {len(phase1.endpoints)} endpoints")

            # Phase 2: Testing
            phase2 = await self.analyze_phase2(url, phase0, phase1)
            logger.info(f"Phase 2 complete: testing analysis done")

            # Phase 3: Validation
            phase3 = await self.analyze_phase3(url, phase0, phase1, phase2)
            logger.info(
                f"Phase 3 complete: confidence {phase3.validation_summary.confidence_score:.2f}"
            )

            logger.info(
                f"Full analysis complete for {url}",
                extra={
                    "url": url,
                    "source_type": phase3.source_type,
                    "confidence": phase3.validation_summary.confidence_score,
                    "endpoints": len(phase3.endpoints),
                    "discrepancies": len(phase3.discrepancies),
                },
            )

            return phase3

        except Exception as e:
            logger.error(
                f"Full analysis failed for {url}: {e}",
                extra={"url": url},
                exc_info=True,
            )
            raise Exception(f"Full analysis failed for {url}: {e}") from e
