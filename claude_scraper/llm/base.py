"""LLM provider protocol for abstraction layer.

This module defines the Protocol interface for LLM providers, enabling
duck typing and dependency injection for different LLM backends (Bedrock, Anthropic).

Example:
    >>> provider: LLMProvider = create_llm_provider('bedrock', config)
    >>> response = provider.invoke("What is 2+2?", system="You are a calculator")
"""

from typing import Protocol


class LLMProvider(Protocol):
    """Protocol for LLM providers using duck typing.

    This protocol defines the interface that all LLM providers must implement,
    allowing for flexible backend switching without tight coupling.

    Implementations:
        - BedrockProvider: AWS Bedrock runtime adapter
        - AnthropicProvider: Anthropic API adapter
    """

    def invoke(self, prompt: str, system: str = "") -> str:
        """Invoke LLM with prompt and return response text.

        Args:
            prompt: User prompt/question to send to LLM
            system: Optional system prompt for context/instructions

        Returns:
            LLM response text as string

        Raises:
            Exception: If LLM invocation fails after retries

        Example:
            >>> response = provider.invoke(
            ...     prompt="Analyze this data source",
            ...     system="You are a data analysis expert"
            ... )
        """
        ...
