"""Anthropic API LLM provider adapter.

This module provides an adapter for the Anthropic API, implementing
exponential backoff retry logic for rate limiting errors.

Example:
    >>> import os
    >>> provider = AnthropicProvider(
    ...     model_id='claude-sonnet-4-5-20251101',
    ...     api_key=os.getenv('ANTHROPIC_API_KEY')
    ... )
    >>> response = provider.invoke("What is 2+2?")
"""

import logging
import time
from typing import Optional, TYPE_CHECKING

from anthropic import Anthropic, APIError, RateLimitError, APITimeoutError, AuthenticationError

if TYPE_CHECKING:
    from logging import Logger

logger: "Logger" = logging.getLogger(__name__)


class AnthropicProvider:
    """Anthropic API adapter for Claude models.

    Implements the LLMProvider protocol with Anthropic API backend.
    Handles API key authentication and implements exponential backoff
    for rate limiting.

    Attributes:
        model_id: Anthropic model identifier (e.g., 'claude-sonnet-4-5-20251101')
        api_key: Anthropic API key
        client: Anthropic SDK client
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds for exponential backoff (default: 1)

    Example:
        >>> provider = AnthropicProvider(
        ...     model_id='claude-sonnet-4-5-20251101',
        ...     api_key='sk-ant-...'
        ... )
        >>> response = provider.invoke("Analyze this data")
    """

    def __init__(
        self,
        model_id: str = "claude-sonnet-4-5-20251101",
        api_key: Optional[str] = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        timeout: float = 30.0
    ) -> None:
        """Initialize Anthropic provider.

        Args:
            model_id: Anthropic model identifier
            api_key: Anthropic API key (reads from ANTHROPIC_API_KEY env if not provided)
            max_retries: Maximum retry attempts for transient errors
            base_delay: Base delay in seconds for exponential backoff
            timeout: Timeout in seconds for API calls (default: 30)

        Raises:
            ValueError: If model_id is empty or API key not found
        """
        if not model_id:
            raise ValueError("model_id cannot be empty")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self.model_id = model_id
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.timeout = timeout

        # Initialize Anthropic client (will read ANTHROPIC_API_KEY from env if api_key not provided)
        try:
            self.client = Anthropic(api_key=api_key, timeout=timeout)
        except Exception as e:
            raise ValueError(
                "Failed to initialize Anthropic client. "
                "Ensure ANTHROPIC_API_KEY environment variable is set."
            ) from e

    def invoke(self, prompt: str, system: str = "") -> str:
        """Invoke Claude model via Anthropic API with retry logic.

        Implements exponential backoff for rate limit errors (429).
        Retries up to max_retries times with delays: 1s, 2s, 4s.

        Args:
            prompt: User prompt to send to Claude
            system: Optional system prompt for instructions

        Returns:
            Claude's response text

        Raises:
            Exception: If all retry attempts fail or non-retryable error occurs

        Example:
            >>> response = provider.invoke(
            ...     prompt="What is 2+2?",
            ...     system="You are a calculator"
            ... )
        """
        if not prompt:
            raise ValueError("prompt cannot be empty")

        # Build messages
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]

        # Retry loop with exponential backoff
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"Invoking Anthropic API (attempt {attempt + 1}/{self.max_retries})",
                    extra={
                        "model_id": self.model_id,
                        "prompt_length": len(prompt),
                        "has_system": bool(system)
                    }
                )

                # Call Anthropic API
                kwargs = {
                    "model": self.model_id,
                    "max_tokens": 8192,  # Increased for large structured outputs (ValidatedSpec)
                    "messages": messages
                }

                if system:
                    kwargs["system"] = system

                response = self.client.messages.create(**kwargs)

                # Extract text from response
                if not response.content:
                    raise ValueError("Empty response from Anthropic API")

                text = response.content[0].text
                if not text:
                    raise ValueError("No text in Anthropic API response")

                logger.info(
                    "Successfully invoked Anthropic API",
                    extra={
                        "model_id": self.model_id,
                        "response_length": len(text),
                        "attempts": attempt + 1
                    }
                )

                return text

            except RateLimitError as e:
                last_exception = e

                # Rate limit errors are retryable
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(
                        f"Retry {attempt + 1}/{self.max_retries} after {delay}s - Rate limited by Anthropic API (429)",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self.max_retries,
                            "model_id": self.model_id
                        }
                    )
                    time.sleep(delay)
                    continue
                else:
                    logger.error(
                        "Max retries exceeded for Anthropic rate limiting",
                        extra={"model_id": self.model_id},
                        exc_info=True
                    )
                    raise Exception(
                        f"Anthropic rate limiting persisted after {self.max_retries} retries (model: {self.model_id})"
                    ) from e

            except APITimeoutError as e:
                last_exception = e

                # Timeout errors are retryable
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(
                        f"Retry {attempt + 1}/{self.max_retries} after {delay}s - Anthropic API timeout",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self.max_retries,
                            "model_id": self.model_id
                        }
                    )
                    time.sleep(delay)
                    continue
                else:
                    logger.error(
                        "Max retries exceeded for Anthropic timeouts",
                        extra={"model_id": self.model_id},
                        exc_info=True
                    )
                    raise Exception(
                        f"Anthropic API timeout persisted after {self.max_retries} retries (model: {self.model_id})"
                    ) from e

            except APIError as e:
                last_exception = e

                # Log and raise non-retryable API errors
                logger.error(
                    f"Anthropic API error: {e}",
                    extra={"model_id": self.model_id},
                    exc_info=True
                )
                raise Exception(f"Anthropic API invocation failed: {e} (model: {self.model_id})") from e

            except Exception as e:
                last_exception = e

                # Log and raise unexpected errors
                logger.error(
                    f"Unexpected Anthropic error: {e}",
                    extra={"model_id": self.model_id},
                    exc_info=True
                )
                raise Exception(f"Anthropic invocation failed: {e} (model: {self.model_id})") from e

        # All retries exhausted
        raise Exception(
            f"Anthropic invocation failed after {self.max_retries} retries (model: {self.model_id})"
        ) from last_exception
