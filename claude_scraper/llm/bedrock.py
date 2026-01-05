"""AWS Bedrock LLM provider adapter.

This module provides an adapter for AWS Bedrock Runtime API, implementing
exponential backoff retry logic for throttling and timeout errors.

Example:
    >>> provider = BedrockProvider(
    ...     model_id='anthropic.claude-sonnet-4-5-v2:0',
    ...     region='us-east-1'
    ... )
    >>> response = provider.invoke("What is 2+2?")
"""

import json
import logging
import time
from typing import Optional, TYPE_CHECKING, Type, TypeVar

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from pydantic import BaseModel

if TYPE_CHECKING:
    from logging import Logger

logger: "Logger" = logging.getLogger(__name__)
T = TypeVar('T', bound=BaseModel)


class BedrockProvider:
    """AWS Bedrock Runtime adapter for Claude models.

    Implements the LLMProvider protocol with AWS Bedrock backend.
    Handles authentication via IAM roles/profiles and implements
    exponential backoff for rate limiting.

    Attributes:
        model_id: Bedrock model identifier (e.g., 'anthropic.claude-sonnet-4-5-v2:0')
        region: AWS region name
        client: Boto3 Bedrock Runtime client
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds for exponential backoff (default: 1)

    Example:
        >>> provider = BedrockProvider(
        ...     model_id='anthropic.claude-sonnet-4-5-v2:0',
        ...     region='us-east-1'
        ... )
        >>> response = provider.invoke("Analyze this data")
    """

    def __init__(
        self,
        model_id: str = "anthropic.claude-sonnet-4-5-v2:0",
        region: str = "us-east-1",
        max_retries: int = 3,
        base_delay: float = 1.0,
        timeout: float = 30.0
    ) -> None:
        """Initialize Bedrock provider.

        Args:
            model_id: Bedrock model identifier
            region: AWS region name
            max_retries: Maximum retry attempts for transient errors
            base_delay: Base delay in seconds for exponential backoff
            timeout: Timeout in seconds for API calls (default: 30)

        Raises:
            ValueError: If model_id or region is empty, or if AWS credentials are not configured
        """
        if not model_id:
            raise ValueError("model_id cannot be empty")
        if not region:
            raise ValueError("region cannot be empty")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self.model_id = model_id
        self.region = region
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.timeout = timeout

        # Initialize boto3 client with error handling
        try:
            from botocore.config import Config as BotoConfig
            boto_config = BotoConfig(
                read_timeout=timeout,
                connect_timeout=timeout,
                retries={'max_attempts': 0}  # We handle retries ourselves
            )
            self.client = boto3.client(
                "bedrock-runtime",
                region_name=region,
                config=boto_config
            )
        except (NoCredentialsError, PartialCredentialsError) as e:
            raise ValueError(
                "AWS credentials not found or incomplete. "
                "Please configure AWS credentials via environment variables, "
                "AWS credentials file, or IAM role."
            ) from e
        except Exception as e:
            raise ValueError(
                f"Failed to initialize Bedrock client: {e}"
            ) from e

    def invoke(self, prompt: str, system: str = "") -> str:
        """Invoke Claude model via Bedrock with retry logic.

        Implements exponential backoff for throttling (429) and timeout errors.
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

        # Build request body following Bedrock Messages API format
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 8192,  # Increased for large structured outputs (ValidatedSpec)
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        if system:
            body["system"] = system

        # Retry loop with exponential backoff
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"Invoking Bedrock model (attempt {attempt + 1}/{self.max_retries})",
                    extra={
                        "model_id": self.model_id,
                        "prompt_length": len(prompt),
                        "has_system": bool(system)
                    }
                )

                response = self.client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                    accept="application/json"
                )

                # Parse response
                response_body = json.loads(response["body"].read())

                # Extract text from content array
                content = response_body.get("content", [])
                if not content:
                    raise ValueError("Empty response from Bedrock")

                text = content[0].get("text", "")
                if not text:
                    raise ValueError("No text in Bedrock response")

                logger.info(
                    "Successfully invoked Bedrock model",
                    extra={
                        "model_id": self.model_id,
                        "response_length": len(text),
                        "attempts": attempt + 1
                    }
                )

                return text

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                last_exception = e

                # Check if error is retryable
                if error_code in ("ThrottlingException", "TooManyRequestsException"):
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{self.max_retries} after {delay}s - Throttled by Bedrock (429)",
                            extra={
                                "attempt": attempt + 1,
                                "max_retries": self.max_retries,
                                "error_code": error_code,
                                "model_id": self.model_id
                            }
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(
                            "Max retries exceeded for Bedrock throttling",
                            extra={"model_id": self.model_id},
                            exc_info=True
                        )
                        raise Exception(
                            f"Bedrock throttling persisted after {self.max_retries} retries (model: {self.model_id})"
                        ) from e

                # Non-retryable errors
                logger.error(
                    f"Bedrock invocation failed: {error_code}",
                    extra={"model_id": self.model_id, "error_code": error_code},
                    exc_info=True
                )
                raise Exception(f"Bedrock invocation failed: {error_code} (model: {self.model_id})") from e

            except Exception as e:
                last_exception = e

                # Retry on timeout or connection errors
                if "timeout" in str(e).lower() or "connection" in str(e).lower():
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{self.max_retries} after {delay}s - Bedrock timeout/connection error",
                            extra={
                                "attempt": attempt + 1,
                                "max_retries": self.max_retries,
                                "error": str(e),
                                "model_id": self.model_id
                            }
                        )
                        time.sleep(delay)
                        continue

                logger.error(
                    f"Unexpected Bedrock error: {e}",
                    extra={"model_id": self.model_id},
                    exc_info=True
                )
                raise Exception(f"Bedrock invocation failed: {e} (model: {self.model_id})") from e

        # All retries exhausted
        raise Exception(
            f"Bedrock invocation failed after {self.max_retries} retries (model: {self.model_id})"
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
        backoff for throttling and timeout errors.

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

        # Build request body with tool use for structured outputs (Bedrock doesn't support native structured outputs)
        tool_name = f"provide_{response_model.__name__.lower()}"
        schema = response_model.model_json_schema()

        # Remove $defs if present (not supported in tool schemas)
        if "$defs" in schema:
            del schema["$defs"]

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 8192,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            # Use tool use for structured outputs (Bedrock approach)
            "tools": [{
                "name": tool_name,
                "description": f"Provide structured output matching {response_model.__name__} schema",
                "input_schema": schema
            }],
            "tool_choice": {
                "type": "tool",
                "name": tool_name
            }
        }

        if system:
            body["system"] = system

        # Retry loop with exponential backoff (same pattern as invoke())
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"Invoking Bedrock model with structured output (attempt {attempt + 1}/{self.max_retries})",
                    extra={
                        "model_id": self.model_id,
                        "prompt_length": len(prompt),
                        "has_system": bool(system),
                        "response_model": response_model.__name__
                    }
                )

                response = self.client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                    accept="application/json"
                )

                # Parse response
                response_body = json.loads(response["body"].read())

                # Extract tool use from content array
                content = response_body.get("content", [])
                if not content:
                    raise ValueError("Empty response from Bedrock")

                # Find tool use block
                tool_use = None
                for block in content:
                    if block.get("type") == "tool_use":
                        tool_use = block
                        break

                if not tool_use:
                    raise ValueError("No tool use in Bedrock response")

                # Extract structured data from tool use input
                tool_input = tool_use.get("input")
                if not tool_input:
                    raise ValueError("No input in Bedrock tool use response")

                # Validate and parse with Pydantic
                # Tool use approach guarantees structured data matching schema
                result = response_model.model_validate(tool_input)

                logger.info(
                    "Successfully invoked Bedrock model with structured output",
                    extra={
                        "model_id": self.model_id,
                        "response_model": response_model.__name__,
                        "attempts": attempt + 1
                    }
                )

                return result

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                last_exception = e

                # Check if error is retryable
                if error_code in ("ThrottlingException", "TooManyRequestsException"):
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{self.max_retries} after {delay}s - Throttled by Bedrock (429)",
                            extra={
                                "attempt": attempt + 1,
                                "max_retries": self.max_retries,
                                "error_code": error_code,
                                "model_id": self.model_id
                            }
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(
                            "Max retries exceeded for Bedrock throttling",
                            extra={"model_id": self.model_id},
                            exc_info=True
                        )
                        raise Exception(
                            f"Bedrock throttling persisted after {self.max_retries} retries (model: {self.model_id})"
                        ) from e

                # Non-retryable errors
                logger.error(
                    f"Bedrock invocation failed: {error_code}",
                    extra={"model_id": self.model_id, "error_code": error_code},
                    exc_info=True
                )
                raise Exception(f"Bedrock invocation failed: {error_code} (model: {self.model_id})") from e

            except Exception as e:
                last_exception = e

                # Retry on timeout or connection errors
                if "timeout" in str(e).lower() or "connection" in str(e).lower():
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{self.max_retries} after {delay}s - Bedrock timeout/connection error",
                            extra={
                                "attempt": attempt + 1,
                                "max_retries": self.max_retries,
                                "error": str(e),
                                "model_id": self.model_id
                            }
                        )
                        time.sleep(delay)
                        continue

                logger.error(
                    f"Unexpected Bedrock error: {e}",
                    extra={"model_id": self.model_id},
                    exc_info=True
                )
                raise Exception(f"Bedrock invocation failed: {e} (model: {self.model_id})") from e

        # All retries exhausted
        raise Exception(
            f"Bedrock structured invocation failed after {self.max_retries} retries (model: {self.model_id})"
        ) from last_exception

    def invoke_structured_with_vision(
        self,
        prompt: str,
        images: list[str],
        response_model: Type[T],
        system: str = ""
    ) -> T:
        """Invoke Claude with vision + structured output using Bedrock.

        Combines Claude's vision capabilities with structured outputs via tool use,
        allowing the LLM to analyze images (screenshots) alongside text prompts and
        return validated Pydantic model responses.

        Args:
            prompt: User prompt/question to send to Claude
            images: List of image file paths (screenshots) to analyze
            response_model: Pydantic model class defining expected response structure
            system: Optional system prompt for instructions

        Returns:
            Validated instance of response_model with LLM response data

        Raises:
            Exception: If all retry attempts fail or non-retryable error occurs
            FileNotFoundError: If image file paths don't exist
            pydantic.ValidationError: If response doesn't match schema

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
        """
        import base64
        import os

        # Validation
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

            # FIX #2: Validate file size before encoding (same as anthropic.py)
            file_size = os.path.getsize(img_path)
            file_size_mb = file_size / (1024 * 1024)
            MAX_SIZE_MB = 4.5  # Account for ~33% base64 overhead

            if file_size_mb > MAX_SIZE_MB:
                raise ValueError(
                    f"Image file too large: {img_path} ({file_size_mb:.2f}MB). "
                    f"Claude on Bedrock has 5MB limit and base64 encoding adds ~33% overhead. "
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

        # Build request body with tool use for structured outputs
        tool_name = f"provide_{response_model.__name__.lower()}"
        schema = response_model.model_json_schema()

        # Remove $defs if present (not supported in tool schemas)
        if "$defs" in schema:
            del schema["$defs"]

        # Build message content with images first, then text
        message_content = [
            *image_blocks,  # Images first
            {
                "type": "text",
                "text": prompt
            }
        ]

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 8192,
            "messages": [
                {
                    "role": "user",
                    "content": message_content
                }
            ],
            # Use tool use for structured outputs (Bedrock approach)
            "tools": [{
                "name": tool_name,
                "description": f"Provide structured output matching {response_model.__name__} schema",
                "input_schema": schema
            }],
            "tool_choice": {
                "type": "tool",
                "name": tool_name
            }
        }

        if system:
            body["system"] = system

        # Retry loop with exponential backoff
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"Invoking Bedrock model with vision + structured output (attempt {attempt + 1}/{self.max_retries})",
                    extra={
                        "model_id": self.model_id,
                        "prompt_length": len(prompt),
                        "num_images": len(images),
                        "has_system": bool(system),
                        "response_model": response_model.__name__
                    }
                )

                response = self.client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                    accept="application/json"
                )

                # Parse response
                response_body = json.loads(response["body"].read())

                # Extract tool use from content array
                content = response_body.get("content", [])
                if not content:
                    raise ValueError("Empty response from Bedrock")

                # Find tool use block
                tool_use = None
                for block in content:
                    if block.get("type") == "tool_use":
                        tool_use = block
                        break

                if not tool_use:
                    raise ValueError("No tool use in Bedrock response")

                # Extract structured data from tool use input
                tool_input = tool_use.get("input")
                if not tool_input:
                    raise ValueError("No input in Bedrock tool use response")

                # Validate and parse with Pydantic
                result = response_model.model_validate(tool_input)

                logger.info(
                    "Successfully invoked Bedrock model with vision + structured output",
                    extra={
                        "model_id": self.model_id,
                        "response_model": response_model.__name__,
                        "num_images": len(images),
                        "attempts": attempt + 1
                    }
                )

                return result

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                last_exception = e

                # Check if error is retryable
                if error_code in ("ThrottlingException", "TooManyRequestsException"):
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{self.max_retries} after {delay}s - Throttled by Bedrock (429)",
                            extra={
                                "attempt": attempt + 1,
                                "max_retries": self.max_retries,
                                "error_code": error_code,
                                "model_id": self.model_id
                            }
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(
                            "Max retries exceeded for Bedrock throttling",
                            extra={"model_id": self.model_id},
                            exc_info=True
                        )
                        raise Exception(
                            f"Bedrock throttling persisted after {self.max_retries} retries (model: {self.model_id})"
                        ) from e

                # Non-retryable errors
                logger.error(
                    f"Bedrock vision invocation failed: {error_code}",
                    extra={"model_id": self.model_id, "error_code": error_code},
                    exc_info=True
                )
                raise Exception(f"Bedrock vision invocation failed: {error_code} (model: {self.model_id})") from e

            except Exception as e:
                last_exception = e

                # Retry on timeout or connection errors
                if "timeout" in str(e).lower() or "connection" in str(e).lower():
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{self.max_retries} after {delay}s - Bedrock timeout/connection error",
                            extra={
                                "attempt": attempt + 1,
                                "max_retries": self.max_retries,
                                "error": str(e),
                                "model_id": self.model_id
                            }
                        )
                        time.sleep(delay)
                        continue

                logger.error(
                    f"Unexpected Bedrock vision error: {e}",
                    extra={"model_id": self.model_id},
                    exc_info=True
                )
                raise Exception(f"Bedrock vision invocation failed: {e} (model: {self.model_id})") from e

        # All retries exhausted
        raise Exception(
            f"Bedrock vision invocation failed after {self.max_retries} retries (model: {self.model_id})"
        ) from last_exception
