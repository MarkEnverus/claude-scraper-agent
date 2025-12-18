"""LLM provider factory for creating provider instances.

This module provides a factory function for creating LLM provider instances
based on configuration, enabling dependency injection and easy provider switching.

Example:
    >>> from claude_scraper.cli.config import Config
    >>> config = Config(provider='bedrock', region='us-east-1')
    >>> provider = create_llm_provider('bedrock', config)
    >>> response = provider.invoke("What is 2+2?")
"""

from claude_scraper.cli.config import Config
from claude_scraper.llm.base import LLMProvider
from claude_scraper.llm.bedrock import BedrockProvider
from claude_scraper.llm.anthropic import AnthropicProvider


def create_llm_provider(provider: str, config: Config) -> LLMProvider:
    """Create LLM provider instance based on provider name.

    Factory function that instantiates the appropriate LLM provider
    (Bedrock or Anthropic) based on the provider string and configuration.

    Args:
        provider: Provider name ('bedrock' or 'anthropic')
        config: Configuration object with provider settings

    Returns:
        LLMProvider: Instance of BedrockProvider or AnthropicProvider
            implementing the LLMProvider protocol

    Raises:
        ValueError: If provider is not 'bedrock' or 'anthropic', or if
            config.provider doesn't match provider parameter

    Example:
        >>> config = Config(
        ...     provider='bedrock',
        ...     model_id='anthropic.claude-sonnet-4-5-v2:0',
        ...     region='us-east-1'
        ... )
        >>> provider = create_llm_provider('bedrock', config)
        >>> response = provider.invoke("Analyze this data")
    """
    # Validate provider parameter matches config.provider
    if config.provider != provider:
        raise ValueError(
            f"Provider mismatch: provider parameter '{provider}' does not match "
            f"config.provider '{config.provider}'"
        )

    # Validate provider value
    if provider not in ("bedrock", "anthropic"):
        raise ValueError(
            f"Unknown provider: {provider}. Must be 'bedrock' or 'anthropic'"
        )

    if provider == "bedrock":
        if not config.region:
            raise ValueError("region required for Bedrock provider")

        return BedrockProvider(
            model_id=config.model_id,
            region=config.region
        )

    elif provider == "anthropic":
        return AnthropicProvider(
            model_id=config.model_id,
            api_key=config.api_key
        )

    else:
        # This should never be reached due to validation above, but kept for completeness
        raise ValueError(
            f"Unknown provider: {provider}. Must be 'bedrock' or 'anthropic'"
        )
