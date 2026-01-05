"""LangGraph state definition for BA analysis pipeline.

This module defines the AnalysisState TypedDict that tracks the state
through the 6-agent pipeline orchestration:
- Run 1: BA Analyzer (4 phases) + BA Validator
- Decision: Determine if Run 2 is needed (confidence < 0.8)
- Run 2: BA Analyzer (4 phases) + BA Validator (conditional)
- Collation: BA Collator merges Run 1 + Run 2 (if exists)
- Phase 4: Executive Summary Generator
- QA: Endpoint QA testing

The state uses BAML-generated types for type safety and tracks all
intermediate results, validation reports, and control flow flags.

Example:
    >>> from claude_scraper.orchestration.state import AnalysisState
    >>> state: AnalysisState = {"url": "https://api.example.com"}
    >>> # State gets populated through pipeline execution
"""

from typing import TypedDict

from claude_scraper.types import (
    Phase0Detection,
    Phase1Documentation,
    Phase2Tests,
    ValidatedSpec,
    ValidationReport,
)


class QAResults(TypedDict):
    """Results from EndpointQATester.test_all_endpoints().

    Attributes:
        total_tested: Total number of endpoints tested
        keep: Number of endpoints to keep (200/401/403 responses)
        remove: Number of endpoints to remove (404 responses)
        flag: Number of endpoints flagged for manual review (429/500/503)
        results: List of individual test results for each endpoint
    """
    total_tested: int
    keep: int
    remove: int
    flag: int
    results: list[dict]


class AnalysisState(TypedDict, total=False):
    """State for the BA analysis pipeline.

    This TypedDict tracks all state through the 6-node LangGraph pipeline.
    Fields are optional (total=False) since they get populated progressively
    as the pipeline executes.

    Attributes:
        url: Input URL to analyze (required)
        output_dir: Output directory for analysis files (optional, defaults to "datasource_analysis")
        provider: LLM provider to use (anthropic or bedrock)

        # Run 1 outputs
        phase0_run1: Phase 0 detection results from Run 1
        phase1_run1: Phase 1 documentation results from Run 1
        phase2_run1: Phase 2 testing results from Run 1
        phase3_run1: Phase 3 validated spec from Run 1
        validation_run1: Validation report for Run 1

        # Run 2 outputs (conditional - only if confidence < 0.8)
        phase0_run2: Phase 0 detection results from Run 2 (None if skipped)
        phase1_run2: Phase 1 documentation results from Run 2 (None if skipped)
        phase2_run2: Phase 2 testing results from Run 2 (None if skipped)
        phase3_run2: Phase 3 validated spec from Run 2 (None if skipped)
        validation_run2: Validation report for Run 2 (None if skipped)

        # Final outputs
        final_spec: Final validated specification after collation
        executive_summary_markdown: Markdown executive summary (Phase 4 output)
        executive_summary_path: Path to saved executive_summary.md file
        qa_results: Endpoint QA testing results

        # Control flow
        run2_required: Boolean flag indicating if Run 2 should execute
        confidence_score: Confidence score from Run 1 validation (0.0-1.0)

    Example:
        >>> state: AnalysisState = {
        ...     "url": "https://api.example.com",
        ...     "phase0_run1": phase0_result,
        ...     "validation_run1": validation_result,
        ...     "confidence_score": 0.75,
        ...     "run2_required": True
        ... }
    """

    # Input
    url: str
    output_dir: str
    provider: str

    # Run 1 outputs
    phase0_run1: Phase0Detection
    phase1_run1: Phase1Documentation
    phase2_run1: Phase2Tests
    phase3_run1: ValidatedSpec
    validation_run1: ValidationReport

    # Run 2 outputs (conditional)
    phase0_run2: Phase0Detection | None
    phase1_run2: Phase1Documentation | None
    phase2_run2: Phase2Tests | None
    phase3_run2: ValidatedSpec | None
    validation_run2: ValidationReport | None

    # Final outputs
    final_spec: ValidatedSpec
    executive_summary_markdown: str | None
    executive_summary_path: str | None
    qa_results: QAResults

    # Control flow
    run2_required: bool
    confidence_score: float
