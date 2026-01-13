"""LLM factory for creating Bedrock ChatBedrockConverse instances.

This module provides a unified factory for all LLM creation with role-based
model selection (fast, reasoning, vision) and capability validation.

Single LLM Stack Architecture:
- Only ChatBedrockConverse used for all LLM calls (text, structured, vision)
- Three model roles: fast (planner), reasoning (analysis), vision (screenshots)
- Strict vision validation: raises ValueError if non-vision model used for vision

Example:
    >>> from agentic_scraper.business_analyst.config import BAConfig
    >>> config = BAConfig()
    >>> factory = LLMFactory(config=config)
    >>>
    >>> # Create models for different roles
    >>> fast_model = factory.create_fast_model()      # Haiku, no extended thinking
    >>> reasoning_model = factory.create_reasoning_model()  # Haiku with extended thinking
    >>> vision_model = factory.create_vision_model()  # Sonnet, vision-capable
    >>>
    >>> # Use helper methods for invocation
    >>> text_response = factory.invoke_text(fast_model, "Analyze this URL")
    >>> structured = factory.invoke_structured(reasoning_model, "Extract data", MySchema)
    >>> vision_result = factory.invoke_structured_with_vision(
    ...     vision_model, "What's in this image?", ["screenshot.png"], MySchema
    ... )
"""

import base64
import logging
import os
from typing import Type, TypeVar, Optional, List

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class LLMFactory:
    """Factory for creating Bedrock ChatBedrockConverse instances with role-based models.

    Single entry point for all LLM creation. Enforces three model roles:
    1. Fast/cheap: Planner, navigation, link rerank (Haiku, no extended thinking)
    2. Deep reasoning: Analysis extraction, Phase0/Phase1 (Haiku with extended thinking)
    3. Vision: Screenshot analysis (Sonnet, vision-capable, validated)

    Vision capability is strictly enforced:
    - create_vision_model() validates model is vision-capable
    - invoke_structured_with_vision() validates at invocation time
    - Non-vision models raise ValueError immediately (fail fast)

    Attributes:
        config: BAConfig instance with model selection and settings
        region: AWS region for Bedrock API

    Example:
        >>> config = BAConfig(
        ...     model_fast="us.anthropic.claude-3-5-haiku-20241022-v1:0",
        ...     model_reasoning="us.anthropic.claude-3-5-haiku-20241022-v1:0",
        ...     model_vision="us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        ... )
        >>> factory = LLMFactory(config=config, region="us-east-1")
        >>>
        >>> # Create models
        >>> planner_model = factory.create_fast_model()
        >>> analyst_model = factory.create_reasoning_model()
        >>> vision_model = factory.create_vision_model()  # Validates Sonnet
    """

    # Vision-capable models (only these can be used for screenshots)
    VISION_CAPABLE_MODELS = [
        "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        "us.anthropic.claude-3-sonnet-20240229-v1:0",
    ]

    def __init__(self, config, region: str = "us-east-1"):
        """Initialize factory with config and region.

        Args:
            config: BAConfig instance with model selection
            region: AWS region for Bedrock (defaults to us-east-1)
        """
        self.config = config
        self.region = region

        logger.debug(
            f"LLMFactory initialized with region={region}, "
            f"fast={config.model_fast}, "
            f"reasoning={config.model_reasoning}, "
            f"vision={config.model_vision}"
        )

    # ============================================================================
    # Model Creation Methods (returns ChatBedrockConverse instances)
    # ============================================================================

    def create_fast_model(self) -> ChatBedrockConverse:
        """Create fast/cheap model for planner and navigation (Haiku, no extended thinking).

        Use this for:
        - BA Planner (planner_react node)
        - Link prioritization and reranking
        - Quick navigation decisions
        - URL categorization

        Returns:
            ChatBedrockConverse: Haiku model without extended thinking

        Example:
            >>> factory = LLMFactory(config)
            >>> planner_model = factory.create_fast_model()
            >>> # Use with create_react_agent for tool binding
        """
        logger.info(
            f"Creating fast model: {self.config.model_fast} "
            f"(max_tokens={self.config.max_tokens_fast})"
        )

        return ChatBedrockConverse(
            model=self.config.model_fast,
            region_name=self.region,
            temperature=self.config.llm_temperature,
            max_tokens=self.config.max_tokens_fast,
            # No extended thinking for fast model (cost-effective)
        )

    def create_reasoning_model(self) -> ChatBedrockConverse:
        """Create deep reasoning model for analysis (Haiku with extended thinking).

        Use this for:
        - BA Analyst (Phase 0, Phase 1 text-only analysis)
        - Endpoint extraction and documentation parsing
        - Data type inference and schema analysis
        - Code generation (generators, orchestrator)

        Extended thinking provides deeper analysis quality while keeping costs
        reasonable by using Haiku.

        Returns:
            ChatBedrockConverse: Haiku model with extended thinking enabled

        Example:
            >>> factory = LLMFactory(config)
            >>> analyst_model = factory.create_reasoning_model()
            >>> # Use with .with_structured_output() for Pydantic schemas
        """
        logger.info(
            f"Creating reasoning model: {self.config.model_reasoning} "
            f"(max_tokens={self.config.max_tokens_reasoning}, "
            f"reasoning_budget={self.config.reasoning_budget})"
        )

        # Extended thinking configuration
        # DISABLED: Bedrock currently rejects reasoningConfig with ValidationException
        # "extraneous key [reasoningConfig] is not permitted"
        # Fail-safe approach: Do not send reasoningConfig until Bedrock support confirmed
        additional_fields = {}
        # if self.config.reasoning_budget > 0:
        #     additional_fields["reasoningConfig"] = {
        #         "type": "enabled",
        #         "maxReasoningEffort": "medium"  # low, medium, high
        #     }

        return ChatBedrockConverse(
            model=self.config.model_reasoning,
            region_name=self.region,
            temperature=self.config.llm_temperature,
            max_tokens=self.config.max_tokens_reasoning,
            additional_model_request_fields=additional_fields,
        )

    def create_vision_model(self) -> ChatBedrockConverse:
        """Create vision-capable model for screenshots (Sonnet, validated).

        Use this for:
        - BA Analyst Phase 0 with screenshots
        - Visual analysis of API documentation, portals, dashboards
        - Screenshot-based operation discovery

        Validates that configured model is vision-capable before creating.
        Only Sonnet models support multimodal (text + images) inputs.

        Returns:
            ChatBedrockConverse: Sonnet model for vision analysis

        Raises:
            ValueError: If model_vision is not in VISION_CAPABLE_MODELS

        Example:
            >>> factory = LLMFactory(config)
            >>> vision_model = factory.create_vision_model()  # Validates Sonnet
            >>> # Use with invoke_structured_with_vision()
        """
        self._assert_vision_capable(self.config.model_vision)

        logger.info(
            f"Creating vision model: {self.config.model_vision} "
            f"(max_tokens={self.config.max_tokens_vision})"
        )

        return ChatBedrockConverse(
            model=self.config.model_vision,
            region_name=self.region,
            temperature=self.config.llm_temperature,
            max_tokens=self.config.max_tokens_vision,
            # No extended thinking for vision (not supported on Sonnet yet)
        )

    # ============================================================================
    # Helper Methods for Invocation (reduce callsite complexity)
    # ============================================================================

    def invoke_text(
        self,
        model: ChatBedrockConverse,
        prompt: str,
        system: Optional[str] = None
    ) -> str:
        """Invoke model for text response.

        Simple text generation without structured output. Useful for:
        - Executive summaries
        - Natural language responses
        - Unstructured analysis

        Args:
            model: ChatBedrockConverse instance (from create_*_model())
            prompt: User prompt text
            system: Optional system prompt for instructions

        Returns:
            str: Model's text response

        Example:
            >>> factory = LLMFactory(config)
            >>> fast_model = factory.create_fast_model()
            >>> response = factory.invoke_text(
            ...     fast_model,
            ...     "Summarize these URLs",
            ...     system="You are a web analyst"
            ... )
        """
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))

        logger.debug(
            f"Invoking model for text response (prompt_length={len(prompt)})"
        )

        response = model.invoke(messages)

        # Extract text from AIMessage
        if hasattr(response, 'content'):
            return response.content
        return str(response)

    def invoke_structured(
        self,
        model: ChatBedrockConverse,
        prompt: str,
        schema: Type[T],
        system: Optional[str] = None
    ) -> T:
        """Invoke model for structured output matching Pydantic schema.

        Uses LangChain's with_structured_output() to enforce schema compliance.

        Args:
            model: ChatBedrockConverse instance (from create_*_model())
            prompt: User prompt text
            schema: Pydantic BaseModel class defining expected structure
            system: Optional system prompt for instructions

        Returns:
            T: Validated Pydantic model instance

        Raises:
            pydantic.ValidationError: If response doesn't match schema

        Example:
            >>> from pydantic import BaseModel
            >>> class Phase0Detection(BaseModel):
            ...     detected_type: str
            ...     discovered_endpoint_urls: list[str]
            >>>
            >>> factory = LLMFactory(config)
            >>> reasoning_model = factory.create_reasoning_model()
            >>> result = factory.invoke_structured(
            ...     reasoning_model,
            ...     "Analyze this API documentation",
            ...     Phase0Detection,
            ...     system="You are a business analyst"
            ... )
        """
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))

        logger.debug(
            f"Invoking model for structured output "
            f"(schema={schema.__name__}, prompt_length={len(prompt)})"
        )

        # Apply structured output schema
        structured_model = model.with_structured_output(schema)

        # Invoke and validate
        result = structured_model.invoke(messages)

        logger.info(
            f"Successfully invoked structured output (schema={schema.__name__})"
        )

        return result

    def invoke_structured_with_vision(
        self,
        model: ChatBedrockConverse,
        prompt: str,
        images: List[str],
        schema: Type[T],
        system: Optional[str] = None
    ) -> T:
        """Invoke vision model with images for structured output.

        Validates that model is vision-capable before invoking (fail fast).
        Loads images, encodes to base64, and sends with prompt.

        Args:
            model: ChatBedrockConverse instance (must be vision-capable)
            prompt: User prompt text
            images: List of image file paths (screenshots)
            schema: Pydantic BaseModel class defining expected structure
            system: Optional system prompt for instructions

        Returns:
            T: Validated Pydantic model instance

        Raises:
            ValueError: If model is not vision-capable
            FileNotFoundError: If image file doesn't exist
            pydantic.ValidationError: If response doesn't match schema

        Example:
            >>> factory = LLMFactory(config)
            >>> vision_model = factory.create_vision_model()
            >>> result = factory.invoke_structured_with_vision(
            ...     vision_model,
            ...     "What operations are shown in this API portal?",
            ...     ["/path/to/screenshot.png"],
            ...     Phase0Detection,
            ...     system="You are analyzing API documentation visually"
            ... )
        """
        # Validate model is vision-capable
        self._assert_vision_capable(model.model_id)

        # Validate inputs
        if not prompt:
            raise ValueError("prompt cannot be empty")
        if not images:
            raise ValueError("images list cannot be empty")
        if not schema:
            raise ValueError("schema cannot be None")

        # Load and encode images
        image_blocks = []
        for img_path in images:
            if not os.path.exists(img_path):
                raise FileNotFoundError(f"Image file not found: {img_path}")

            # Validate file size before encoding
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

        logger.debug(
            f"Invoking vision model with structured output "
            f"(schema={schema.__name__}, num_images={len(images)}, "
            f"prompt_length={len(prompt)})"
        )

        # Apply structured output schema
        structured_model = model.with_structured_output(schema)

        # Build message content: images first, then text
        content_blocks = [
            *image_blocks,
            {"type": "text", "text": prompt}
        ]

        # Create messages list
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=content_blocks))

        # Invoke model - LangChain handles retries and validation
        result = structured_model.invoke(messages)

        logger.info(
            f"Successfully invoked vision model with structured output "
            f"(schema={schema.__name__}, num_images={len(images)})"
        )

        return result

    # ============================================================================
    # Validation
    # ============================================================================

    def _assert_vision_capable(self, model_id: str):
        """Validate that model supports vision (multimodal inputs).

        Raises ValueError if model is not in VISION_CAPABLE_MODELS allowlist.
        This prevents silent failures when trying to use non-vision models
        for screenshot analysis.

        Args:
            model_id: Bedrock model ID to validate

        Raises:
            ValueError: If model_id not in VISION_CAPABLE_MODELS

        Example:
            >>> factory = LLMFactory(config)
            >>> factory._assert_vision_capable("us.anthropic.claude-3-5-haiku-20241022-v1:0")
            # ValueError: Model is not vision-capable
        """
        if model_id not in self.VISION_CAPABLE_MODELS:
            raise ValueError(
                f"Model '{model_id}' is not vision-capable. "
                f"Vision requires one of: {self.VISION_CAPABLE_MODELS}. "
                f"Screenshots require Sonnet models - Haiku does not support multimodal inputs."
            )


# Export public API
__all__ = [
    "LLMFactory",
]
