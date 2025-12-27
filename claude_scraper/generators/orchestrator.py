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
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass

from claude_scraper.generators.hybrid_generator import HybridGenerator, GeneratedFiles
from claude_scraper.types.errors import (
    OrchestrationError,
    BAAnalysisError,
    GenerationError,
)

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationResult:
    """Result of orchestrated scraper generation.

    Attributes:
        generated_files: Paths to generated scraper files
        ba_spec_path: Path to BA spec used (for audit)
        source_type: Detected source type (API, FTP, WEBSITE, EMAIL)
        confidence_score: BA Analyzer confidence score (if URL was analyzed)
        analysis_performed: Whether BA analysis was performed (vs using existing spec)
    """
    generated_files: GeneratedFiles
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
        hybrid_generator: Optional[HybridGenerator] = None,
        analysis_output_dir: str = "datasource_analysis",
    ):
        """Initialize orchestrator.

        Args:
            hybrid_generator: Generator instance (default: creates new)
            analysis_output_dir: Where BA Analyzer saves specs (default: datasource_analysis)
        """
        self.hybrid_generator = hybrid_generator or HybridGenerator()
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
            GenerationError: If scraper generation fails or BAML not available
            ValueError: If URL is invalid
        """
        if not url or not url.strip():
            raise ValueError("url cannot be empty")

        # Strip whitespace from URL
        url = url.strip()

        logger.info("Starting orchestration for URL", extra={"url": url})

        # Step 1: Run BA Analyzer (import here to avoid circular dependency)
        logger.info("Step 1: Running BA Analyzer on URL", extra={})
        try:
            from claude_scraper.agents.ba_analyzer import BAAnalyzer
            from claude_scraper.storage.repository import AnalysisRepository
            from claude_scraper.tools.botasaurus_tool import BotasaurusTool

            ba_analyzer = BAAnalyzer(
                botasaurus=BotasaurusTool(),
                repository=AnalysisRepository(str(self.analysis_output_dir)),
            )

            validated_spec = await ba_analyzer.run_full_analysis(url)

            logger.info(
                "BA Analysis complete",
                extra={
                    "source_type": validated_spec.source_type,
                    "confidence": validated_spec.validation_summary.confidence_score,
                    "endpoints": len(validated_spec.endpoints or []),
                },
            )
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
            source_type=validated_spec.source_type,
            confidence_score=validated_spec.validation_summary.confidence_score,
            analysis_performed=True,
        )

        logger.info(
            "Orchestration complete",
            extra={
                "scraper_path": str(result.generated_files.scraper_path),
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
            GenerationError: If scraper generation fails or BAML not available
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
                "scraper_path": str(result.generated_files.scraper_path),
                "source_type": result.source_type,
            },
        )

        return result

    async def _generate_scraper(
        self,
        ba_spec_dict: Dict[str, Any],
        output_dir: Optional[Union[str, Path]],
    ) -> GeneratedFiles:
        """Generate scraper using HybridGenerator.

        Routes to appropriate generator based on source_type.
        Currently all source types use HybridGenerator.

        Args:
            ba_spec_dict: BA Analyzer validated spec
            output_dir: Output directory for scraper

        Returns:
            GeneratedFiles with paths to created files

        Raises:
            GenerationError: If generation fails or BAML not available
        """
        source_type = ba_spec_dict.get("source_type", "").upper()

        # Determine output directory with smart default
        if output_dir is None:
            output_dir = self._determine_output_dir(ba_spec_dict)
        else:
            output_dir = Path(output_dir)

        logger.info(
            "Routing to generator for source_type",
            extra={"source_type": source_type, "output_dir": str(output_dir)},
        )

        # Route based on source type
        # Currently all use HybridGenerator
        if source_type in ["API", "FTP", "WEBSITE", "EMAIL"]:
            return await self.hybrid_generator.generate_scraper(
                ba_spec=ba_spec_dict,
                output_dir=output_dir,
            )
        else:
            raise GenerationError(
                f"Unsupported source_type: {source_type}. "
                f"Expected one of: API, FTP, WEBSITE, EMAIL"
            )

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

        Creates: ./sourcing/scraping/{datasource}/{dataset}/

        Args:
            ba_spec: Validated BA spec

        Returns:
            Path to output directory
        """
        from claude_scraper.generators.variable_transformer import VariableTransformer

        transformer = VariableTransformer()
        transformed = transformer.transform(ba_spec)
        source_snake = transformed["template_vars"]["source_snake"]
        dataset_snake = transformed["template_vars"].get("dataset_snake", "data")

        # Use source_snake as datasource (already in snake_case)
        datasource = source_snake
        dataset = dataset_snake

        return Path(f"./sourcing/scraping/{datasource}/{dataset}/")
