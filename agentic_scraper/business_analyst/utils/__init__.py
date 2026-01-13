"""Utilities for BA Analyst.

This package contains utility functions for:
- Vision-based analysis (multimodal LLM calls, screenshots)
- Markdown chunking (token-aware content splitting)
- Link scoring (deterministic heuristic scoring)
- Cost controls (token limits, prioritization)
"""

from agentic_scraper.business_analyst.utils.vision_utils import (
    invoke_with_vision,
    save_screenshot,
    is_spa_likely,
    encode_image_to_base64,
    validate_screenshot_quality,
)

from agentic_scraper.business_analyst.utils.chunking import (
    estimate_tokens,
    chunk_markdown,
    select_top_chunks,
    merge_chunks,
    extract_api_keywords,
    chunk_by_headings,
    MarkdownChunk,
)

from agentic_scraper.business_analyst.utils.link_scoring import (
    score_link_deterministic,
    filter_links_by_domain,
    filter_visited_links,
    score_and_sort_links,
    HIGH_VALUE_KEYWORDS,
    LOW_VALUE_KEYWORDS,
)

__all__ = [
    # Vision utilities
    'invoke_with_vision',
    'save_screenshot',
    'is_spa_likely',
    'encode_image_to_base64',
    'validate_screenshot_quality',
    # Chunking utilities
    'estimate_tokens',
    'chunk_markdown',
    'select_top_chunks',
    'merge_chunks',
    'extract_api_keywords',
    'chunk_by_headings',
    'MarkdownChunk',
    # Link scoring utilities
    'score_link_deterministic',
    'filter_links_by_domain',
    'filter_visited_links',
    'score_and_sort_links',
    'HIGH_VALUE_KEYWORDS',
    'LOW_VALUE_KEYWORDS',
]
