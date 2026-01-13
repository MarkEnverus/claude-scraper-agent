"""Unit tests for LLM factory.

Tests the LLM creation and configuration utilities.
"""

import pytest
from unittest.mock import Mock, patch
from pydantic import BaseModel, Field

from agentic_scraper.business_analyst.llm_factory import (
    create_claude_with_reasoning,
    create_claude_from_config,
    with_structured_output,
    create_structured_llm,
)
from agentic_scraper.business_analyst.config import BAConfig
from agentic_scraper.llm.bedrock import BedrockProvider


class TestCreateClaudeWithReasoning:
    """Tests for create_claude_with_reasoning function."""

    @patch("claude_scraper.business_analyst.llm_factory.BedrockProvider")
    def test_default_parameters(self, mock_bedrock_cls):
        """Test LLM creation with default parameters."""
        # Arrange
        mock_llm = Mock()
        mock_bedrock_cls.return_value = mock_llm

        # Act
        result = create_claude_with_reasoning()

        # Assert
        mock_bedrock_cls.assert_called_once()
        call_kwargs = mock_bedrock_cls.call_args[1]
        # BedrockProvider should be created with model and region
        assert "model_id" in call_kwargs
        assert call_kwargs["region"] == "us-east-1"

    @patch("claude_scraper.business_analyst.llm_factory.BedrockProvider")
    def test_custom_parameters(self, mock_bedrock_cls):
        """Test LLM creation with custom parameters."""
        # Arrange
        mock_llm = Mock()
        mock_bedrock_cls.return_value = mock_llm

        # Act
        result = create_claude_with_reasoning(
            temperature=0.5,
            max_tokens=8192,
            reasoning_budget=4096,
            model="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            region="us-west-2"
        )

        # Assert
        call_kwargs = mock_bedrock_cls.call_args[1]
        assert call_kwargs["model_id"] == "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        assert call_kwargs["region"] == "us-west-2"

    @patch("claude_scraper.business_analyst.llm_factory.BedrockProvider")
    def test_returns_bedrock_instance(self, mock_bedrock_cls):
        """Test that function returns BedrockProvider instance."""
        # Arrange
        mock_llm = Mock(spec=BedrockProvider)
        mock_bedrock_cls.return_value = mock_llm

        # Act
        result = create_claude_with_reasoning()

        # Assert
        assert result == mock_llm


class TestCreateClaudeFromConfig:
    """Tests for create_claude_from_config function."""

    @patch("claude_scraper.business_analyst.llm_factory.BedrockProvider")
    def test_uses_config_parameters(self, mock_bedrock_cls):
        """Test that config parameters are properly used."""
        # Arrange
        mock_llm = Mock()
        mock_bedrock_cls.return_value = mock_llm

        config = BAConfig(
            llm_temperature=0.7,
            max_tokens_per_llm_call=6144,
            llm_reasoning_budget=3072,
            llm_model="us.anthropic.claude-3-5-haiku-20241022-v1:0"
        )

        # Act
        result = create_claude_from_config(config)

        # Assert
        call_kwargs = mock_bedrock_cls.call_args[1]
        assert call_kwargs["model_id"] == "us.anthropic.claude-3-5-haiku-20241022-v1:0"

    @patch("claude_scraper.business_analyst.llm_factory.BedrockProvider")
    def test_default_config(self, mock_bedrock_cls):
        """Test with default BAConfig."""
        # Arrange
        mock_llm = Mock()
        mock_bedrock_cls.return_value = mock_llm

        config = BAConfig()

        # Act
        result = create_claude_from_config(config)

        # Assert
        mock_bedrock_cls.assert_called_once()
        # Should use default config values
        call_kwargs = mock_bedrock_cls.call_args[1]
        assert call_kwargs["model_id"] == config.llm_model


class TestWithStructuredOutput:
    """Tests for with_structured_output function."""

    def test_structured_output_configuration(self):
        """Test structured output configuration."""
        # Arrange
        class TestSchema(BaseModel):
            name: str
            count: int

        mock_llm = Mock(spec=BedrockProvider)

        # Act
        result = with_structured_output(mock_llm, TestSchema)

        # Assert
        # BedrockProvider natively supports structured output, so it returns the same instance
        assert result == mock_llm

    def test_invalid_schema_raises_error(self):
        """Test that non-Pydantic schema raises ValueError."""
        # Arrange
        mock_llm = Mock(spec=BedrockProvider)

        # Act & Assert
        with pytest.raises(ValueError, match="must be a Pydantic BaseModel"):
            with_structured_output(mock_llm, dict)


class TestCreateStructuredLLM:
    """Tests for create_structured_llm function."""

    @patch("claude_scraper.business_analyst.llm_factory.BedrockProvider")
    def test_create_with_schema(self, mock_bedrock_cls):
        """Test creating structured LLM with schema."""
        # Arrange
        class TestSchema(BaseModel):
            result: str

        mock_llm = Mock(spec=BedrockProvider)
        mock_bedrock_cls.return_value = mock_llm

        # Act
        result = create_structured_llm(TestSchema)

        # Assert
        # Should return BedrockProvider instance
        assert result == mock_llm

    @patch("claude_scraper.business_analyst.llm_factory.BedrockProvider")
    def test_create_with_custom_parameters(self, mock_bedrock_cls):
        """Test creating structured LLM with custom parameters."""
        # Arrange
        class TestSchema(BaseModel):
            data: list[str]

        mock_llm = Mock(spec=BedrockProvider)
        mock_bedrock_cls.return_value = mock_llm

        # Act
        result = create_structured_llm(
            schema=TestSchema,
            temperature=0.3,
            max_tokens=2048,
            reasoning_budget=1024
        )

        # Assert
        call_kwargs = mock_bedrock_cls.call_args[1]
        # BedrockProvider is created with model and region
        assert "model_id" in call_kwargs

    @patch("claude_scraper.business_analyst.llm_factory.BedrockProvider")
    def test_create_with_config(self, mock_bedrock_cls):
        """Test creating structured LLM with BAConfig."""
        # Arrange
        class TestSchema(BaseModel):
            endpoints: list[str]

        mock_llm = Mock(spec=BedrockProvider)
        mock_bedrock_cls.return_value = mock_llm

        config = BAConfig(
            llm_temperature=0.9,
            max_tokens_per_llm_call=5000,
            llm_model="us.anthropic.claude-3-5-haiku-20241022-v1:0"
        )

        # Act
        result = create_structured_llm(TestSchema, config=config)

        # Assert
        call_kwargs = mock_bedrock_cls.call_args[1]
        assert call_kwargs["model_id"] == "us.anthropic.claude-3-5-haiku-20241022-v1:0"


class TestIntegration:
    """Integration tests for LLM factory."""

    @patch("claude_scraper.business_analyst.llm_factory.BedrockProvider")
    def test_end_to_end_structured_llm_creation(self, mock_bedrock_cls):
        """Test complete flow of creating a structured LLM."""
        # Arrange
        class EndpointSchema(BaseModel):
            url: str = Field(..., description="Endpoint URL")
            method: str = Field(..., description="HTTP method")

        mock_llm = Mock(spec=BedrockProvider)
        mock_bedrock_cls.return_value = mock_llm

        config = BAConfig()

        # Act
        # Create base LLM from config
        llm = create_claude_from_config(config)
        # Wrap with structured output (returns same instance for BedrockProvider)
        structured_llm = with_structured_output(llm, EndpointSchema)

        # Assert
        assert structured_llm == mock_llm

    @patch("claude_scraper.business_analyst.llm_factory.BedrockProvider")
    def test_convenience_function_equivalent(self, mock_bedrock_cls):
        """Test that convenience function is equivalent to manual flow."""
        # Arrange
        class TestSchema(BaseModel):
            value: int

        mock_llm = Mock(spec=BedrockProvider)
        mock_bedrock_cls.return_value = mock_llm

        # Act
        result = create_structured_llm(
            schema=TestSchema,
            temperature=0.8,
            max_tokens=3000
        )

        # Assert
        # Should create BedrockProvider with correct params
        call_kwargs = mock_bedrock_cls.call_args[1]
        assert "model_id" in call_kwargs
        assert result == mock_llm
