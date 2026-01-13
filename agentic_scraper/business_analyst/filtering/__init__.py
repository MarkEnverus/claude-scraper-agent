"""Endpoint filtering package for BA Analyst.

This package implements hybrid 3-stage endpoint filtering:
- Stage 1: Deterministic pre-filter (pattern matching)
- Stage 2: LLM classification + ranking
- Stage 3: Deterministic caps + audit trail

The filtering system produces:
- validated_datasource_spec.json (filtered endpoints for scraper generator)
- endpoint_inventory.json (full audit trail with categories/reasons)
- executive_data_summary.md (data-focused executive summary)
"""

from agentic_scraper.business_analyst.filtering.endpoint_filter import (
    run_hybrid_filter,
    FilteringResult,
    DiscardedEndpoint,
    CategorizedEndpoint,
)

__all__ = [
    "run_hybrid_filter",
    "FilteringResult",
    "DiscardedEndpoint",
    "CategorizedEndpoint",
]
