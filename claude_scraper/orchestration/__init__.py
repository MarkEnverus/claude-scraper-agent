"""Orchestration layer for LangGraph pipelines.

This module provides LangGraph-based orchestration for the BA analysis pipeline.

Public API:
- AnalysisState: TypedDict for pipeline state
- create_pipeline: Factory function for creating the pipeline
- pipeline: Default pipeline instance (with checkpointing)
- run1_node, decision_node, run2_node, collation_node, qa_node: Node functions

Example:
    >>> from claude_scraper.orchestration import pipeline, AnalysisState
    >>> state: AnalysisState = {"url": "https://api.example.com"}
    >>> result = await pipeline.ainvoke(state)
    >>> print(f"Analysis complete: {result['final_spec'].source_type}")
"""

from claude_scraper.orchestration.nodes import (
    collation_node,
    decision_node,
    qa_node,
    run1_node,
    run2_node,
)
from claude_scraper.orchestration.pipeline import (
    create_pipeline,
    create_pipeline_without_checkpointing,
    pipeline,
    should_run_second_pass,
)
from claude_scraper.orchestration.state import AnalysisState, QAResults

__all__ = [
    "AnalysisState",
    "QAResults",
    "create_pipeline",
    "create_pipeline_without_checkpointing",
    "pipeline",
    "should_run_second_pass",
    "run1_node",
    "decision_node",
    "run2_node",
    "collation_node",
    "qa_node",
]
