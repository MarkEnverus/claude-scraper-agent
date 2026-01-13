"""Orchestrator for scraper generation with BA Analyzer integration.

This module provides a simple orchestrator that:
1. Accepts BA spec file OR source URL
2. If URL provided, triggers BA Analyzer to analyze it
3. Routes to specialist generators based on source_type
4. Handles errors from both BA analysis and generation
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass

from agentic_scraper.generators.hybrid_generator import HybridGenerator, GeneratedFiles
from agentic_scraper.types.errors import (
    OrchestrationError,
    BAAnalysisError,
    GenerationError,
)
from agentic_scraper.llm.factory import LLMFactory
from agentic_scraper.business_analyst.config import BAConfig

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationResult:
    """Result of orchestrated scraper generation.

    Attributes:
        generated_files: List of paths to generated scraper files (supports multi-scraper generation)
        ba_spec_path: Path to BA spec used (for audit)
        source_type: Detected source type (API, FTP, WEBSITE, EMAIL)
        confidence_score: BA Analyzer confidence score (if URL was analyzed)
        analysis_performed: Whether BA analysis was performed (vs using existing spec)
    """
    generated_files: List[GeneratedFiles]
    ba_spec_path: Path
    source_type: str
    confidence_score: Optional[float] = None
    analysis_performed: bool = False


class ScraperOrchestrator:
    """Orchestrator for scraper generation with BA Analyzer integration.

    This orchestrator provides two input modes:
    1. BA spec file path: Load existing validated spec and generate scraper
    2. Source URL: Run BA Analyzer, then generate scraper from output

    The orchestrator routes to appropriate specialist generators based on
    the source_type field in the BA spec:
    - API → HybridGenerator (http_api method)
    - FTP → HybridGenerator (ftp_client method)
    - WEBSITE → HybridGenerator (website_parser method)
    - EMAIL → HybridGenerator (email_collector method)

    Example:
        >>> orchestrator = ScraperOrchestrator()
        >>>
        >>> # Mode 1: Use existing BA spec
        >>> result = orchestrator.generate_from_spec(
        ...     ba_spec_file="datasource_analysis/validated_datasource_spec.json",
        ...     output_dir="generated_scrapers"
        ... )
        >>>
        >>> # Mode 2: Analyze URL first, then generate
        >>> result = await orchestrator.generate_from_url(
        ...     url="https://api.example.com",
        ...     output_dir="generated_scrapers"
        ... )
    """

    def __init__(
        self,
        factory: Optional[LLMFactory] = None,
        hybrid_generator: Optional[HybridGenerator] = None,
        analysis_output_dir: str = "datasource_analysis",
    ):
        """Initialize orchestrator.

        Args:
            factory: LLMFactory for code generation (default: auto-create from BAConfig)
            hybrid_generator: Generator instance (default: creates new with provided factory)
            analysis_output_dir: Where BA Analyzer saves specs (default: datasource_analysis)
        """
        # Auto-create LLMFactory if not provided
        if not factory and not hybrid_generator:
            # Create default BAConfig and LLMFactory
            config = BAConfig()
            factory = LLMFactory(config=config, region=config.aws_region)
            logger.info("Auto-created LLMFactory with default BAConfig for code generation")

        # Create or use provided generator
        if hybrid_generator:
            self.hybrid_generator = hybrid_generator
        else:
            self.hybrid_generator = HybridGenerator(factory=factory)

        self.analysis_output_dir = Path(analysis_output_dir)

        logger.info(
            "Initialized ScraperOrchestrator",
            extra={
                "analysis_dir": str(self.analysis_output_dir),
                "has_hybrid_generator": self.hybrid_generator is not None,
            },
        )

    async def generate_from_url(
        self,
        url: str,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> OrchestrationResult:
        """Generate scraper by analyzing URL with BA Analyzer.

        This method:
        1. Runs BA Analyzer full 4-phase analysis on the URL
        2. Loads the generated validated_datasource_spec.json
        3. Routes to appropriate generator based on source_type
        4. Returns generated scraper files

        Args:
            url: Source URL to analyze
            output_dir: Where to save generated scraper (default: smart default based on source)

        Returns:
            OrchestrationResult with generated files and metadata

        Raises:
            BAAnalysisError: If BA Analyzer fails
            GenerationError: If scraper generation fails
            ValueError: If URL is invalid
        """
        if not url or not url.strip():
            raise ValueError("url cannot be empty")

        # Strip whitespace from URL
        url = url.strip()

        logger.info("Starting orchestration for URL", extra={"url": url})

        # Step 1: Run BA Analyzer (using new business_analyst system)
        logger.info("Step 1: Running BA Analyzer on URL", extra={})
        try:
            from agentic_scraper.business_analyst.cli import run_analysis
            from agentic_scraper.business_analyst.config import BAConfig
            from urllib.parse import urlparse

            # Extract domain from URL
            parsed = urlparse(url)
            allowed_domains = [parsed.netloc]

            # Create BA config
            config = BAConfig(render_mode="auto")

            # Run new BA analyzer
            logger.info(f"Running new LangGraph BA Analyzer on {url}")
            final_state = run_analysis(
                seed_url=url,
                max_depth=2,
                allowed_domains=allowed_domains,
                output_dir=str(self.analysis_output_dir),
                config=config
            )

            logger.info(
                "BA Analysis complete",
                extra={
                    "pages_visited": len(final_state.get("visited", [])),
                    "endpoints_found": len(final_state.get("endpoints", [])),
                    "stop_reason": final_state.get("stop_reason", "unknown"),
                },
            )

            # Note: New BA system already generates site_report.md
            # No need for separate executive summary generation

        except Exception as e:
            logger.error("BA Analyzer failed", extra={"url": url, "error": str(e)}, exc_info=True)
            raise BAAnalysisError(f"BA Analyzer failed for {url}: {e}") from e

        # Step 2: Load BA spec from saved file
        spec_path = self.analysis_output_dir / "validated_datasource_spec.json"

        # Load spec file (will raise FileNotFoundError if missing)
        try:
            ba_spec_dict = self._load_ba_spec_file(spec_path)
        except FileNotFoundError:
            raise BAAnalysisError(
                f"BA Analyzer did not create expected output file: {spec_path}"
            )

        # Step 3: Generate scraper using loaded spec
        logger.info("Step 2: Generating scraper from BA spec", extra={})
        try:
            generated = await self._generate_scraper(
                ba_spec_dict=ba_spec_dict,
                output_dir=output_dir,
            )
        except Exception as e:
            logger.error("Scraper generation failed", extra={"url": url, "error": str(e)}, exc_info=True)
            raise GenerationError(f"Scraper generation failed: {e}") from e

        # Step 4: Return result
        result = OrchestrationResult(
            generated_files=generated,
            ba_spec_path=spec_path,
            source_type=ba_spec_dict.get("source_type", "UNKNOWN"),
            confidence_score=ba_spec_dict.get("confidence_score"),
            analysis_performed=True,
        )

        logger.info(
            "Orchestration complete",
            extra={
                "scrapers_generated": len(result.generated_files),
                "scraper_paths": [str(gf.scraper_path) for gf in result.generated_files],
                "source_type": result.source_type,
                "confidence": result.confidence_score,
            },
        )

        return result

    async def generate_from_spec(
        self,
        ba_spec_file: Union[str, Path],
        output_dir: Optional[Union[str, Path]] = None,
    ) -> OrchestrationResult:
        """Generate scraper from existing BA spec file.

        This method:
        1. Loads existing validated BA spec from file
        2. Routes to appropriate generator based on source_type
        3. Returns generated scraper files

        Args:
            ba_spec_file: Path to validated_datasource_spec.json
            output_dir: Where to save generated scraper (default: smart default based on source)

        Returns:
            OrchestrationResult with generated files and metadata

        Raises:
            GenerationError: If scraper generation fails
            FileNotFoundError: If BA spec file doesn't exist
            ValueError: If BA spec is invalid
        """
        spec_path = Path(ba_spec_file)

        if not spec_path.exists():
            raise FileNotFoundError(f"BA spec file not found: {spec_path}")

        logger.info("Starting orchestration from BA spec", extra={"spec_path": str(spec_path)})

        # Step 1: Load BA spec
        ba_spec_dict = self._load_ba_spec_file(spec_path)

        # Step 2: Generate scraper
        logger.info("Generating scraper from BA spec", extra={})
        try:
            generated = await self._generate_scraper(
                ba_spec_dict=ba_spec_dict,
                output_dir=output_dir,
            )
        except Exception as e:
            logger.error("Scraper generation failed", extra={"spec_path": str(spec_path), "error": str(e)}, exc_info=True)
            raise GenerationError(f"Scraper generation failed: {e}") from e

        # Step 3: Return result
        source_type = ba_spec_dict.get("source_type", "UNKNOWN")
        confidence = ba_spec_dict.get("validation_summary", {}).get("confidence_score")

        result = OrchestrationResult(
            generated_files=generated,
            ba_spec_path=spec_path,
            source_type=source_type,
            confidence_score=confidence,
            analysis_performed=False,
        )

        logger.info(
            "Orchestration complete",
            extra={
                "scrapers_generated": len(result.generated_files),
                "scraper_paths": [str(gf.scraper_path) for gf in result.generated_files],
                "source_type": result.source_type,
            },
        )

        return result

    async def _generate_scraper(
        self,
        ba_spec_dict: Dict[str, Any],
        output_dir: Optional[Union[str, Path]],
    ) -> List[GeneratedFiles]:
        """Generate scraper(s) using HybridGenerator.

        For multi-endpoint specs, generates one scraper per endpoint.
        Routes to appropriate generator based on source_type.
        Currently all source types use HybridGenerator.

        Args:
            ba_spec_dict: BA Analyzer validated spec
            output_dir: Output directory for scraper(s)

        Returns:
            List of GeneratedFiles (one per scraper)

        Raises:
            GenerationError: If generation fails
        """
        source_type = ba_spec_dict.get("source_type", "").upper()
        endpoints = ba_spec_dict.get("endpoints", [])

        # Validate source type
        if source_type not in ["API", "FTP", "WEBSITE", "EMAIL"]:
            raise GenerationError(
                f"Unsupported source_type: {source_type}. "
                f"Expected one of: API, FTP, WEBSITE, EMAIL"
            )

        if not endpoints:
            raise GenerationError("BA spec has no endpoints")

        # Determine base output directory
        if output_dir is None:
            output_dir = self._determine_output_dir(ba_spec_dict)
        else:
            output_dir = Path(output_dir)

        # Multi-endpoint: generate one scraper per endpoint
        if len(endpoints) > 1:
            logger.info(
                f"Multi-endpoint spec detected: generating {len(endpoints)} scrapers",
                extra={"source_type": source_type, "endpoint_count": len(endpoints)},
            )
            results = []

            for i, endpoint in enumerate(endpoints, 1):
                # Use endpoint_id (contains specific operation) instead of name (may be generic)
                endpoint_name = endpoint.get("endpoint_id", endpoint.get("name", f"endpoint_{i}"))
                logger.info(f"Generating scraper {i}/{len(endpoints)}: {endpoint_name}")

                # Create single-endpoint BA spec (preserve original dataset)
                single_endpoint_spec = {
                    **ba_spec_dict,
                    "endpoints": [endpoint],
                    # Keep original dataset, add endpoint_name for path generation
                    "_endpoint_name": endpoint_name,  # Pass to _determine_output_dir
                }

                # Determine unique output directory for this endpoint
                # Always use monorepo structure: {base}/sourcing/scraping/{datasource}/{dataset}/{endpoint_snake}/
                monorepo_path = self._determine_output_dir(single_endpoint_spec)

                if output_dir is not None:
                    # User specified output_dir - use it as base, then add monorepo structure
                    endpoint_output_dir = output_dir / monorepo_path
                else:
                    # No output_dir specified - use monorepo structure from current directory
                    endpoint_output_dir = monorepo_path

                # Generate scraper for this endpoint
                generated_files = await self.hybrid_generator.generate_scraper(
                    ba_spec=single_endpoint_spec,
                    output_dir=endpoint_output_dir,
                )
                results.append(generated_files)

                logger.info(f"✓ Generated scraper {i}/{len(endpoints)}: {generated_files.scraper_path}")

            return results

        # Single endpoint: generate one scraper
        else:
            logger.info(
                "Single-endpoint spec detected: generating 1 scraper",
                extra={"source_type": source_type, "output_dir": str(output_dir)},
            )
            generated_files = await self.hybrid_generator.generate_scraper(
                ba_spec=ba_spec_dict,
                output_dir=output_dir,
            )
            return [generated_files]

    def _load_ba_spec_file(self, spec_path: Path) -> Dict[str, Any]:
        """Load and validate BA spec from JSON file.

        Args:
            spec_path: Path to validated_datasource_spec.json

        Returns:
            BA spec as dictionary

        Raises:
            ValueError: If spec is invalid
        """
        try:
            with open(spec_path, "r", encoding="utf-8") as f:
                ba_spec = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in BA spec file: {e}") from e

        # Validate required fields
        errors = self.hybrid_generator.validate_ba_spec(ba_spec)
        if errors:
            raise ValueError(
                f"BA spec validation failed:\n" + "\n".join(f"  - {err}" for err in errors)
            )

        return ba_spec

    def _determine_output_dir(self, ba_spec: Dict[str, Any]) -> Path:
        """Determine smart output directory from BA spec.

        Creates:
        - Single endpoint: ./sourcing/scraping/{datasource}/{dataset}/
        - Multi-endpoint: ./sourcing/scraping/{datasource}/{dataset}/{endpoint}/

        Args:
            ba_spec: Validated BA spec

        Returns:
            Path to output directory
        """
        from agentic_scraper.generators.variable_transformer import VariableTransformer

        transformer = VariableTransformer()
        transformed = transformer.transform(ba_spec)

        # Use datasource_snake from BA spec (preferred) or fall back to source_snake
        datasource = transformed["template_vars"].get("datasource_snake") or \
                     ba_spec.get("datasource") or \
                     transformed["template_vars"]["source_snake"]
        dataset = transformed["template_vars"].get("dataset_snake", "data")

        # For multi-endpoint specs, append endpoint name to path
        endpoint_name = ba_spec.get("_endpoint_name")
        if endpoint_name:
            # Convert endpoint name to snake_case for path
            endpoint_snake = transformer._to_snake_case(endpoint_name)
            return Path(f"./sourcing/scraping/{datasource}/{dataset}/{endpoint_snake}/")

        return Path(f"./sourcing/scraping/{datasource}/{dataset}/")
