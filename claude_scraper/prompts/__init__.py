"""Prompts package for Claude Scraper Agent.

This package contains all LLM prompts migrated from BAML to Python.
Each module contains prompts for a specific functional area.
"""

from claude_scraper.prompts.ba_analyzer import (
    phase0_prompt,
    analyze_endpoint_prompt,
    phase1_prompt,
    phase2_prompt,
    phase3_prompt,
)
from claude_scraper.prompts.ba_validator import (
    validate_phase0_prompt,
    validate_phase1_prompt,
    validate_phase2_prompt,
    validate_complete_spec_prompt,
)
from claude_scraper.prompts.ba_collator import (
    merge_phase0_prompt,
    merge_complete_specs_prompt,
)
from claude_scraper.prompts.ba_executive_summary import (
    generate_executive_summary_prompt,
)
from claude_scraper.prompts.scraper_generator import (
    generate_collect_content_prompt,
    generate_validate_content_prompt,
    generate_complex_auth_prompt,
)

__all__ = [
    # BA Analyzer prompts
    "phase0_prompt",
    "analyze_endpoint_prompt",
    "phase1_prompt",
    "phase2_prompt",
    "phase3_prompt",
    # BA Validator prompts
    "validate_phase0_prompt",
    "validate_phase1_prompt",
    "validate_phase2_prompt",
    "validate_complete_spec_prompt",
    # BA Collator prompts
    "merge_phase0_prompt",
    "merge_complete_specs_prompt",
    # BA Executive Summary prompts
    "generate_executive_summary_prompt",
    # Scraper Generator prompts
    "generate_collect_content_prompt",
    "generate_validate_content_prompt",
    "generate_complex_auth_prompt",
]
