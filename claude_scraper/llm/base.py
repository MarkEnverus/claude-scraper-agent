"""LLM provider protocol for abstraction layer.

This module defines the Protocol interface for LLM providers, enabling
duck typing and dependency injection for different LLM backends (Bedrock, Anthropic).

Example:
    >>> provider: LLMProvider = create_llm_provider('bedrock', config)
    >>> response = provider.invoke("What is 2+2?", system="You are a calculator")
"""

from typing import Protocol, Type, TypeVar
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


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

    def invoke_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system: str = ""
    ) -> T:
        """Invoke LLM with structured output using Claude's JSON schema feature.

        Uses Claude's native structured outputs API to ensure the response
        matches the provided Pydantic model schema. This eliminates the need
        for manual JSON parsing and validation.

        Args:
            prompt: User prompt/question to send to LLM
            response_model: Pydantic model class defining the expected response structure
            system: Optional system prompt for context/instructions

        Returns:
            Validated instance of response_model populated with LLM response data

        Raises:
            Exception: If LLM invocation fails after retries
            pydantic.ValidationError: If LLM response doesn't match schema (rare with structured outputs)

        Example:
            >>> from pydantic import BaseModel
            >>> class Phase0Detection(BaseModel):
            ...     detected_type: str
            ...     confidence: float
            >>>
            >>> result = provider.invoke_structured(
            ...     prompt="Analyze this data source...",
            ...     response_model=Phase0Detection,
            ...     system="You are a data analysis expert"
            ... )
            >>> print(result.detected_type)  # Type-safe access
            'API'
        """
        ...

    def invoke_structured_with_vision(
        self,
        prompt: str,
        images: list[str],
        response_model: Type[T],
        system: str = ""
    ) -> T:
        """Invoke LLM with vision + structured output.

        Combines Claude's vision capabilities with structured outputs, allowing
        the LLM to analyze images (screenshots) alongside text prompts and return
        validated Pydantic model responses.

        Args:
            prompt: User prompt/question to send to LLM
            images: List of image file paths (screenshots) to analyze
            response_model: Pydantic model class defining the expected response structure
            system: Optional system prompt for context/instructions

        Returns:
            Validated instance of response_model populated with LLM response data

        Raises:
            Exception: If LLM invocation fails after retries
            FileNotFoundError: If image file paths don't exist
            pydantic.ValidationError: If LLM response doesn't match schema

        Example:
            >>> from pydantic import BaseModel
            >>> class Phase0Detection(BaseModel):
            ...     detected_type: str
            ...     discovered_endpoint_urls: list[str]
            >>>
            >>> result = provider.invoke_structured_with_vision(
            ...     prompt="Look at this API documentation screenshot. Identify all operations.",
            ...     images=["/path/to/screenshot.png"],
            ...     response_model=Phase0Detection,
            ...     system="You are analyzing API documentation visually"
            ... )
            >>> print(len(result.discovered_endpoint_urls))  # Type-safe access
            10
        """
        ...
