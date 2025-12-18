"""LangGraph pipeline definition for BA analysis orchestration.

This module defines the StateGraph pipeline that orchestrates the 5-agent
BA analysis workflow with conditional routing and checkpointing.

Pipeline structure:
    START → run1 → decision → run2 (if confidence < 0.8) → collation → qa → END
                          ↘ (if confidence ≥ 0.8) → collation → qa → END

The pipeline uses LangGraph's StateGraph with:
- AnalysisState TypedDict for type-safe state management
- 5 nodes: run1, decision, run2, collation, qa
- Conditional routing based on confidence threshold (0.8)
- MemorySaver checkpointing for resume capability

Example:
    >>> from claude_scraper.orchestration.pipeline import create_pipeline
    >>> pipeline = create_pipeline()
    >>> result = await pipeline.ainvoke({"url": "https://api.example.com"})
    >>> print(f"Final confidence: {result['final_spec'].validation_summary.confidence_score}")
"""

import logging
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from claude_scraper.orchestration.nodes import (
    collation_node,
    decision_node,
    qa_node,
    run1_node,
    run2_node,
)
from claude_scraper.orchestration.state import AnalysisState

logger = logging.getLogger(__name__)


def should_run_second_pass(state: AnalysisState) -> Literal["run2", "collation"]:
    """Conditional routing function for Run 2 decision.

    Determines whether to execute Run 2 based on the confidence score
    from Run 1 validation:
    - If confidence < 0.8: Route to "run2" for focused re-analysis
    - If confidence >= 0.8: Route to "collation" (skip Run 2)

    This function is used as a conditional edge in the StateGraph to
    implement the decision logic after Run 1 completes.

    Args:
        state: Current pipeline state (must contain "run2_required")

    Returns:
        "run2" if second pass is required, "collation" otherwise

    Raises:
        ValueError: If run2_required is missing from state

    Example:
        >>> state = {"run2_required": True, "confidence_score": 0.75}
        >>> should_run_second_pass(state)
        'run2'
        >>> state = {"run2_required": False, "confidence_score": 0.85}
        >>> should_run_second_pass(state)
        'collation'
    """
    run2_required = state.get("run2_required")

    if run2_required is None:
        raise ValueError(
            "run2_required must be present in state for routing decision"
        )

    if run2_required:
        logger.info("Routing to Run 2 (confidence below threshold)")
        return "run2"
    else:
        logger.info("Routing to collation (confidence meets threshold)")
        return "collation"


def create_pipeline(with_checkpointing: bool = True) -> CompiledStateGraph:
    """Create and compile the BA analysis pipeline.

    Creates a LangGraph StateGraph with 5 nodes and conditional routing:
    1. run1_node: Execute Run 1 (4-phase analysis + validation)
    2. decision_node: No-op node for routing decision
    3. run2_node: Execute Run 2 (conditional - only if confidence < 0.8)
    4. collation_node: Merge Run 1 + Run 2 into final spec
    5. qa_node: Test endpoints with HTTP requests

    Pipeline edges:
    - START → run1 (unconditional)
    - run1 → decision (unconditional)
    - decision → run2 OR collation (conditional based on confidence)
    - run2 → collation (unconditional)
    - collation → qa (unconditional)
    - qa → END (unconditional)

    Args:
        with_checkpointing: Enable MemorySaver checkpointing for resume (default: True)

    Returns:
        Compiled StateGraph ready for execution

    Example:
        >>> pipeline = create_pipeline()
        >>> result = await pipeline.ainvoke(
        ...     {"url": "https://api.example.com"},
        ...     {"configurable": {"thread_id": "analysis-1"}}
        ... )

        >>> # Resume from checkpoint
        >>> result = await pipeline.ainvoke(
        ...     None,  # Resume from last state
        ...     {"configurable": {"thread_id": "analysis-1"}}
        ... )
    """
    logger.info("Creating BA analysis pipeline")

    # Create StateGraph with AnalysisState schema
    graph = StateGraph(AnalysisState)

    # Add nodes
    logger.debug("Adding nodes to pipeline")
    graph.add_node("run1", run1_node)
    graph.add_node("decision", decision_node)
    graph.add_node("run2", run2_node)
    graph.add_node("collation", collation_node)
    graph.add_node("qa", qa_node)

    # Add edges
    logger.debug("Adding edges to pipeline")

    # START → run1 (always execute Run 1)
    graph.add_edge(START, "run1")

    # run1 → decision (always route to decision node)
    graph.add_edge("run1", "decision")

    # decision → run2 OR collation (conditional based on confidence)
    graph.add_conditional_edges(
        "decision",
        should_run_second_pass,
        {
            "run2": "run2",  # If confidence < 0.8
            "collation": "collation",  # If confidence >= 0.8
        },
    )

    # run2 → collation (if Run 2 was executed)
    graph.add_edge("run2", "collation")

    # collation → qa (always run QA after collation)
    graph.add_edge("collation", "qa")

    # qa → END (pipeline complete)
    graph.add_edge("qa", END)

    # Compile with optional checkpointing
    if with_checkpointing:
        logger.info("Compiling pipeline with MemorySaver checkpointing")
        checkpointer = MemorySaver()
        compiled = graph.compile(checkpointer=checkpointer)
    else:
        logger.info("Compiling pipeline without checkpointing")
        compiled = graph.compile()

    logger.info("Pipeline created successfully")
    return compiled


def create_pipeline_without_checkpointing() -> CompiledStateGraph:
    """Create pipeline without checkpointing for testing.

    This is a convenience function for creating a pipeline without
    checkpointing, which is useful for unit tests and simple executions
    that don't need resume capability.

    Returns:
        Compiled StateGraph without checkpointing

    Example:
        >>> pipeline = create_pipeline_without_checkpointing()
        >>> result = await pipeline.ainvoke({"url": "https://api.example.com"})
    """
    return create_pipeline(with_checkpointing=False)


# Convenience: Create default pipeline instance
# Users can import and use directly: from pipeline import pipeline
logger.info("Creating default pipeline instance")
pipeline = create_pipeline(with_checkpointing=True)
