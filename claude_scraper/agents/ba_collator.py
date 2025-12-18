"""BA Collator Agent.

This module provides the BACollator class for merging Run 1 and Run 2 analysis
results with weighted confidence scoring.

The collator follows the weighted merge algorithm from ba-collator.md:
- Run 1: 30% weight (initial discovery)
- Run 2: 70% weight (validator-guided focused analysis)
- Run 2 wins for conflicts

Example:
    >>> from claude_scraper.agents.ba_collator import BACollator
    >>> from claude_scraper.storage.repository import AnalysisRepository
    >>>
    >>> collator = BACollator()
    >>> result = await collator.merge_complete_specs(run1_spec, run2_spec)
    >>> print(f"Final confidence: {result.validation_summary.final_confidence_score}")
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from baml_client import b
from baml_client.types import (
    CollationResult,
    Phase0Detection,
    ValidatedSpec,
)

from claude_scraper.storage.repository import AnalysisRepository

logger = logging.getLogger(__name__)


class BACollator:
    """Collator for merging Run 1 and Run 2 BA analysis results.

    This class merges two Business Analyst analysis runs into a final,
    comprehensive specification using weighted confidence scoring.

    Attributes:
        RUN1_WEIGHT: Weight for Run 1 confidence scores (0.3 = 30%)
        RUN2_WEIGHT: Weight for Run 2 confidence scores (0.7 = 70%)
        repository: File repository for saving/loading analysis files

    Example:
        >>> collator = BACollator()
        >>> merged_phase0 = await collator.merge_phase0(run1_p0, run2_p0, ["endpoints"])
        >>> merged_spec = await collator.merge_complete_specs(run1_spec, run2_spec)
    """

    # Weighted confidence scoring per plan (ba-collator.md)
    RUN1_WEIGHT = 0.3  # 30% weight for initial discovery
    RUN2_WEIGHT = 0.7  # 70% weight for validator-guided focused analysis
    CONFIDENCE_PRECISION = 3  # 0.001 precision (0.1% granularity)

    def __init__(
        self,
        repository: AnalysisRepository | None = None,
        base_dir: str | Path = "datasource_analysis"
    ) -> None:
        """Initialize BA Collator.

        Args:
            repository: Optional repository for file operations. If None, creates new one.
            base_dir: Base directory for analysis files (default: "datasource_analysis")

        Example:
            >>> collator = BACollator()
            >>> collator = BACollator(base_dir="custom_analysis_dir")
        """
        self.repository = repository or AnalysisRepository(base_dir)
        logger.info(
            "Initialized BACollator",
            extra={
                "run1_weight": self.RUN1_WEIGHT,
                "run2_weight": self.RUN2_WEIGHT,
                "base_dir": str(base_dir)
            }
        )

    async def merge_phase0(
        self,
        run1: Phase0Detection,
        run2: Phase0Detection,
        run2_focus_areas: list[str]
    ) -> Phase0Detection:
        """Merge two Phase 0 detection results with weighted scoring.

        Merges Run 1 and Run 2 Phase 0 detection results using 30/70 weighted
        confidence scoring. Run 2 is given higher weight as it's a focused
        re-analysis based on validator feedback.

        Args:
            run1: Phase 0 detection from first BA run
            run2: Phase 0 detection from second BA run (validator-guided)
            run2_focus_areas: List of areas Run 2 focused on (e.g., ["endpoints"])

        Returns:
            Merged Phase0Detection with weighted confidence score

        Example:
            >>> merged = await collator.merge_phase0(run1_p0, run2_p0, ["endpoints"])
            >>> print(f"Merged confidence: {merged.confidence}")
            Merged confidence: 0.905
        """
        logger.info(
            "Merging Phase 0 results (30% Run 1, 70% Run 2)",
            extra={
                "run1_type": run1.detected_type,
                "run1_confidence": run1.confidence,
                "run2_type": run2.detected_type,
                "run2_confidence": run2.confidence,
                "run2_focus_areas": run2_focus_areas
            }
        )

        # Calculate expected weighted confidence for logging
        expected_confidence = (
            self.RUN1_WEIGHT * run1.confidence +
            self.RUN2_WEIGHT * run2.confidence
        )
        logger.debug(
            f"Expected weighted confidence: {expected_confidence:.3f}",
            extra={"expected_confidence": expected_confidence}
        )

        # Call BAML function to merge
        try:
            result = await b.MergePhase0(
                run1=run1,
                run2=run2,
                run2_focus_areas=run2_focus_areas
            )

            logger.info(
                f"Merged Phase 0: type={result.detected_type}, "
                f"confidence={result.confidence:.3f}",
                extra={
                    "detected_type": result.detected_type,
                    "confidence": result.confidence,
                    "indicators_count": len(result.indicators),
                    "api_calls_count": len(result.discovered_api_calls),
                    "endpoints_count": len(result.endpoints)
                }
            )

            return result

        except Exception as e:
            logger.error(
                f"Failed to merge Phase 0 results: {e}",
                exc_info=True,
                extra={
                    "run1_type": run1.detected_type,
                    "run2_type": run2.detected_type
                }
            )
            raise

    async def merge_complete_specs(
        self,
        run1: ValidatedSpec,
        run2: ValidatedSpec,
        save_result: bool = True
    ) -> ValidatedSpec:
        """Merge complete Run 1 and Run 2 validated specifications.

        Merges two complete Business Analyst analysis runs into a final,
        definitive data source specification. Uses weighted confidence
        scoring (30% Run 1, 70% Run 2) and resolves conflicts by preferring
        Run 2 values.

        Args:
            run1: Validated specification from first BA run
            run2: Validated specification from second BA run (validator-guided)
            save_result: If True, save merged spec to final_validated_spec.json

        Returns:
            Final merged ValidatedSpec with collation metadata

        Example:
            >>> merged = await collator.merge_complete_specs(run1, run2)
            >>> print(f"Total endpoints: {merged.executive_summary.total_endpoints_discovered}")
            >>> print(f"Final confidence: {merged.validation_summary.final_confidence_score}")
        """
        logger.info(
            "Merging complete specifications",
            extra={
                "run1_timestamp": run1.timestamp,
                "run2_timestamp": run2.timestamp,
                "run1_confidence": run1.validation_summary.confidence_score,
                "run2_confidence": run2.validation_summary.confidence_score,
                "run1_endpoints": len(run1.endpoints),
                "run2_endpoints": len(run2.endpoints)
            }
        )

        # Calculate weighted final confidence for logging
        final_confidence = self.calculate_weighted_confidence(
            run1.validation_summary.confidence_score,
            run2.validation_summary.confidence_score
        )
        logger.info(
            f"Calculated weighted confidence: {final_confidence:.3f}",
            extra={"final_confidence": final_confidence}
        )

        # Call BAML function to merge
        try:
            result = await b.MergeCompleteSpecs(run1=run1, run2=run2)

            logger.info(
                "Collation complete",
                extra={
                    "total_endpoints": result.executive_summary.total_endpoints_discovered,
                    "final_confidence": result.validation_summary.final_confidence_score,
                    "collation_complete": result.validation_summary.collation_complete,
                    "runs_analyzed": result.validation_summary.runs_analyzed
                }
            )

            # Save merged result
            if save_result:
                self.repository.save("final_validated_spec.json", result)
                logger.info(
                    "Saved final merged specification to final_validated_spec.json",
                    extra={"file": "final_validated_spec.json"}
                )

            return result

        except Exception as e:
            logger.error(
                f"Failed to merge complete specs: {e}",
                exc_info=True,
                extra={
                    "run1_endpoints": len(run1.endpoints),
                    "run2_endpoints": len(run2.endpoints)
                }
            )
            raise

    def calculate_weighted_confidence(
        self,
        run1_confidence: float,
        run2_confidence: float
    ) -> float:
        """Calculate weighted confidence score with validation.

        Calculates the weighted average confidence score using the
        configured weights (30% Run 1, 70% Run 2).

        Args:
            run1_confidence: Confidence score from Run 1 (must be 0.0-1.0)
            run2_confidence: Confidence score from Run 2 (must be 0.0-1.0)

        Returns:
            Weighted confidence: (0.3 × run1) + (0.7 × run2), rounded to 3 decimals

        Raises:
            ValueError: If confidence scores are out of bounds

        Example:
            >>> collator.calculate_weighted_confidence(0.8, 0.95)
            0.905
        """
        # Validate inputs are in valid range
        if not (0.0 <= run1_confidence <= 1.0):
            raise ValueError(
                f"run1_confidence must be between 0.0 and 1.0, got {run1_confidence}"
            )
        if not (0.0 <= run2_confidence <= 1.0):
            raise ValueError(
                f"run2_confidence must be between 0.0 and 1.0, got {run2_confidence}"
            )

        weighted = (
            self.RUN1_WEIGHT * run1_confidence +
            self.RUN2_WEIGHT * run2_confidence
        )

        logger.debug(
            f"Weighted confidence: ({self.RUN1_WEIGHT} × {run1_confidence}) + "
            f"({self.RUN2_WEIGHT} × {run2_confidence}) = {weighted:.3f}",
            extra={
                "run1_confidence": run1_confidence,
                "run2_confidence": run2_confidence,
                "weighted_confidence": weighted
            }
        )

        # Round to configured precision for clean output
        return round(weighted, self.CONFIDENCE_PRECISION)

    def resolve_conflicts(
        self,
        run1_value: str,
        run2_value: str,
        field_name: str
    ) -> str:
        """Resolve conflicts between Run 1 and Run 2 values.

        When Run 1 and Run 2 disagree on a field value, this method
        resolves the conflict by preferring Run 2 (70% weight, validator-guided).

        Args:
            run1_value: Value from Run 1
            run2_value: Value from Run 2
            field_name: Name of field being resolved (for logging)

        Returns:
            Resolved value (Run 2 wins for conflicts)

        Example:
            >>> collator.resolve_conflicts("HTTP", "HTTPS", "protocol")
            'HTTPS'
        """
        if run1_value == run2_value:
            logger.debug(
                f"No conflict in {field_name}: both runs agree on '{run1_value}'",
                extra={"field": field_name, "value": run1_value}
            )
            return run1_value

        logger.debug(
            f"Conflict in {field_name}: Run 1 = '{run1_value}', "
            f"Run 2 = '{run2_value}'. Run 2 wins (70% weight).",
            extra={
                "field": field_name,
                "run1_value": run1_value,
                "run2_value": run2_value,
                "resolution": run2_value
            }
        )

        return run2_value  # Run 2 wins per weighted merge algorithm

    def create_collation_result(
        self,
        final_spec: ValidatedSpec,
        run1_spec: ValidatedSpec,
        run2_spec: ValidatedSpec
    ) -> CollationResult:
        """Create collation result summary.

        Creates a CollationResult object summarizing the merge operation
        for return to the orchestrator.

        Args:
            final_spec: Merged final specification
            run1_spec: Original Run 1 specification
            run2_spec: Original Run 2 specification

        Returns:
            CollationResult with merge statistics

        Example:
            >>> result = collator.create_collation_result(final, run1, run2)
            >>> print(f"Endpoints merged: {result.total_endpoints}")
        """
        # Count improvements and discrepancies
        improvements_count = len(run2_spec.endpoints) - len(run1_spec.endpoints)
        discrepancies_resolved = (
            final_spec.validation_summary.discrepancies_resolved
            if final_spec.validation_summary.discrepancies_resolved
            else 0
        )

        # Calculate consistency rate
        # Consistency = (endpoints tested in both runs) / (endpoints in run1)
        # This shows what percentage of run1 endpoints were re-validated in run2
        if len(run1_spec.endpoints) > 0:
            consistency_count = sum(
                1 for ep in final_spec.endpoints
                if ep.tested_in_run1 and ep.tested_in_run2
            )

            # Warn if consistency count exceeds Run 1 endpoints (data integrity issue)
            if consistency_count > len(run1_spec.endpoints):
                logger.warning(
                    f"Consistency count ({consistency_count}) exceeds Run 1 endpoint count "
                    f"({len(run1_spec.endpoints)}). Some endpoints may be incorrectly marked.",
                    extra={
                        "consistency_count": consistency_count,
                        "run1_endpoint_count": len(run1_spec.endpoints),
                        "run2_endpoint_count": len(run2_spec.endpoints)
                    }
                )

            # Cap consistency count at run1 endpoint count to avoid > 100%
            consistency_count = min(consistency_count, len(run1_spec.endpoints))
            consistency_rate = f"{(consistency_count / len(run1_spec.endpoints)) * 100:.0f}%"
        else:
            consistency_rate = "N/A"

        result = CollationResult(
            collation_complete=True,
            final_spec_path="datasource_analysis/final_validated_spec.json",
            final_confidence_score=final_spec.validation_summary.final_confidence_score or 0.0,
            total_endpoints=final_spec.executive_summary.total_endpoints_discovered,
            endpoints_run1=len(run1_spec.endpoints),
            endpoints_run2=len(run2_spec.endpoints),
            improvements_count=max(0, improvements_count),
            discrepancies_resolved=discrepancies_resolved,
            consistency_rate=consistency_rate,
            ready_for_scraper_generation=True
        )

        logger.info(
            "Created collation result",
            extra={
                "total_endpoints": result.total_endpoints,
                "final_confidence": result.final_confidence_score,
                "improvements": result.improvements_count,
                "consistency": result.consistency_rate
            }
        )

        return result
