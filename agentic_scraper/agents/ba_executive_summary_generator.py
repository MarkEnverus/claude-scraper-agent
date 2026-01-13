"""BA Executive Summary Generator Agent.

This module provides the BAExecutiveSummaryGenerator class for creating
markdown executive summaries from validated specifications.

The generator produces a JIRA-ready markdown document summarizing:
- Data source overview
- Endpoint inventory (table format)
- Authentication requirements
- Key findings and discrepancies
- Scraper implementation plan
- Next steps

Example:
    >>> from agentic_scraper.agents.ba_executive_summary_generator import BAExecutiveSummaryGenerator
    >>> from agentic_scraper.storage.repository import AnalysisRepository
    >>>
    >>> generator = BAExecutiveSummaryGenerator()
    >>> markdown = await generator.generate_summary(validated_spec)
    >>> print(f"Generated {len(markdown)} characters of markdown")
"""

import logging
from pathlib import Path

from agentic_scraper.llm.factory import LLMFactory
from agentic_scraper.types import ValidatedSpec
from agentic_scraper.prompts.ba_executive_summary import generate_executive_summary_prompt
from agentic_scraper.storage.repository import AnalysisRepository

logger = logging.getLogger(__name__)


class BAExecutiveSummaryGenerator:
    """Generator for executive summary markdown documents.

    This class generates human-readable executive summaries from validated
    specifications, producing JIRA/Confluence-compatible markdown output.

    Attributes:
        repository: File repository for saving analysis files
        OUTPUT_FILENAME: Default filename for executive summary

    Example:
        >>> generator = BAExecutiveSummaryGenerator()
        >>> markdown = await generator.generate_summary(validated_spec)
        >>> # Markdown is automatically saved to datasource_analysis/executive_summary.md
    """

    OUTPUT_FILENAME = "executive_summary.md"

    def __init__(
        self,
        factory: LLMFactory,
        repository: AnalysisRepository | None = None,
        base_dir: str | Path = "datasource_analysis"
    ) -> None:
        """Initialize Executive Summary Generator.

        Args:
            factory: LLMFactory for creating reasoning model (quality writing)
            repository: Optional repository for file operations. If None, creates new one.
            base_dir: Base directory for analysis files (default: "datasource_analysis")

        Example:
            >>> from agentic_scraper.llm.factory import LLMFactory
            >>> from agentic_scraper.business_analyst.config import BAConfig
            >>> config = BAConfig()
            >>> factory = LLMFactory(config=config, region=config.aws_region)
            >>> generator = BAExecutiveSummaryGenerator(factory)
        """
        self.factory = factory
        self.llm = factory.create_reasoning_model()  # Haiku with extended thinking for quality writing
        self.repository = repository or AnalysisRepository(base_dir)
        logger.info(
            "Initialized BAExecutiveSummaryGenerator",
            extra={"base_dir": str(base_dir)}
        )

    async def generate_summary(
        self,
        validated_spec: ValidatedSpec,
        save_result: bool = True
    ) -> str:
        """Generate markdown executive summary from validated specification.

        Uses Claude's structured outputs to produce a comprehensive markdown
        document suitable for JIRA/Confluence.

        Args:
            validated_spec: Validated specification from collation
            save_result: If True, save markdown to executive_summary.md (default: True)

        Returns:
            Markdown string containing executive summary

        Raises:
            Exception: If summary generation fails

        Example:
            >>> markdown = await generator.generate_summary(validated_spec)
            >>> print(f"Generated summary with {markdown.count('#')} sections")
        """
        logger.info(
            "Generating executive summary",
            extra={
                "source": validated_spec.source,
                "endpoints": len(validated_spec.endpoints),
                "confidence": validated_spec.validation_summary.confidence_score
            }
        )

        try:
            # Create prompt for executive summary generation
            prompt = generate_executive_summary_prompt(validated_spec=validated_spec)

            # Call LLM to generate markdown (returns plain string, not structured)
            markdown = self.factory.invoke_text(
                model=self.llm,
                prompt=prompt,
                system="You are an expert technical writer specializing in creating clear, comprehensive executive summaries for business stakeholders."
            )

            logger.info(
                "Executive summary generated successfully",
                extra={
                    "markdown_length": len(markdown),
                    "line_count": markdown.count('\n'),
                    "has_tables": '|' in markdown
                }
            )

            # Save markdown to file
            if save_result:
                output_path = Path(self.repository.base_dir) / self.OUTPUT_FILENAME
                output_path.write_text(markdown, encoding="utf-8")
                logger.info(
                    f"Saved executive summary to {output_path.absolute()}",
                    extra={"file": self.OUTPUT_FILENAME}
                )

            return markdown

        except Exception as e:
            logger.error(
                f"Failed to generate executive summary: {e}",
                exc_info=True,
                extra={"source": validated_spec.source}
            )
            raise Exception(f"Executive summary generation failed: {e}") from e

    def get_summary_path(self) -> Path:
        """Get the full path where executive summary will be saved.

        Returns:
            Path object for executive_summary.md

        Example:
            >>> path = generator.get_summary_path()
            >>> print(f"Summary will be saved to: {path}")
        """
        return Path(self.repository.base_dir) / self.OUTPUT_FILENAME
