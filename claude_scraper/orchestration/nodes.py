"""LangGraph node implementations for BA analysis pipeline.

This module implements the 5 nodes that make up the BA analysis pipeline:
1. run1_node: Execute Run 1 (4-phase BA analysis + validation)
2. decision_node: Determine if Run 2 is needed (confidence check)
3. run2_node: Execute Run 2 (focused re-analysis based on validation gaps)
4. collation_node: Merge Run 1 + Run 2 into final specification
5. qa_node: Run Endpoint QA testing on final spec

Each node is an async function that takes AnalysisState and returns
a dict of state updates. Nodes are designed to be composed into a
LangGraph StateGraph pipeline.

Example:
    >>> from claude_scraper.orchestration.nodes import run1_node
    >>> from claude_scraper.orchestration.state import AnalysisState
    >>>
    >>> state: AnalysisState = {"url": "https://api.example.com"}
    >>> updates = await run1_node(state)
    >>> print(updates["confidence_score"])
"""

import logging
import time
from functools import wraps
from typing import Any

from baml_client.baml_client.types import (
    Phase0Detection,
    Phase1Documentation,
    Phase2Tests,
    ValidatedSpec,
    ValidationReport,
)
from claude_scraper.agents.ba_analyzer import BAAnalyzer
from claude_scraper.agents.ba_collator import BACollator
from claude_scraper.agents.ba_validator import BAValidator
from claude_scraper.agents.endpoint_qa import EndpointQATester
from claude_scraper.orchestration.state import AnalysisState
from claude_scraper.storage.repository import AnalysisRepository
from claude_scraper.tools.botasaurus_tool import BotasaurusTool
from claude_scraper.types.errors import (
    CollationError,
    QATestingError,
    Run1AnalysisError,
    Run2AnalysisError,
)

logger = logging.getLogger(__name__)


def profile_node(node_name: str):
    """Decorator to profile node execution time and log performance metrics.

    Wraps an async node function to measure execution time and log:
    - Start time
    - End time
    - Total elapsed time
    - Success/failure status

    Args:
        node_name: Human-readable name for the node (e.g., "Run 1 Analysis")

    Returns:
        Decorator function that wraps the node

    Example:
        >>> @profile_node("Run 1 Analysis")
        ... async def run1_node(state: AnalysisState) -> dict:
        ...     # node implementation
        ...     pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            logger.info(f"[PERF] {node_name} started")

            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time

                logger.info(
                    f"[PERF] {node_name} completed successfully in {elapsed:.2f}s",
                    extra={
                        "node": node_name,
                        "elapsed_seconds": elapsed,
                        "status": "success",
                    }
                )

                return result

            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(
                    f"[PERF] {node_name} failed after {elapsed:.2f}s: {e}",
                    extra={
                        "node": node_name,
                        "elapsed_seconds": elapsed,
                        "status": "failed",
                        "error": str(e),
                    },
                    exc_info=True,
                )
                raise

        return wrapper
    return decorator


def profile_phase(phase_name: str):
    """Decorator to profile individual phase execution within a node.

    Similar to profile_node but designed for fine-grained profiling of
    individual phases (e.g., Phase 0, Phase 1, etc.) within a node.

    Args:
        phase_name: Human-readable name for the phase (e.g., "Phase 0 Detection")

    Returns:
        Decorator function that wraps the phase function

    Example:
        >>> @profile_phase("Phase 0 Detection")
        ... async def analyze_phase0(url: str) -> Phase0Detection:
        ...     # phase implementation
        ...     pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            logger.debug(f"[PERF] {phase_name} started")

            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time

                logger.debug(
                    f"[PERF] {phase_name} completed in {elapsed:.2f}s",
                    extra={
                        "phase": phase_name,
                        "elapsed_seconds": elapsed,
                    }
                )

                return result

            except Exception as e:
                elapsed = time.time() - start_time
                logger.debug(
                    f"[PERF] {phase_name} failed after {elapsed:.2f}s",
                    extra={
                        "phase": phase_name,
                        "elapsed_seconds": elapsed,
                        "error": str(e),
                    }
                )
                raise

        return wrapper
    return decorator


def _convert_endpoint_details_to_spec(endpoint: Any) -> Any:
    """Convert EndpointDetails to EndpointSpec for QA testing.

    Args:
        endpoint: EndpointDetails object from ValidatedSpec

    Returns:
        EndpointSpec object suitable for QA testing

    Example:
        >>> endpoint_details = validated_spec.endpoints[0]
        >>> endpoint_spec = _convert_endpoint_details_to_spec(endpoint_details)
    """
    from baml_client.baml_client.types import EndpointSpec

    # Determine if authentication is mentioned based on authentication dict
    auth_mentioned = bool(endpoint.authentication)

    return EndpointSpec(
        endpoint_id=endpoint.endpoint_id,
        path=endpoint.path,
        method=endpoint.method,
        description=endpoint.name,
        parameters=[],  # Parameters from EndpointDetails if needed
        response_format=endpoint.response_format,
        authentication_mentioned=auth_mentioned,
    )


@profile_node("Run 1 Analysis")
async def run1_node(state: AnalysisState) -> dict[str, Any]:
    """Execute Run 1: 4-phase BA analysis + validation.

    Performs the first complete analysis run:
    - Phase 0: Detect data source type
    - Phase 1: Extract documentation/metadata
    - Phase 2: Live testing (placeholder - requires Bash integration)
    - Phase 3: Generate validated specification
    - Validation: Validate complete spec and calculate confidence

    Args:
        state: Current pipeline state (must contain "url")

    Returns:
        State updates with Run 1 results:
        - phase0_run1: Phase 0 detection results
        - phase1_run1: Phase 1 documentation results
        - phase2_run1: Phase 2 testing results
        - phase3_run1: Phase 3 validated spec
        - validation_run1: Validation report
        - confidence_score: Overall confidence from validation
        - run2_required: Boolean flag indicating if Run 2 is needed

    Raises:
        ValueError: If URL is missing from state
        Exception: If any phase fails

    Example:
        >>> state = {"url": "https://api.example.com"}
        >>> updates = await run1_node(state)
        >>> print(f"Confidence: {updates['confidence_score']}")
    """
    url = state.get("url")
    if not url:
        raise ValueError("URL is required in state for run1_node")

    logger.info(f"Starting Run 1 analysis for {url}")

    try:
        # Initialize tools and agents
        botasaurus = BotasaurusTool()
        repository = AnalysisRepository(state.get("output_dir", "datasource_analysis"))

        analyzer = BAAnalyzer(
            botasaurus=botasaurus,
            repository=repository,
        )
        validator = BAValidator(repository=repository)

        # Phase 0: Detection
        logger.info("Run 1: Starting Phase 0 - Data source detection")
        phase0 = await analyzer.analyze_phase0(url)
        logger.info(
            f"Run 1 Phase 0 complete: {phase0.detected_type} "
            f"(confidence: {phase0.confidence:.2f})"
        )

        # Phase 1: Documentation
        logger.info("Run 1: Starting Phase 1 - Documentation extraction")
        phase1 = await analyzer.analyze_phase1(url, phase0)
        logger.info(
            f"Run 1 Phase 1 complete: {len(phase1.endpoints)} endpoints, "
            f"quality: {phase1.doc_quality}"
        )

        # Phase 2: Testing
        logger.info("Run 1: Starting Phase 2 - Live testing")
        phase2 = await analyzer.analyze_phase2(url, phase0, phase1)
        logger.info(
            f"Run 1 Phase 2 complete: {len(phase2.files_saved)} files saved"
        )

        # Phase 3: Validation
        logger.info("Run 1: Starting Phase 3 - Validated specification")
        phase3 = await analyzer.analyze_phase3(url, phase0, phase1, phase2)
        logger.info(
            f"Run 1 Phase 3 complete: {len(phase3.endpoints)} endpoints validated, "
            f"confidence: {phase3.validation_summary.confidence_score:.2f}"
        )

        # Validation
        logger.info("Run 1: Starting validation")
        validation = await validator.validate_complete_spec(phase3)
        confidence = validation.overall_confidence
        run2_required = validator.should_run_second_analysis(validation)

        logger.info(
            f"Run 1 complete: confidence={confidence:.2f}, "
            f"run2_required={run2_required}, "
            f"status={validation.overall_status}"
        )

        return {
            "phase0_run1": phase0,
            "phase1_run1": phase1,
            "phase2_run1": phase2,
            "phase3_run1": phase3,
            "validation_run1": validation,
            "confidence_score": confidence,
            "run2_required": run2_required,
        }

    except Exception as e:
        logger.error(
            "Run 1 analysis failed",
            extra={"url": url, "error": str(e)},
            exc_info=True,
        )
        raise Run1AnalysisError(
            f"Run 1 analysis failed for {url}: {e}",
            url=url
        ) from e


@profile_node("Decision Node")
async def decision_node(state: AnalysisState) -> dict[str, Any]:
    """Decision node: Check if Run 2 is needed.

    This is a lightweight decision node that examines the validation
    results from Run 1 to determine the next step. No agent calls are made.

    Decision logic:
    - If confidence >= 0.8: Skip Run 2, proceed to collation
    - If confidence < 0.8: Execute Run 2 with focused re-analysis

    Args:
        state: Current pipeline state (must contain "confidence_score" and "run2_required")

    Returns:
        Empty dict (no state updates needed - routing is handled by conditional edges)

    Raises:
        ValueError: If required state keys are missing

    Example:
        >>> state = {
        ...     "confidence_score": 0.75,
        ...     "run2_required": True,
        ...     "validation_run1": validation
        ... }
        >>> updates = await decision_node(state)
        >>> # Routing happens via should_run_second_pass() function
    """
    confidence = state.get("confidence_score")
    run2_required = state.get("run2_required")

    if confidence is None or run2_required is None:
        raise ValueError(
            "confidence_score and run2_required must be present in state for decision_node"
        )

    logger.info(
        f"Decision node: confidence={confidence:.2f}, run2_required={run2_required}"
    )

    if run2_required:
        validation = state.get("validation_run1")
        if validation:
            # Use temporary validator instance to extract focus areas
            repository = AnalysisRepository(state.get("output_dir", "datasource_analysis"))
            validator_temp = BAValidator(repository=repository)
            focus_areas = validator_temp.get_run2_focus_areas(validation)
            logger.info(
                f"Run 2 will execute with {len(focus_areas)} focus areas",
                extra={"focus_areas": focus_areas[:3]},  # Log first 3
            )
        else:
            logger.warning("validation_run1 missing - Run 2 will execute without focus areas")
    else:
        logger.info("Confidence threshold met - skipping Run 2")

    # No state updates needed - routing is handled by conditional edges
    return {}


@profile_node("Run 2 Analysis")
async def run2_node(state: AnalysisState) -> dict[str, Any]:
    """Execute Run 2: Focused re-analysis based on validation gaps.

    Performs a second analysis run focused on areas identified as
    problematic or incomplete by the validator. Uses validation_run1
    recommendations to guide the re-analysis.

    Args:
        state: Current pipeline state (must contain "url" and "validation_run1")

    Returns:
        State updates with Run 2 results:
        - phase0_run2: Phase 0 detection results
        - phase1_run2: Phase 1 documentation results
        - phase2_run2: Phase 2 testing results
        - phase3_run2: Phase 3 validated spec
        - validation_run2: Validation report

    Raises:
        ValueError: If required state keys are missing
        Exception: If any phase fails

    Example:
        >>> state = {
        ...     "url": "https://api.example.com",
        ...     "validation_run1": validation
        ... }
        >>> updates = await run2_node(state)
        >>> print(f"Run 2 confidence: {updates['validation_run2'].overall_confidence}")
    """
    url = state.get("url")
    validation_run1 = state.get("validation_run1")

    if not url:
        raise ValueError("URL is required in state for run2_node")
    if not validation_run1:
        raise ValueError("validation_run1 is required in state for run2_node")

    logger.info(f"Starting Run 2 analysis for {url}")

    # Extract focus areas from Run 1 validation
    repository = AnalysisRepository(state.get("output_dir", "datasource_analysis"))
    validator = BAValidator(repository=repository)
    focus_areas = validator.get_run2_focus_areas(validation_run1)
    logger.info(
        f"Run 2 will focus on {len(focus_areas)} areas",
        extra={"focus_areas": focus_areas[:5]},  # Log first 5
    )

    try:
        # Initialize tools and agents
        botasaurus = BotasaurusTool()
        repository = AnalysisRepository(state.get("output_dir", "datasource_analysis"))

        analyzer = BAAnalyzer(
            botasaurus=botasaurus,
            repository=repository,
        )

        # Phase 0: Detection
        logger.info("Run 2: Starting Phase 0 - Data source detection")
        phase0 = await analyzer.analyze_phase0(url)
        logger.info(
            f"Run 2 Phase 0 complete: {phase0.detected_type} "
            f"(confidence: {phase0.confidence:.2f})"
        )

        # Phase 1: Documentation
        logger.info("Run 2: Starting Phase 1 - Documentation extraction")
        phase1 = await analyzer.analyze_phase1(url, phase0)
        logger.info(
            f"Run 2 Phase 1 complete: {len(phase1.endpoints)} endpoints, "
            f"quality: {phase1.doc_quality}"
        )

        # Phase 2: Testing
        logger.info("Run 2: Starting Phase 2 - Live testing")
        phase2 = await analyzer.analyze_phase2(url, phase0, phase1)
        logger.info(
            f"Run 2 Phase 2 complete: {len(phase2.files_saved)} files saved"
        )

        # Phase 3: Validation
        logger.info("Run 2: Starting Phase 3 - Validated specification")
        phase3 = await analyzer.analyze_phase3(url, phase0, phase1, phase2)
        logger.info(
            f"Run 2 Phase 3 complete: {len(phase3.endpoints)} endpoints validated, "
            f"confidence: {phase3.validation_summary.confidence_score:.2f}"
        )

        # Validation
        logger.info("Run 2: Starting validation")
        validation = await validator.validate_complete_spec(phase3)
        confidence = validation.overall_confidence

        logger.info(
            f"Run 2 complete: confidence={confidence:.2f}, "
            f"status={validation.overall_status}"
        )

        return {
            "phase0_run2": phase0,
            "phase1_run2": phase1,
            "phase2_run2": phase2,
            "phase3_run2": phase3,
            "validation_run2": validation,
        }

    except Exception as e:
        logger.error(
            "Run 2 analysis failed",
            extra={"url": url, "error": str(e)},
            exc_info=True,
        )
        raise Run2AnalysisError(
            f"Run 2 analysis failed for {url}: {e}",
            url=url
        ) from e


@profile_node("Collation")
async def collation_node(state: AnalysisState) -> dict[str, Any]:
    """Collate Run 1 + Run 2 (if exists) into final specification.

    Merges analysis results from Run 1 and Run 2 (if Run 2 was executed)
    using the BACollator with weighted confidence scoring:
    - Run 1: 30% weight
    - Run 2: 70% weight (validator-guided)

    If Run 2 was skipped, creates a final spec from Run 1 only.

    Args:
        state: Current pipeline state (must contain "phase3_run1")

    Returns:
        State updates:
        - final_spec: Merged ValidatedSpec ready for QA testing

    Raises:
        ValueError: If phase3_run1 is missing
        Exception: If collation fails

    Example:
        >>> state = {
        ...     "phase3_run1": spec1,
        ...     "phase3_run2": spec2,
        ...     "run2_required": True
        ... }
        >>> updates = await collation_node(state)
        >>> print(f"Final endpoints: {len(updates['final_spec'].endpoints)}")
    """
    phase3_run1 = state.get("phase3_run1")
    if not phase3_run1:
        raise ValueError("phase3_run1 is required in state for collation_node")

    phase3_run2 = state.get("phase3_run2")
    run2_required = state.get("run2_required", False)

    logger.info("Starting collation")

    try:
        repository = AnalysisRepository(state.get("output_dir", "datasource_analysis"))
        collator = BACollator(repository=repository)

        if run2_required and phase3_run2:
            # Merge Run 1 + Run 2
            logger.info(
                "Merging Run 1 + Run 2 specifications",
                extra={
                    "run1_endpoints": len(phase3_run1.endpoints),
                    "run2_endpoints": len(phase3_run2.endpoints),
                },
            )
            final_spec = await collator.merge_complete_specs(
                run1=phase3_run1,
                run2=phase3_run2,
                save_result=True,
            )
            logger.info(
                "Collation complete (Run 1 + Run 2)",
                extra={
                    "final_endpoints": len(final_spec.endpoints),
                    "final_confidence": final_spec.validation_summary.final_confidence_score,
                },
            )
        else:
            # Use Run 1 only
            logger.info(
                "Using Run 1 specification only (Run 2 skipped or not executed)",
                extra={"run1_endpoints": len(phase3_run1.endpoints)},
            )
            # When Run 2 is skipped, the final spec is just Run 1
            final_spec = phase3_run1

        return {"final_spec": final_spec}

    except Exception as e:
        logger.error(
            "Collation failed",
            extra={"error": str(e)},
            exc_info=True,
        )
        raise CollationError(f"Collation failed: {e}") from e


@profile_node("QA Testing")
async def qa_node(state: AnalysisState) -> dict[str, Any]:
    """Run Endpoint QA testing on final specification.

    Tests each endpoint in the final specification using the EndpointQATester
    to verify accessibility and correctness. Uses HTTP requests with a
    deterministic decision matrix (no LLM calls).

    Decision matrix:
    - 200/401/403: keep (endpoint exists)
    - 404: remove (endpoint invalid)
    - 429/500/503: flag (cannot determine)

    Args:
        state: Current pipeline state (must contain "final_spec")

    Returns:
        State updates:
        - qa_results: QA testing results with summary statistics

    Raises:
        ValueError: If final_spec is missing
        Exception: If QA testing fails

    Example:
        >>> state = {"final_spec": validated_spec}
        >>> updates = await qa_node(state)
        >>> print(f"QA: {updates['qa_results']['keep']} kept, "
        ...       f"{updates['qa_results']['remove']} removed")
    """
    final_spec = state.get("final_spec")
    if not final_spec:
        raise ValueError("final_spec is required in state for qa_node")

    logger.info(
        f"Starting Endpoint QA testing on {len(final_spec.endpoints)} endpoints"
    )

    try:
        repository = AnalysisRepository(state.get("output_dir", "datasource_analysis"))
        tester = EndpointQATester(repository=repository)

        # Convert EndpointDetails to EndpointSpec for testing
        endpoint_specs = [
            _convert_endpoint_details_to_spec(ep)
            for ep in final_spec.endpoints
        ]

        # Test all endpoints
        qa_results = tester.test_all_endpoints(endpoint_specs)

        logger.info(
            f"QA testing complete: {qa_results['keep']} kept, "
            f"{qa_results['remove']} removed, {qa_results['flag']} flagged",
            extra={
                "total_tested": qa_results["total_tested"],
                "keep": qa_results["keep"],
                "remove": qa_results["remove"],
                "flag": qa_results["flag"],
            },
        )

        return {"qa_results": qa_results}

    except Exception as e:
        logger.error(
            "QA testing failed",
            extra={"error": str(e)},
            exc_info=True,
        )
        raise QATestingError(f"QA testing failed: {e}") from e
