"""Prompt templates for scraper generation.

This package contains prompt templates for code generation.
BA Analyzer prompts are now in agentic_scraper.business_analyst.prompts.
"""

# Import scraper generation prompts (these still exist)
try:
    from agentic_scraper.prompts.scraper_generator import (
        generate_collect_content_prompt,
        generate_validate_content_prompt,
        generate_complex_auth_prompt,
    )

    __all__ = [
        # Scraper Generator prompts
        "generate_collect_content_prompt",
        "generate_validate_content_prompt",
        "generate_complex_auth_prompt",
    ]
except ImportError:
    # If scraper_generator doesn't exist, just export empty list
    __all__ = []
