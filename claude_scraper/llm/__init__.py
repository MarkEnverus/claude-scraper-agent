"""LLM client abstractions for Bedrock and Anthropic"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_scraper.llm.base import LLMProvider
    from claude_scraper.llm.bedrock import BedrockProvider
    from claude_scraper.llm.anthropic import AnthropicProvider
    from claude_scraper.llm.factory import create_llm_provider

__all__ = [
    "LLMProvider",
    "BedrockProvider",
    "AnthropicProvider",
    "create_llm_provider",
]


def __getattr__(name: str):
    """Lazy load modules to avoid import errors when dependencies not installed."""
    if name == "LLMProvider":
        from claude_scraper.llm.base import LLMProvider
        return LLMProvider
    elif name == "BedrockProvider":
        from claude_scraper.llm.bedrock import BedrockProvider
        return BedrockProvider
    elif name == "AnthropicProvider":
        from claude_scraper.llm.anthropic import AnthropicProvider
        return AnthropicProvider
    elif name == "create_llm_provider":
        from claude_scraper.llm.factory import create_llm_provider
        return create_llm_provider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
