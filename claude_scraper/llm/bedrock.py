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
from typing import Optional, TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

if TYPE_CHECKING:
    from logging import Logger

logger: "Logger" = logging.getLogger(__name__)


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
