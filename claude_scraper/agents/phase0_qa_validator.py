"""Phase 0 QA Validator Agent.

This module provides the Phase0QAValidator class for independently validating
Phase 0 detection results using vision-based operation counting.

The validator uses Claude's vision capabilities to count operations visible
in the main API screenshot and compares that count against the number of
endpoints actually discovered. This catches counting errors and missing operations.

Example:
    >>> from claude_scraper.agents.phase0_qa_validator import Phase0QAValidator
    >>> from claude_scraper.llm.anthropic import AnthropicProvider
    >>>
    >>> llm = AnthropicProvider(config)
    >>> validator = Phase0QAValidator(llm)
    >>> report = validator.validate(
    ...     main_screenshot="/path/to/screenshot.png",
    ...     discovered_endpoint_urls=["url1", "url2", ...],
    ...     primary_api_name="Pricing API"
    ... )
    >>> if not report.is_complete:
    ...     print(f"Warning: {report.validation_notes}")
"""

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from claude_scraper.llm.base import LLMProvider
from claude_scraper.prompts.ba_analyzer import phase0_qa_validation_prompt

logger = logging.getLogger(__name__)


class Phase0ValidationReport(BaseModel):
    """Validation report for Phase 0 detection results.

    This model represents the results of independently counting operations
    visible in the main API screenshot and comparing against discovered endpoints.

    Attributes:
        operations_visible_in_screenshot: Total operations counted in screenshot
        operations_discovered: Total endpoint URLs discovered in Phase 0
        is_complete: True if counts match (validation passed)
        missing_operations: Names of operations visible but not discovered (if any)
        confidence: Confidence in the count (0.0-1.0)
        validation_notes: Human-readable explanation of validation results

    Example:
        >>> report = Phase0ValidationReport(
        ...     operations_visible_in_screenshot=10,
        ...     operations_discovered=9,
        ...     is_complete=False,
        ...     missing_operations=["Get Resource Data"],
        ...     confidence=0.95,
        ...     validation_notes="One operation visible in screenshot but not discovered"
        ... )
    """

    operations_visible_in_screenshot: int = Field(
        description="Total number of operations counted in the main API screenshot"
    )
    operations_discovered: int = Field(
        description="Total number of endpoint URLs discovered in Phase 0"
    )
    is_complete: bool = Field(
        description="True if visible operations match discovered count"
    )
    missing_operations: list[str] = Field(
        description="Names of operations visible in screenshot but not discovered",
        default_factory=list
    )
    confidence: float = Field(
        description="Confidence in the count accuracy (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    validation_notes: str = Field(
        description="Human-readable explanation of validation results"
    )


class Phase0QAValidator:
    """QA validator for Phase 0 detection results.

    This class uses Claude's vision capabilities to independently count
    operations visible in the main API documentation screenshot and compare
    that count against the number of endpoints actually discovered.

    This provides defense-in-depth validation to catch counting errors,
    missing operations, or other Phase 0 discovery issues.

    Attributes:
        llm: LLM provider for vision-based structured calls

    Example:
        >>> llm_provider = AnthropicProvider(config)
        >>> validator = Phase0QAValidator(llm_provider)
        >>> report = validator.validate(
        ...     main_screenshot="/tmp/page_screenshot.png",
        ...     discovered_endpoint_urls=["url1", "url2"],
        ...     primary_api_name="Test API"
        ... )
        >>> print(report.is_complete)
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        """Initialize Phase0 QA Validator.

        Args:
            llm_provider: LLM provider for vision-based structured calls
                         (Bedrock or Anthropic)

        Example:
            >>> from claude_scraper.llm.anthropic import AnthropicProvider
            >>> llm = AnthropicProvider(config)
            >>> validator = Phase0QAValidator(llm)
        """
        self.llm = llm_provider
        logger.info("Initialized Phase0QAValidator")

    def validate(
        self,
        main_screenshot: str | Path,
        discovered_endpoint_urls: list[str],
        primary_api_name: str = ""
    ) -> Phase0ValidationReport:
        """Validate Phase 0 results using vision-based operation counting.

        Uses Claude's vision capabilities to independently count operations
        visible in the main screenshot and compares against discovered endpoints.

        Args:
            main_screenshot: Path to main API overview screenshot
            discovered_endpoint_urls: List of endpoint URLs discovered in Phase 0
            primary_api_name: Optional name of primary API for context

        Returns:
            Phase0ValidationReport with validation results

        Raises:
            FileNotFoundError: If screenshot file doesn't exist
            Exception: If validation fails

        Example:
            >>> report = validator.validate(
            ...     main_screenshot="/tmp/api_screenshot.png",
            ...     discovered_endpoint_urls=["url1", "url2", "url3"],
            ...     primary_api_name="Data API"
            ... )
            >>> if not report.is_complete:
            ...     logger.warning(f"Missing operations: {report.missing_operations}")
        """
        screenshot_path = Path(main_screenshot)

        if not screenshot_path.exists():
            raise FileNotFoundError(
                f"Screenshot not found: {screenshot_path}"
            )

        discovered_count = len(discovered_endpoint_urls)

        logger.info(
            "Running Phase 0 QA validation",
            extra={
                "screenshot": str(screenshot_path),
                "discovered_count": discovered_count,
                "primary_api": primary_api_name
            }
        )

        try:
            # Create validation prompt
            prompt = phase0_qa_validation_prompt(
                primary_api_name=primary_api_name,
                discovered_count=discovered_count
            )

            # Use vision to independently count operations
            report = self.llm.invoke_structured_with_vision(
                prompt=prompt,
                images=[str(screenshot_path)],
                response_model=Phase0ValidationReport,
                system=(
                    "You are a meticulous QA validator. Your job is to carefully "
                    "count ALL operations visible in the API documentation screenshot "
                    "and identify any discrepancies with what was discovered."
                )
            )

            # Log validation results
            if report.is_complete:
                logger.info(
                    "✅ Phase 0 validation PASSED - All operations discovered",
                    extra={
                        "visible_count": report.operations_visible_in_screenshot,
                        "discovered_count": report.operations_discovered,
                        "confidence": report.confidence
                    }
                )
            else:
                logger.warning(
                    f"⚠️  Phase 0 validation FAILED - Discrepancy detected",
                    extra={
                        "visible_count": report.operations_visible_in_screenshot,
                        "discovered_count": report.operations_discovered,
                        "missing_operations": report.missing_operations,
                        "confidence": report.confidence,
                        "notes": report.validation_notes
                    }
                )

            return report

        except Exception as e:
            logger.error(
                f"Phase 0 validation failed with error: {e}",
                exc_info=True,
                extra={"screenshot": str(screenshot_path)}
            )
            raise Exception(f"Phase 0 QA validation failed: {e}") from e
