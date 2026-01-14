"""LLM module - Unified factory for Bedrock ChatBedrockConverse models.

This module provides a single entry point for all LLM creation through LLMFactory.

Single LLM Stack Architecture:
- Only ChatBedrockConverse used for all LLM calls (text, structured, vision)
- Three model roles: fast (planner), reasoning (analysis), vision (screenshots)
- Strict vision validation: raises ValueError if non-vision model used for vision

Example:
    >>> from agentic_scraper.llm.factory import LLMFactory
    >>> from agentic_scraper.business_analyst.config import BAConfig
    >>>
    >>> config = BAConfig()
    >>> factory = LLMFactory(config=config)
    >>>
    >>> # Create models for different roles
    >>> fast_model = factory.create_fast_model()      # Haiku, no extended thinking
    >>> reasoning_model = factory.create_reasoning_model()  # Haiku with extended thinking
    >>> vision_model = factory.create_vision_model()  # Sonnet, vision-capable
"""

from agentic_scraper.llm.factory import LLMFactory

__all__ = [
    "LLMFactory",
]
