"""Configuration management for Claude Scraper CLI.

This module provides configuration loading and validation for different LLM providers
(Bedrock and Anthropic), including environment variable management and format validation.
"""

import os
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Config:
    """Configuration for Claude Scraper CLI"""

    provider: Literal["bedrock", "anthropic"]
    model_id: str
    region: str | None  # For Bedrock
    api_key: str | None  # For Anthropic

    def __post_init__(self) -> None:
        """Validate configuration after initialization"""
        # Validate Bedrock model_id format
        if self.provider == "bedrock":
            if not self.model_id.startswith("anthropic.claude-"):
                raise ValueError(
                    f"Invalid Bedrock model_id: {self.model_id}. "
                    "Must start with 'anthropic.claude-'. "
                    "Valid examples: 'anthropic.claude-sonnet-4-5-v2:0', "
                    "'anthropic.claude-opus-4-5-20251101-v1:0'"
                )

        # Validate Anthropic API key format
        if self.provider == "anthropic" and self.api_key:
            if not self.api_key.startswith("sk-ant-"):
                raise ValueError(
                    f"Invalid ANTHROPIC_API_KEY format. "
                    "Anthropic API keys must start with 'sk-ant-'"
                )

    @classmethod
    def from_env(cls, provider: Literal["bedrock", "anthropic"] = "bedrock") -> "Config":
        """Load configuration from environment variables

        Args:
            provider: LLM provider to use ('bedrock' or 'anthropic')

        Returns:
            Config: Configured instance

        Raises:
            ValueError: If provider is unknown or required env vars are missing
        """
        if provider == "bedrock":
            return cls(
                provider="bedrock",
                model_id=os.getenv(
                    "BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-5-20250929-v1:0"
                ),
                region=os.getenv("AWS_REGION", "us-west-2"),
                api_key=None,
            )
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY environment variable required for Anthropic provider"
                )
            return cls(
                provider="anthropic",
                model_id="claude-sonnet-4-5-20250929",
                region=None,
                api_key=api_key,
            )
        else:
            raise ValueError(
                f"Unknown provider: {provider}. Must be 'bedrock' or 'anthropic'"
            )
