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

from baml_client import b
from baml_client.types import (
    Phase0Detection,
    Phase1Documentation,
    Phase2Tests,
    ValidatedSpec,
)
from claude_scraper.storage.repository import AnalysisRepository
from claude_scraper.tools.botasaurus_tool import BotasaurusTool

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
        botasaurus: Optional[BotasaurusTool] = None,
        repository: Optional[AnalysisRepository] = None,
    ) -> None:
        """Initialize BA analyzer.

        Args:
            botasaurus: Botasaurus tool for browser automation (handles all network calls)
            repository: Optional repository for saving artifacts (default: datasource_analysis/)
        """
        self.botasaurus = botasaurus or BotasaurusTool()  # Create default if not provided
        self.repository = repository or AnalysisRepository("datasource_analysis")

        logger.info(
            "Initialized BAAnalyzer",
            extra={
                "has_botasaurus": self.botasaurus is not None,
                "repository_path": self.repository.base_dir,
            },
        )

    async def analyze_phase0(self, url: str) -> Phase0Detection:
        """Phase 0: Detect data source type.

        Analyzes the URL to determine if it's an API, FTP server, website portal,
        or email source. Uses network traffic monitoring and HTML analysis.

        Args:
            url: URL to analyze

        Returns:
            Phase0Detection with type, confidence, indicators, and discovered endpoints

        Raises:
            ValueError: If URL is empty
            Exception: If analysis fails

        Example:
            >>> phase0 = await analyzer.analyze_phase0("https://api.example.com")
            >>> print(phase0.detected_type)
            DataSourceType.API
        """
        if not url or not url.strip():
            raise ValueError("url cannot be empty")

        logger.info(f"Starting Phase 0 analysis for {url}")

        # Fetch HTML content using Botasaurus (handles JavaScript)
        html_content = ""
        network_calls: list[str] = []

        try:
            logger.info("Using Botasaurus to fetch page content with JavaScript execution")
            html_content = self.botasaurus.get_page_content(url)
            logger.info(
                f"Botasaurus fetched HTML content",
                extra={"url": url, "html_bytes": len(html_content)},
            )

            # Also extract network calls
            logger.info("Extracting network calls via Botasaurus")
            network_calls = self.botasaurus.extract_network_calls(url)
            logger.info(
                f"Discovered {len(network_calls)} network calls",
                extra={"url": url, "count": len(network_calls)},
            )
        except Exception as e:
            logger.warning(
                f"Botasaurus failed, using empty content: {e}",
                extra={"url": url},
            )
            html_content = ""
            network_calls = []

        # Call BAML function for Phase 0 analysis
        try:
            result = await b.AnalyzePhase0(
                url=url,
                html_content=html_content,
                network_calls=network_calls,
            )

            # Save result
            self.repository.save("phase0_detection.json", result)

            # CRITICAL: Verify file was actually created
            try:
                self.repository.load("phase0_detection.json", Phase0Detection)
                logger.info("Phase 0 result saved and verified")
            except Exception as e:
                raise RuntimeError(f"Failed to save phase0_detection.json - file verification failed: {e}")

            logger.info(
                f"Phase 0 complete: {result.detected_type} (confidence: {result.confidence:.2f})",
                extra={
                    "url": url,
                    "detected_type": result.detected_type,
                    "confidence": result.confidence,
                    "endpoints_found": len(result.endpoints),
                },
            )

            return result

        except Exception as e:
            logger.error(
                f"Phase 0 analysis failed: {e}",
                extra={"url": url},
                exc_info=True,
            )
            raise Exception(f"Phase 0 analysis failed for {url}: {e}") from e

    async def analyze_phase1(
        self, url: str, phase0: Phase0Detection
    ) -> Phase1Documentation:
        """Phase 1: Analyze documentation/metadata.

        Extracts detailed information about the data source:
        - For APIs: Endpoints, parameters, authentication requirements
        - For websites: Download links, file formats, access requirements
        - For FTP/Email: Connection details, data formats

        Args:
            url: URL to analyze
            phase0: Phase 0 detection results

        Returns:
            Phase1Documentation with extracted metadata

        Raises:
            ValueError: If URL is empty
            Exception: If analysis fails

        Example:
            >>> phase1 = await analyzer.analyze_phase1(url, phase0)
            >>> print(f"Found {len(phase1.endpoints)} endpoints")
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
        documentation_content = ""

        try:
            logger.info("Using Botasaurus to fetch documentation content")
            documentation_content = self.botasaurus.get_page_content(url)
            logger.info(
                f"Botasaurus fetched documentation content",
                extra={"url": url, "html_bytes": len(documentation_content)},
            )
        except Exception as e:
            logger.warning(
                f"Botasaurus failed for Phase 1: {e}",
                extra={"url": url},
            )
            documentation_content = ""

        # Call BAML function for Phase 1 analysis
        try:
            result = await b.AnalyzePhase1(
                url=url,
                documentation_content=documentation_content,
                phase0_result=phase0,
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
                    "doc_quality": result.doc_quality,
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

        # Compile test results into summary text
        test_results_content = f"# API Endpoint Testing Results\n\n"
        test_results_content += f"Total endpoints tested: {len(test_results)}\n"
        test_results_content += f"Test directory: {test_dir}\n\n"

        for result in test_results:
            test_results_content += f"\n## Endpoint: {result['endpoint']}\n"
            test_results_content += f"Method: {result['method']}\n"
            test_results_content += f"Test Type: {result['test_type']}\n"
            test_results_content += f"Status Code: {result['status_code']} {result['status_text']}\n"
            test_results_content += f"\nResponse Headers:\n"
            for key, value in result['headers'].items():
                test_results_content += f"  {key}: {value}\n"
            test_results_content += f"\nBody Preview:\n{result['body_preview']}\n"
            test_results_content += "\n---\n"

        logger.info(f"Compiled test results: {len(test_results)} endpoints tested")

        # Call BAML function for Phase 2 analysis
        try:
            result = await b.AnalyzePhase2(
                url=url,
                test_results_content=test_results_content,
                phase0_result=phase0,
                phase1_result=phase1,
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

        # Call BAML function for Phase 3 analysis
        try:
            result = await b.AnalyzePhase3(
                url=url,
                phase0=phase0,
                phase1=phase1,
                phase2=phase2,
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
