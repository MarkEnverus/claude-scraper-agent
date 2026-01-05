"""BA Validator Agent - Validates Business Analyst analysis results.

This module implements the validation agent that checks BA analysis outputs
for completeness, assigns confidence scores, and determines if a second
analysis run is needed.

The validator uses Claude's structured outputs to perform LLM-based validation
of each phase and the complete specification.

Example:
    >>> from claude_scraper.agents.ba_validator import BAValidator
    >>> from claude_scraper.llm import create_llm_provider
    >>> from claude_scraper.types import Phase0Detection, ValidatedSpec
    >>>
    >>> llm_provider = create_llm_provider("bedrock", config)
    >>> validator = BAValidator(llm_provider)
    >>>
    >>> # Validate Phase 0
    >>> phase0 = Phase0Detection(...)
    >>> result = await validator.validate_phase0(phase0, "https://example.com")
    >>>
    >>> # Validate complete spec
    >>> spec = ValidatedSpec(...)
    >>> report = await validator.validate_complete_spec(spec)
    >>>
    >>> # Check if Run 2 is needed
    >>> if validator.should_run_second_analysis(report):
    ...     focus_areas = validator.get_run2_focus_areas(report)
"""

import logging
from datetime import datetime, timezone
from typing import Any

from claude_scraper.llm.base import LLMProvider
from claude_scraper.types import (
    Phase0Detection,
    Phase1Documentation,
    Phase2Tests,
    ValidatedSpec,
    ValidationReport,
    ValidationResult,
    ValidationOverallStatus,
    PhaseValidation,
    CriticalGap,
)
from claude_scraper.prompts.ba_validator import (
    validate_phase0_prompt,
    validate_phase1_prompt,
    validate_phase2_prompt,
    validate_complete_spec_prompt,
)
from claude_scraper.storage.repository import AnalysisRepository

logger = logging.getLogger(__name__)

# Confidence threshold for triggering Run 2 (from plan)
RUN2_CONFIDENCE_THRESHOLD = 0.8


class BAValidator:
    """Validator for Business Analyst analysis results.

    This class provides methods to validate each phase of the BA analysis
    (Phase 0-2) and the complete specification. It uses BAML functions to
    perform LLM-based validation and provides decision logic for determining
    if a second analysis run is needed.

    Attributes:
        repository: Repository for saving/loading analysis artifacts
        confidence_threshold: Confidence threshold for triggering Run 2 (default: 0.8)

    Example:
        >>> validator = BAValidator()
        >>> report = await validator.validate_complete_spec(spec)
        >>> if validator.should_run_second_analysis(report):
        ...     print("Second run required")
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        repository: AnalysisRepository | None = None,
        confidence_threshold: float = RUN2_CONFIDENCE_THRESHOLD
    ):
        """Initialize BA Validator.

        Args:
            llm_provider: LLM provider for structured LLM calls (Bedrock or Anthropic)
            repository: Optional repository for persistence. If None, uses default.
            confidence_threshold: Confidence threshold for Run 2 decision (default: 0.8)

        Raises:
            ValueError: If confidence_threshold is not between 0.0 and 1.0
        """
        if confidence_threshold < 0.0:
            raise ValueError(f"confidence_threshold must be >= 0.0, got {confidence_threshold}")
        elif confidence_threshold > 1.0:
            raise ValueError(f"confidence_threshold must be <= 1.0, got {confidence_threshold}")

        self.llm = llm_provider
        self.repository = repository or AnalysisRepository()
        self.confidence_threshold = confidence_threshold

        logger.debug(
            f"Initialized BAValidator with confidence_threshold={confidence_threshold}",
            extra={"threshold": confidence_threshold}
        )

    async def validate_phase0(
        self,
        phase0: Phase0Detection,
        original_url: str
    ) -> dict[str, Any]:
        """Validate Phase 0 detection results.

        Validates that the data source type detection is plausible, has
        sufficient indicators, and appropriate confidence score.

        Args:
            phase0: Phase 0 detection results
            original_url: Original URL being analyzed

        Returns:
            Dictionary with validation results including confidence, gaps, and recommendations

        Raises:
            Exception: If BAML function call fails

        Example:
            >>> phase0 = Phase0Detection(
            ...     detected_type=DataSourceType.API,
            ...     confidence=0.95,
            ...     indicators=["REST endpoints", "JSON responses"],
            ...     discovered_api_calls=["https://api.example.com/v1/data"],
            ...     endpoints=[],
            ...     url="https://api.example.com"
            ... )
            >>> result = await validator.validate_phase0(phase0, "https://api.example.com")
            >>> print(result["confidence"])
        """
        logger.info(
            f"Validating Phase 0 results for {original_url}",
            extra={"url": original_url, "detected_type": phase0.detected_type}
        )

        try:
            # Create prompt for Phase 0 validation
            prompt = validate_phase0_prompt(
                phase0_result=phase0,
                original_url=original_url
            )

            # Call LLM with structured output
            result = self.llm.invoke_structured(
                prompt=prompt,
                response_model=ValidationResult,
                system="You are an expert validation analyst specializing in data source detection validation."
            )

            logger.info(
                f"Phase 0 validation complete: confidence={result.confidence:.2f}, "
                f"gaps={len(result.identified_gaps)}",
                extra={
                    "confidence": result.confidence,
                    "gaps_count": len(result.identified_gaps),
                    "recommendations_count": len(result.recommendations)
                }
            )

            # Convert to dict for easier handling
            return {
                "confidence": result.confidence,
                "identified_gaps": result.identified_gaps,
                "recommendations": result.recommendations,
                "validation_notes": result.validation_notes
            }

        except Exception as e:
            logger.error(
                f"Failed to validate Phase 0: {e}",
                extra={"url": original_url},
                exc_info=True
            )
            raise

    async def validate_phase1(
        self,
        phase1: Phase1Documentation,
        phase0: Phase0Detection
    ) -> dict[str, Any]:
        """Validate Phase 1 documentation results.

        Validates that documentation extraction is complete, consistent with
        Phase 0, and has appropriate quality.

        Args:
            phase1: Phase 1 documentation results
            phase0: Phase 0 detection results for context

        Returns:
            Dictionary with validation results

        Raises:
            Exception: If BAML function call fails

        Example:
            >>> result = await validator.validate_phase1(phase1, phase0)
            >>> if result["confidence"] < 0.8:
            ...     print("Phase 1 needs improvement")
        """
        logger.info(
            "Validating Phase 1 documentation results",
            extra={
                "endpoints_count": len(phase1.endpoints),
                "doc_quality": phase1.doc_quality
            }
        )

        try:
            # Create prompt for Phase 1 validation
            prompt = validate_phase1_prompt(
                phase1_result=phase1,
                phase0_result=phase0
            )

            # Call LLM with structured output
            result = self.llm.invoke_structured(
                prompt=prompt,
                response_model=ValidationResult,
                system="You are an expert validation analyst specializing in documentation extraction validation."
            )

            logger.info(
                f"Phase 1 validation complete: confidence={result.confidence:.2f}, "
                f"gaps={len(result.identified_gaps)}",
                extra={
                    "confidence": result.confidence,
                    "gaps_count": len(result.identified_gaps)
                }
            )

            return {
                "confidence": result.confidence,
                "identified_gaps": result.identified_gaps,
                "recommendations": result.recommendations,
                "validation_notes": result.validation_notes
            }

        except Exception as e:
            logger.error(
                f"Failed to validate Phase 1: {e}",
                exc_info=True
            )
            raise

    async def validate_phase2(
        self,
        phase2: Phase2Tests,
        phase1: Phase1Documentation
    ) -> dict[str, Any]:
        """Validate Phase 2 testing results.

        Validates that live testing was performed with actual evidence,
        results are consistent with Phase 1, and conclusions are justified.

        Args:
            phase2: Phase 2 testing results
            phase1: Phase 1 documentation for context

        Returns:
            Dictionary with validation results

        Raises:
            Exception: If BAML function call fails

        Example:
            >>> result = await validator.validate_phase2(phase2, phase1)
            >>> for gap in result["identified_gaps"]:
            ...     print(gap)
        """
        logger.info(
            "Validating Phase 2 testing results",
            extra={"files_saved": len(phase2.files_saved)}
        )

        try:
            # Create prompt for Phase 2 validation
            prompt = validate_phase2_prompt(
                phase2_result=phase2,
                phase1_result=phase1
            )

            # Call LLM with structured output
            result = self.llm.invoke_structured(
                prompt=prompt,
                response_model=ValidationResult,
                system="You are an expert validation analyst specializing in API testing and authentication validation."
            )

            logger.info(
                f"Phase 2 validation complete: confidence={result.confidence:.2f}, "
                f"gaps={len(result.identified_gaps)}",
                extra={
                    "confidence": result.confidence,
                    "gaps_count": len(result.identified_gaps)
                }
            )

            return {
                "confidence": result.confidence,
                "identified_gaps": result.identified_gaps,
                "recommendations": result.recommendations,
                "validation_notes": result.validation_notes
            }

        except Exception as e:
            logger.error(
                f"Failed to validate Phase 2: {e}",
                exc_info=True
            )
            raise

    async def validate_complete_spec(
        self,
        spec: ValidatedSpec
    ) -> ValidationReport:
        """Validate complete specification with deterministic checks.

        Performs comprehensive validation of the complete BA analysis output,
        checking for endpoint enumeration completeness, confidence score
        consistency, and overall quality.

        Args:
            spec: Complete validated specification

        Returns:
            ValidationReport with overall status, confidence, gaps, and recommendations

        Raises:
            Exception: If BAML function call fails

        Example:
            >>> spec = ValidatedSpec(...)
            >>> report = await validator.validate_complete_spec(spec)
            >>> print(f"Overall status: {report.overall_status}")
            >>> print(f"Overall confidence: {report.overall_confidence}")
        """
        logger.info("Validating complete specification")

        # DETERMINISTIC CHECK: Endpoint enumeration completeness
        # This check MUST happen before LLM validation to ensure it's not missed
        executive_total = spec.executive_summary.total_endpoints_discovered
        endpoints_documented = len(spec.endpoints)

        enumeration_gap = None
        if endpoints_documented < executive_total:
            logger.warning(
                f"Incomplete enumeration detected: {endpoints_documented}/{executive_total} endpoints",
                extra={
                    "executive_total": executive_total,
                    "documented": endpoints_documented,
                    "missing": executive_total - endpoints_documented
                }
            )
            enumeration_gap = {
                "gap_type": "incomplete_enumeration",
                "severity": "CRITICAL",
                "description": f"Only {endpoints_documented}/{executive_total} endpoints documented",
                "action_required": "Second pass must enumerate ALL endpoints",
                "discovered": executive_total,
                "documented": endpoints_documented,
                "missing": executive_total - endpoints_documented
            }

        try:
            # Create prompt for complete spec validation
            prompt = validate_complete_spec_prompt(spec=spec)

            # Call LLM with structured output
            report = self.llm.invoke_structured(
                prompt=prompt,
                response_model=ValidationReport,
                system="You are an expert validation analyst specializing in comprehensive data source specification validation."
            )

            # INJECT deterministic gap if LLM missed it
            if enumeration_gap:
                # Check if LLM already identified this gap
                has_enum_gap = any(
                    "incomplete_enumeration" in str(gap).lower() or
                    "enumeration" in str(gap).lower()
                    for gap in (report.critical_gaps or [])
                )

                if not has_enum_gap:
                    logger.warning("LLM missed enumeration gap - injecting deterministically")
                    if not report.critical_gaps:
                        report.critical_gaps = []
                    report.critical_gaps.append(enumeration_gap)

            logger.info(f"Validation complete: overall_confidence={report.overall_confidence}")

            # Save validation report
            try:
                self.repository.save("ba_validation_report.json", report)
                logger.info("Validation report saved to ba_validation_report.json")
            except Exception as save_error:
                logger.warning(
                    f"Failed to save validation report: {save_error}",
                    exc_info=True
                )
                # Don't fail the validation if save fails

            return report

        except Exception as e:
            logger.error(
                f"Failed to validate complete spec: {e}",
                exc_info=True
            )
            raise

    def should_run_second_analysis(self, report: ValidationReport) -> bool:
        """Determine if Run 2 is needed based on confidence threshold.

        Uses the configured confidence threshold (default 0.8) to determine
        if a second analysis run should be performed.

        Args:
            report: Validation report from validate_complete_spec

        Returns:
            True if overall_confidence < threshold, False otherwise

        Example:
            >>> report = ValidationReport(overall_confidence=0.75, ...)
            >>> if validator.should_run_second_analysis(report):
            ...     print("Second run recommended")
        """
        needs_run2 = report.overall_confidence < self.confidence_threshold

        logger.info(
            f"Run 2 decision: {'REQUIRED' if needs_run2 else 'NOT REQUIRED'} "
            f"(confidence={report.overall_confidence:.2f}, threshold={self.confidence_threshold})",
            extra={
                "needs_run2": needs_run2,
                "confidence": report.overall_confidence,
                "threshold": self.confidence_threshold
            }
        )

        return needs_run2

    def get_run2_focus_areas(self, report: ValidationReport) -> list[str]:
        """Extract focus areas for Run 2 from validation report.

        Collects all identified gaps and recommendations from the validation
        report to guide the second analysis run.

        Args:
            report: Validation report from validate_complete_spec

        Returns:
            List of focus areas and recommendations for Run 2

        Example:
            >>> report = ValidationReport(...)
            >>> focus_areas = validator.get_run2_focus_areas(report)
            >>> for area in focus_areas:
            ...     print(f"- {area}")
        """
        focus_areas: list[str] = []

        # Add recommendations from report
        focus_areas.extend(report.recommendations_for_second_pass)

        # Add critical gaps as focus areas
        for gap in report.critical_gaps:
            focus_areas.append(
                f"{gap.gap_type}: {gap.description} - {gap.action_required}"
            )

        # Add phase-specific gaps
        for phase_name, phase_validation in report.phase_validations.items():
            if phase_validation.status != ValidationOverallStatus.PASS:
                for issue in phase_validation.issues:
                    # Defensive: ensure issue is a dict
                    if not isinstance(issue, dict):
                        logger.warning(f"Invalid issue format in {phase_name}: {issue}")
                        continue

                    issue_text = issue.get("issue", "")
                    recommendation = issue.get("recommendation", "")
                    if issue_text:
                        focus_areas.append(f"{phase_name}: {issue_text}")
                    if recommendation:
                        focus_areas.append(f"{phase_name} recommendation: {recommendation}")

        logger.info(
            f"Extracted {len(focus_areas)} focus areas for Run 2",
            extra={"focus_areas_count": len(focus_areas)}
        )

        return focus_areas

    def create_validation_summary(
        self,
        report: ValidationReport
    ) -> dict[str, Any]:
        """Create a human-readable summary of validation results.

        Args:
            report: Validation report

        Returns:
            Dictionary with summary statistics and key findings

        Example:
            >>> summary = validator.create_validation_summary(report)
            >>> print(summary["status"])
            >>> print(summary["critical_gaps_count"])
        """
        return {
            "status": report.overall_status.value,
            "confidence": report.overall_confidence,
            "needs_run2": self.should_run_second_analysis(report),
            "critical_gaps_count": len(report.critical_gaps),
            "recommendations_count": len(report.recommendations_for_second_pass),
            "phase_validations": {
                phase: {
                    "status": validation.status.value,
                    "issues_count": len(validation.issues)
                }
                for phase, validation in report.phase_validations.items()
            },
            "validation_timestamp": report.validation_timestamp,
            "summary": report.validation_summary
        }
