"""Configuration for BA Analyst.

This module defines the configuration options for the Business Analyst system.
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class Credentials(BaseModel):
    """Credentials for authenticated requests."""
    type: str = Field(..., description="Credential type: bearer, basic, or cookie")
    value: str = Field(..., description="Credential value (token, username:password, etc.)")


class BAConfig(BaseModel):
    """Configuration for BA Analyst.

    Controls behavior of fetching, rendering, navigation, and stop conditions.
    """
    # Rendering configuration
    render_mode: str = Field("auto", description="Screenshot mode: always, auto, or never")
    render_enabled: bool = Field(True, description="Master switch for rendering (disable in CI)")
    max_screenshots: int = Field(20, description="Maximum screenshots to capture (cost control)")

    # Navigation limits
    max_depth: int = Field(3, description="Maximum navigation depth from seed URL")
    max_steps: int = Field(50, description="Maximum total pages to visit")
    allowed_domains: list[str] = Field(default_factory=list, description="Allowed domains (empty = same domain only)")

    # Stop thresholds
    high_value_threshold: float = Field(0.5, description="Minimum combined score for high-value links")
    auth_block_tolerance: int = Field(3, description="Max consecutive 401/403 before stopping")
    rate_limit_tolerance: int = Field(5, description="Max total 429 rate limits before stopping")
    forbidden_tolerance: int = Field(3, description="Max total 403 forbidden before stopping")

    # Minimum discovery thresholds (prevent premature stopping)
    min_pages_before_stop: int = Field(5, description="Minimum pages to analyze before allowing stop")
    min_candidate_api_calls: int = Field(3, description="Minimum API calls to discover before allowing stop")
    min_high_value_links_seen: int = Field(10, description="Minimum high-value links to see before allowing stop")

    # Auth configuration
    respect_robots: bool = Field(False, description="Respect robots.txt directives")
    stop_on_auth_gate: bool = Field(True, description="Stop at login portals vs continue with docs")
    credentials: Optional[Credentials] = Field(None, description="Optional credentials for auth")

    # Cost controls
    max_tokens_per_chunk: int = Field(2000, description="Max tokens per markdown chunk")
    max_chunks_per_page: int = Field(3, description="Max chunks to analyze per page")
    max_tokens_per_llm_call: int = Field(4096, description="Max tokens per LLM output")
    max_endpoints_to_analyze: int = Field(10, description="Max endpoints to analyze in detail")

    # Endpoint filtering configuration (NEW_GRAPH_v2)
    max_endpoints_for_generation: int = Field(
        5,
        description="Maximum endpoints to pass to scraper generator (prevents scraper explosion)"
    )
    endpoint_min_confidence: float = Field(
        0.7,
        description="Minimum confidence threshold for LLM-classified endpoints (0.0-1.0)"
    )

    # Parameter analysis configuration (Phase 1.5 - MISO operations discovery)
    enable_parameter_analysis: bool = Field(
        True,
        description="Enable Phase 1.5 parameter analysis (LLM enrichment of parameter metadata)"
    )
    max_operations_per_api: int = Field(
        20,
        description="Maximum operations to discover per API (prevents explosion on APIM portals)"
    )

    # Context management
    max_messages_in_history: int = Field(12, description="Maximum messages to keep in ReAct agent history")

    # LLM configuration - Role-based model selection
    model_fast: str = Field(
        "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        description="Fast/cheap model for planner and navigation (Haiku, no extended thinking)"
    )
    model_reasoning: str = Field(
        "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        description="Deep reasoning model for analysis (Haiku with extended thinking)"
    )
    model_vision: str = Field(
        "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        description="Vision-capable model for screenshots (must support images)"
    )

    # AWS configuration
    aws_region: str = Field("us-east-1", description="AWS region for Bedrock")

    # Per-role max tokens
    max_tokens_fast: int = Field(4096, description="Max tokens for fast model (planner)")
    max_tokens_reasoning: int = Field(8192, description="Max tokens for reasoning model (analyst)")
    max_tokens_vision: int = Field(8192, description="Max tokens for vision model (screenshots)")

    # LLM behavior
    llm_temperature: float = Field(1.0, description="LLM temperature (must be 1.0 for reasoning)")
    reasoning_budget: int = Field(2048, description="Reasoning token budget for extended thinking")

    # Observability
    enable_langsmith: bool = Field(True, description="Enable LangSmith tracing")
    enable_pii_redaction: bool = Field(True, description="Enable PII redaction in logs")
    log_level: str = Field("INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR")

    @model_validator(mode='after')
    def validate_reasoning_temperature(self):
        """Enforce temperature=1.0 when reasoning is enabled.

        Following langchain-experimental pattern: Extended reasoning (thinking)
        requires temperature=1.0 for optimal performance.

        Raises:
            ValueError: If reasoning budget > 0 and temperature != 1.0
        """
        if self.reasoning_budget > 0 and self.llm_temperature != 1.0:
            raise ValueError(
                f"Extended reasoning requires temperature=1.0, got {self.llm_temperature}"
            )
        return self

    @model_validator(mode='after')
    def validate_vision_model(self):
        """Ensure vision model is vision-capable.

        Only Sonnet models support multimodal (text + images) inputs.
        Haiku models do not support vision and will fail if used for screenshots.

        Raises:
            ValueError: If model_vision is not in allowed vision-capable models
        """
        VISION_CAPABLE_MODELS = [
            "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            "us.anthropic.claude-3-sonnet-20240229-v1:0",
        ]

        if self.model_vision not in VISION_CAPABLE_MODELS:
            raise ValueError(
                f"model_vision '{self.model_vision}' is not vision-capable. "
                f"Allowed models: {VISION_CAPABLE_MODELS}. "
                f"Screenshots require Sonnet models - Haiku does not support multimodal inputs."
            )
        return self

    model_config = ConfigDict(extra="forbid")  # Strict - no extra fields allowed
