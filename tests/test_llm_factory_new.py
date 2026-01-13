"""Unit tests for LLMFactory (agentic_scraper/llm/factory.py).

Tests the new unified LLM factory with role-based model selection and vision validation.
No network calls - all tests are pure unit tests with mocks.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pydantic import BaseModel, Field

from agentic_scraper.llm.factory import LLMFactory
from agentic_scraper.business_analyst.config import BAConfig


class TestSchema(BaseModel):
    """Test schema for structured output."""
    name: str = Field(..., description="Test name")
    count: int = Field(..., description="Test count")


class TestLLMFactoryInit:
    """Tests for LLMFactory initialization."""

    def test_init_with_defaults(self):
        """Test factory initialization with default region."""
        config = BAConfig()
        factory = LLMFactory(config=config)

        assert factory.config == config
        assert factory.region == "us-east-1"

    def test_init_with_custom_region(self):
        """Test factory initialization with custom region."""
        config = BAConfig()
        factory = LLMFactory(config=config, region="us-west-2")

        assert factory.config == config
        assert factory.region == "us-west-2"


class TestCreateFastModel:
    """Tests for create_fast_model method."""

    @patch("agentic_scraper.llm.factory.ChatBedrockConverse")
    def test_creates_haiku_without_reasoning(self, mock_chat_cls):
        """Test that fast model creates Haiku without extended thinking."""
        # Arrange
        config = BAConfig()
        factory = LLMFactory(config=config)
        mock_model = Mock()
        mock_chat_cls.return_value = mock_model

        # Act
        result = factory.create_fast_model()

        # Assert
        mock_chat_cls.assert_called_once_with(
            model="us.anthropic.claude-3-5-haiku-20241022-v1:0",
            region_name="us-east-1",
            temperature=1.0,
            max_tokens=4096,
        )
        assert result == mock_model

    @patch("agentic_scraper.llm.factory.ChatBedrockConverse")
    def test_uses_config_max_tokens(self, mock_chat_cls):
        """Test that fast model uses config max_tokens_fast."""
        # Arrange
        config = BAConfig(max_tokens_fast=2048)
        factory = LLMFactory(config=config)
        mock_model = Mock()
        mock_chat_cls.return_value = mock_model

        # Act
        factory.create_fast_model()

        # Assert
        call_kwargs = mock_chat_cls.call_args[1]
        assert call_kwargs["max_tokens"] == 2048


class TestCreateReasoningModel:
    """Tests for create_reasoning_model method."""

    @patch("agentic_scraper.llm.factory.ChatBedrockConverse")
    def test_creates_haiku_with_reasoning(self, mock_chat_cls):
        """Test that reasoning model creates Haiku with extended thinking."""
        # Arrange
        config = BAConfig(reasoning_budget=2048)
        factory = LLMFactory(config=config)
        mock_model = Mock()
        mock_chat_cls.return_value = mock_model

        # Act
        result = factory.create_reasoning_model()

        # Assert
        call_kwargs = mock_chat_cls.call_args[1]
        assert call_kwargs["model"] == "us.anthropic.claude-3-5-haiku-20241022-v1:0"
        assert call_kwargs["region_name"] == "us-east-1"
        assert call_kwargs["temperature"] == 1.0
        assert call_kwargs["max_tokens"] == 8192
        # Check extended thinking config
        assert "additional_model_request_fields" in call_kwargs
        reasoning_config = call_kwargs["additional_model_request_fields"]
        assert reasoning_config == {
            "reasoningConfig": {
                "type": "enabled",
                "maxReasoningEffort": "medium"
            }
        }
        assert result == mock_model

    @patch("agentic_scraper.llm.factory.ChatBedrockConverse")
    def test_no_reasoning_when_budget_zero(self, mock_chat_cls):
        """Test that reasoning model doesn't add config when budget is 0."""
        # Arrange
        config = BAConfig(reasoning_budget=0)
        factory = LLMFactory(config=config)
        mock_model = Mock()
        mock_chat_cls.return_value = mock_model

        # Act
        factory.create_reasoning_model()

        # Assert
        call_kwargs = mock_chat_cls.call_args[1]
        # Should have additional_model_request_fields but empty
        assert call_kwargs["additional_model_request_fields"] == {}


class TestCreateVisionModel:
    """Tests for create_vision_model method."""

    @patch("agentic_scraper.llm.factory.ChatBedrockConverse")
    def test_creates_sonnet_for_vision(self, mock_chat_cls):
        """Test that vision model creates Sonnet (vision-capable)."""
        # Arrange
        config = BAConfig()
        factory = LLMFactory(config=config)
        mock_model = Mock()
        mock_chat_cls.return_value = mock_model

        # Act
        result = factory.create_vision_model()

        # Assert
        mock_chat_cls.assert_called_once_with(
            model="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            region_name="us-east-1",
            temperature=1.0,
            max_tokens=8192,
        )
        assert result == mock_model

    def test_validates_vision_capable_model(self):
        """Test that vision model validates model is vision-capable."""
        # Arrange - Haiku is NOT vision-capable
        config = BAConfig(
            model_vision="us.anthropic.claude-3-5-haiku-20241022-v1:0"
        )
        factory = LLMFactory(config=config)

        # Act & Assert - Should raise ValueError during config validation
        # Note: This is caught by BAConfig.validate_vision_model() at config init
        with pytest.raises(ValueError, match="not vision-capable"):
            # Try to create config with invalid vision model
            BAConfig(model_vision="us.anthropic.claude-3-5-haiku-20241022-v1:0")


class TestInvokeText:
    """Tests for invoke_text method."""

    @patch("agentic_scraper.llm.factory.ChatBedrockConverse")
    def test_invoke_text_basic(self, mock_chat_cls):
        """Test basic text invocation."""
        # Arrange
        config = BAConfig()
        factory = LLMFactory(config=config)
        mock_model = Mock()
        mock_response = Mock()
        mock_response.content = "This is the response"
        mock_model.invoke.return_value = mock_response

        # Act
        result = factory.invoke_text(mock_model, "Test prompt")

        # Assert
        mock_model.invoke.assert_called_once()
        assert result == "This is the response"

    @patch("agentic_scraper.llm.factory.ChatBedrockConverse")
    def test_invoke_text_with_system(self, mock_chat_cls):
        """Test text invocation with system prompt."""
        # Arrange
        config = BAConfig()
        factory = LLMFactory(config=config)
        mock_model = Mock()
        mock_response = Mock()
        mock_response.content = "Response with system"
        mock_model.invoke.return_value = mock_response

        # Act
        result = factory.invoke_text(
            mock_model,
            "Test prompt",
            system="You are a test assistant"
        )

        # Assert
        mock_model.invoke.assert_called_once()
        # Check that messages include system prompt
        messages = mock_model.invoke.call_args[0][0]
        assert len(messages) == 2  # System + Human
        assert result == "Response with system"


class TestInvokeStructured:
    """Tests for invoke_structured method."""

    @patch("agentic_scraper.llm.factory.ChatBedrockConverse")
    def test_invoke_structured_basic(self, mock_chat_cls):
        """Test basic structured invocation."""
        # Arrange
        config = BAConfig()
        factory = LLMFactory(config=config)
        mock_model = Mock()
        mock_structured_model = Mock()
        mock_result = TestSchema(name="test", count=42)
        mock_model.with_structured_output.return_value = mock_structured_model
        mock_structured_model.invoke.return_value = mock_result

        # Act
        result = factory.invoke_structured(
            mock_model,
            "Extract data",
            TestSchema
        )

        # Assert
        mock_model.with_structured_output.assert_called_once_with(TestSchema)
        mock_structured_model.invoke.assert_called_once()
        assert result == mock_result

    @patch("agentic_scraper.llm.factory.ChatBedrockConverse")
    def test_invoke_structured_with_system(self, mock_chat_cls):
        """Test structured invocation with system prompt."""
        # Arrange
        config = BAConfig()
        factory = LLMFactory(config=config)
        mock_model = Mock()
        mock_structured_model = Mock()
        mock_result = TestSchema(name="test", count=10)
        mock_model.with_structured_output.return_value = mock_structured_model
        mock_structured_model.invoke.return_value = mock_result

        # Act
        result = factory.invoke_structured(
            mock_model,
            "Extract data",
            TestSchema,
            system="You are a data extractor"
        )

        # Assert
        mock_structured_model.invoke.assert_called_once()
        messages = mock_structured_model.invoke.call_args[0][0]
        assert len(messages) == 2  # System + Human
        assert result == mock_result


class TestInvokeStructuredWithVision:
    """Tests for invoke_structured_with_vision method."""

    @patch("agentic_scraper.llm.factory.os.path.exists")
    @patch("agentic_scraper.llm.factory.os.path.getsize")
    @patch("agentic_scraper.llm.factory.open")
    @patch("agentic_scraper.llm.factory.base64.b64encode")
    def test_invoke_vision_validates_model(
        self, mock_b64, mock_open, mock_getsize, mock_exists
    ):
        """Test that vision invocation validates model is vision-capable."""
        # Arrange
        config = BAConfig()
        factory = LLMFactory(config=config)

        # Create Haiku model (NOT vision-capable)
        mock_haiku_model = Mock()
        mock_haiku_model.model = "us.anthropic.claude-3-5-haiku-20241022-v1:0"

        mock_exists.return_value = True
        mock_getsize.return_value = 1024  # 1KB

        # Act & Assert
        with pytest.raises(ValueError, match="not vision-capable"):
            factory.invoke_structured_with_vision(
                mock_haiku_model,
                "What's in this image?",
                ["test.png"],
                TestSchema
            )

    @patch("agentic_scraper.llm.factory.os.path.exists")
    @patch("agentic_scraper.llm.factory.os.path.getsize")
    @patch("agentic_scraper.llm.factory.open")
    @patch("agentic_scraper.llm.factory.base64.b64encode")
    def test_invoke_vision_success(
        self, mock_b64, mock_open, mock_getsize, mock_exists
    ):
        """Test successful vision invocation with Sonnet."""
        # Arrange
        config = BAConfig()
        factory = LLMFactory(config=config)

        # Create Sonnet model (vision-capable)
        mock_sonnet_model = Mock()
        mock_sonnet_model.model = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

        mock_structured_model = Mock()
        mock_result = TestSchema(name="visual", count=5)
        mock_sonnet_model.with_structured_output.return_value = mock_structured_model
        mock_structured_model.invoke.return_value = mock_result

        mock_exists.return_value = True
        mock_getsize.return_value = 1024 * 1024  # 1MB
        mock_b64.return_value.decode.return_value = "base64_image_data"

        # Mock file read
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = b"fake_image_data"
        mock_open.return_value = mock_file

        # Act
        result = factory.invoke_structured_with_vision(
            mock_sonnet_model,
            "What's in this image?",
            ["test.png"],
            TestSchema
        )

        # Assert
        mock_sonnet_model.with_structured_output.assert_called_once_with(TestSchema)
        mock_structured_model.invoke.assert_called_once()
        assert result == mock_result

    @patch("agentic_scraper.llm.factory.os.path.exists")
    def test_invoke_vision_file_not_found(self, mock_exists):
        """Test that vision invocation raises FileNotFoundError for missing images."""
        # Arrange
        config = BAConfig()
        factory = LLMFactory(config=config)

        mock_sonnet_model = Mock()
        mock_sonnet_model.model = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

        mock_exists.return_value = False

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Image file not found"):
            factory.invoke_structured_with_vision(
                mock_sonnet_model,
                "What's in this image?",
                ["nonexistent.png"],
                TestSchema
            )

    @patch("agentic_scraper.llm.factory.os.path.exists")
    @patch("agentic_scraper.llm.factory.os.path.getsize")
    def test_invoke_vision_file_too_large(self, mock_getsize, mock_exists):
        """Test that vision invocation raises ValueError for oversized images."""
        # Arrange
        config = BAConfig()
        factory = LLMFactory(config=config)

        mock_sonnet_model = Mock()
        mock_sonnet_model.model = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

        mock_exists.return_value = True
        mock_getsize.return_value = 5 * 1024 * 1024  # 5MB (too large)

        # Act & Assert
        with pytest.raises(ValueError, match="Image file too large"):
            factory.invoke_structured_with_vision(
                mock_sonnet_model,
                "What's in this image?",
                ["huge.png"],
                TestSchema
            )


class TestAssertVisionCapable:
    """Tests for _assert_vision_capable validation method."""

    def test_sonnet_is_vision_capable(self):
        """Test that Sonnet passes vision validation."""
        # Arrange
        config = BAConfig()
        factory = LLMFactory(config=config)

        # Act & Assert - Should not raise
        factory._assert_vision_capable("us.anthropic.claude-3-5-sonnet-20241022-v2:0")

    def test_haiku_is_not_vision_capable(self):
        """Test that Haiku fails vision validation."""
        # Arrange
        config = BAConfig()
        factory = LLMFactory(config=config)

        # Act & Assert
        with pytest.raises(ValueError, match="not vision-capable"):
            factory._assert_vision_capable("us.anthropic.claude-3-5-haiku-20241022-v1:0")

    def test_unknown_model_is_not_vision_capable(self):
        """Test that unknown model fails vision validation."""
        # Arrange
        config = BAConfig()
        factory = LLMFactory(config=config)

        # Act & Assert
        with pytest.raises(ValueError, match="not vision-capable"):
            factory._assert_vision_capable("us.anthropic.claude-unknown-model")


class TestBAConfigValidation:
    """Tests for BAConfig vision model validation."""

    def test_config_validates_vision_model(self):
        """Test that BAConfig validates vision model at initialization."""
        # Act & Assert - Should raise during config creation
        with pytest.raises(ValueError, match="not vision-capable"):
            BAConfig(model_vision="us.anthropic.claude-3-5-haiku-20241022-v1:0")

    def test_config_allows_valid_vision_model(self):
        """Test that BAConfig allows valid Sonnet vision model."""
        # Act - Should not raise
        config = BAConfig(
            model_vision="us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        )

        # Assert
        assert config.model_vision == "us.anthropic.claude-3-5-sonnet-20241022-v2:0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
