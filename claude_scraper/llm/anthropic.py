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
from typing import Optional, TYPE_CHECKING, Type, TypeVar

from anthropic import Anthropic, APIError, RateLimitError, APITimeoutError, AuthenticationError
from pydantic import BaseModel

if TYPE_CHECKING:
    from logging import Logger

logger: "Logger" = logging.getLogger(__name__)
T = TypeVar('T', bound=BaseModel)


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
        model_id: str = "claude-sonnet-4-5-20250929",
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

                start = time.time()
                response = self.client.messages.create(**kwargs)
                elapsed = time.time() - start

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
                logger.info(f"[PERF] Anthropic API call: {elapsed:.2f}s, {len(text)} chars")

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

    def invoke_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system: str = ""
    ) -> T:
        """Invoke Claude with structured output using JSON schema.

        Uses Claude's native structured outputs feature to ensure the response
        matches the provided Pydantic model schema. Implements exponential
        backoff for rate limit and timeout errors.

        Args:
            prompt: User prompt to send to Claude
            response_model: Pydantic model class defining expected response structure
            system: Optional system prompt for instructions

        Returns:
            Validated instance of response_model with LLM response data

        Raises:
            Exception: If all retry attempts fail or non-retryable error occurs
            pydantic.ValidationError: If response doesn't match schema

        Example:
            >>> from pydantic import BaseModel
            >>> class Analysis(BaseModel):
            ...     detected_type: str
            ...     confidence: float
            >>>
            >>> result = provider.invoke_structured(
            ...     prompt="Analyze...",
            ...     response_model=Analysis
            ... )
        """
        if not prompt:
            raise ValueError("prompt cannot be empty")
        if not response_model:
            raise ValueError("response_model cannot be None")

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
                    f"Invoking Anthropic API with structured output (attempt {attempt + 1}/{self.max_retries})",
                    extra={
                        "model_id": self.model_id,
                        "prompt_length": len(prompt),
                        "has_system": bool(system),
                        "response_model": response_model.__name__
                    }
                )

                # Call Anthropic API with structured output
                schema = response_model.model_json_schema()

                # Inline $defs if present (Anthropic doesn't support $ref references)
                if "$defs" in schema:
                    defs = schema.pop("$defs")

                    def resolve_refs(obj, definitions):
                        """Recursively resolve $ref references by inlining definitions"""
                        if isinstance(obj, dict):
                            if "$ref" in obj:
                                # Extract definition name from #/$defs/TypeName
                                ref = obj["$ref"]
                                if ref.startswith("#/$defs/"):
                                    def_name = ref.replace("#/$defs/", "")
                                    if def_name in definitions:
                                        # Replace $ref with inline definition
                                        return resolve_refs(definitions[def_name].copy(), definitions)
                                return obj
                            else:
                                # Recursively process all dict values
                                return {k: resolve_refs(v, definitions) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [resolve_refs(item, definitions) for item in obj]
                        return obj

                    schema = resolve_refs(schema, defs)

                # Clean schema for Anthropic requirements
                def clean_schema_for_anthropic(obj):
                    """Recursively clean schema for Anthropic compatibility"""
                    if isinstance(obj, dict):
                        # Add additionalProperties: false for object types
                        if obj.get("type") == "object":
                            obj["additionalProperties"] = False

                        # Remove unsupported properties for number/integer types
                        if obj.get("type") in ("number", "integer"):
                            # Anthropic doesn't support maximum, minimum, multipleOf, etc.
                            for key in ["maximum", "minimum", "multipleOf", "exclusiveMaximum", "exclusiveMinimum"]:
                                obj.pop(key, None)

                        # Remove unsupported properties for string types
                        if obj.get("type") == "string":
                            # Keep enum and pattern, but remove format-specific validations
                            for key in ["minLength", "maxLength"]:
                                obj.pop(key, None)

                        # Recursively process all dict values
                        for value in obj.values():
                            clean_schema_for_anthropic(value)
                    elif isinstance(obj, list):
                        for item in obj:
                            clean_schema_for_anthropic(item)

                clean_schema_for_anthropic(schema)

                kwargs = {
                    "model": self.model_id,
                    "max_tokens": 8192,
                    "messages": messages,
                    "betas": ["structured-outputs-2025-11-13"],  # Beta header required!
                    # Claude's native structured output feature
                    "output_format": {  # NOT response_format!
                        "type": "json_schema",
                        "schema": schema  # Direct schema, no name field
                    }
                }

                if system:
                    kwargs["system"] = system

                response = self.client.beta.messages.create(**kwargs)  # Use beta client!

                # Extract text from response
                if not response.content:
                    raise ValueError("Empty response from Anthropic API")

                text = response.content[0].text
                if not text:
                    raise ValueError("No text in Anthropic API response")

                # Validate and parse with Pydantic
                # Claude's structured outputs should guarantee valid JSON matching schema
                result = response_model.model_validate_json(text)

                logger.info(
                    "Successfully invoked Anthropic API with structured output",
                    extra={
                        "model_id": self.model_id,
                        "response_model": response_model.__name__,
                        "attempts": attempt + 1
                    }
                )

                return result

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
            f"Anthropic structured invocation failed after {self.max_retries} retries (model: {self.model_id})"
        ) from last_exception

    def invoke_structured_with_vision(
        self,
        prompt: str,
        images: list[str],
        response_model: Type[T],
        system: str = ""
    ) -> T:
        """Invoke Claude with vision + structured output.

        Combines Claude's vision capabilities with structured outputs, allowing
        analysis of screenshots alongside text prompts with validated Pydantic responses.

        Args:
            prompt: User prompt/question to send to Claude
            images: List of image file paths (screenshots) to analyze
            response_model: Pydantic model class defining expected response structure
            system: Optional system prompt for instructions

        Returns:
            Validated instance of response_model with LLM response data

        Raises:
            ValueError: If prompt/images/response_model invalid
            FileNotFoundError: If image file doesn't exist
            Exception: If all retry attempts fail

        Example:
            >>> result = provider.invoke_structured_with_vision(
            ...     prompt="Identify all API operations visible in these screenshots",
            ...     images=["/path/to/screenshot.png"],
            ...     response_model=Phase0Detection
            ... )
        """
        import base64
        import os

        if not prompt:
            raise ValueError("prompt cannot be empty")
        if not images:
            raise ValueError("images list cannot be empty")
        if not response_model:
            raise ValueError("response_model cannot be None")

        # Load and encode images
        image_blocks = []
        for img_path in images:
            if not os.path.exists(img_path):
                raise FileNotFoundError(f"Image file not found: {img_path}")

            # FIX #2: Validate file size before encoding to prevent ISO-NE 5.98MB failure
            file_size = os.path.getsize(img_path)
            file_size_mb = file_size / (1024 * 1024)
            MAX_SIZE_MB = 4.5  # Account for ~33% base64 overhead

            if file_size_mb > MAX_SIZE_MB:
                raise ValueError(
                    f"Image file too large: {img_path} ({file_size_mb:.2f}MB). "
                    f"Anthropic API limit is 5MB and base64 encoding adds ~33% overhead. "
                    f"Maximum recommended file size is {MAX_SIZE_MB}MB. "
                    f"The image should be compressed before passing to the API."
                )
            elif file_size_mb > 3.0:
                logger.warning(
                    f"Image file size is large: {os.path.basename(img_path)} ({file_size_mb:.2f}MB). "
                    f"Approaching {MAX_SIZE_MB}MB limit. Consider compression if issues occur."
                )

            with open(img_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            # Determine media type from extension
            ext = os.path.splitext(img_path)[1].lower()
            media_type = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.webp': 'image/webp',
                '.gif': 'image/gif'
            }.get(ext, 'image/png')

            image_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_data
                }
            })

        # Build messages with images + text
        messages = [
            {
                "role": "user",
                "content": [
                    *image_blocks,  # Images first
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]

        # Retry loop with exponential backoff
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"Invoking Anthropic API with vision + structured output (attempt {attempt + 1}/{self.max_retries})",
                    extra={
                        "model_id": self.model_id,
                        "prompt_length": len(prompt),
                        "num_images": len(images),
                        "has_system": bool(system),
                        "response_model": response_model.__name__
                    }
                )

                # Prepare schema (same as invoke_structured)
                schema = response_model.model_json_schema()

                # Inline $defs if present
                if "$defs" in schema:
                    defs = schema.pop("$defs")

                    def resolve_refs(obj, definitions):
                        if isinstance(obj, dict):
                            if "$ref" in obj:
                                ref = obj["$ref"]
                                if ref.startswith("#/$defs/"):
                                    def_name = ref.replace("#/$defs/", "")
                                    if def_name in definitions:
                                        return resolve_refs(definitions[def_name].copy(), definitions)
                                return obj
                            else:
                                return {k: resolve_refs(v, definitions) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [resolve_refs(item, definitions) for item in obj]
                        return obj

                    schema = resolve_refs(schema, defs)

                # Clean schema for Anthropic compatibility
                def clean_schema_for_anthropic(obj):
                    """Recursively clean schema for Anthropic compatibility"""
                    if isinstance(obj, dict):
                        # Add additionalProperties: false for object types
                        if obj.get("type") == "object":
                            obj["additionalProperties"] = False

                        # Remove unsupported properties for number/integer types
                        if obj.get("type") in ("number", "integer"):
                            # Anthropic doesn't support maximum, minimum, multipleOf, etc.
                            for key in ["maximum", "minimum", "multipleOf", "exclusiveMaximum", "exclusiveMinimum"]:
                                obj.pop(key, None)

                        # Remove unsupported properties for string types
                        if obj.get("type") == "string":
                            # Keep enum and pattern, but remove format-specific validations
                            for key in ["minLength", "maxLength"]:
                                obj.pop(key, None)

                        # Recursively process all dict values
                        for value in obj.values():
                            clean_schema_for_anthropic(value)
                    elif isinstance(obj, list):
                        for item in obj:
                            clean_schema_for_anthropic(item)

                clean_schema_for_anthropic(schema)

                # Call Anthropic API with vision + structured output
                kwargs = {
                    "model": self.model_id,
                    "max_tokens": 4096,
                    "messages": messages,
                    "betas": ["structured-outputs-2025-11-13"],
                    "output_format": {
                        "type": "json_schema",
                        "schema": schema
                    }
                }

                if system:
                    kwargs["system"] = system

                response = self.client.beta.messages.create(**kwargs)

                # Extract text from response
                if not response.content:
                    raise ValueError("Empty response from Anthropic API")

                text = response.content[0].text
                if not text:
                    raise ValueError("No text in Anthropic API response")

                # Validate and parse with Pydantic
                result = response_model.model_validate_json(text)

                logger.info(
                    "Successfully invoked Anthropic API with vision + structured output",
                    extra={
                        "model_id": self.model_id,
                        "response_model": response_model.__name__,
                        "num_images": len(images),
                        "attempts": attempt + 1
                    }
                )

                return result

            except RateLimitError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(f"Retry {attempt + 1}/{self.max_retries} after {delay}s - Rate limited by Anthropic API")
                    time.sleep(delay)
                    continue
                else:
                    logger.error("Max retries exceeded for rate limits", exc_info=True)
                    raise Exception(f"Rate limit persisted after {self.max_retries} retries") from e

            except APITimeoutError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(f"Retry {attempt + 1}/{self.max_retries} after {delay}s - Anthropic API timeout")
                    time.sleep(delay)
                    continue
                else:
                    logger.error("Max retries exceeded for timeouts", exc_info=True)
                    raise Exception(f"Timeout persisted after {self.max_retries} retries") from e

            except APIError as e:
                last_exception = e
                logger.error(f"Anthropic API error: {e}", exc_info=True)
                raise Exception(f"Anthropic API invocation failed: {e}") from e

            except Exception as e:
                last_exception = e
                logger.error(f"Unexpected error: {e}", exc_info=True)
                raise Exception(f"Anthropic invocation failed: {e}") from e

        # All retries exhausted
        raise Exception(
            f"Anthropic vision invocation failed after {self.max_retries} retries"
        ) from last_exception
