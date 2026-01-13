"""Tests for LLM provider abstraction layer.

Tests basic functionality of Bedrock and Anthropic providers,
factory creation, and error handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from agentic_scraper.llm import (
    BedrockProvider,
    AnthropicProvider,
    create_llm_provider
)
from agentic_scraper.cli.config import Config


class TestBedrockProvider:
    """Test BedrockProvider adapter."""

    def test_init_validates_model_id(self):
        """Test that empty model_id raises ValueError."""
        with pytest.raises(ValueError, match="model_id cannot be empty"):
            BedrockProvider(model_id="", region="us-east-1")

    def test_init_validates_region(self):
        """Test that empty region raises ValueError."""
        with pytest.raises(ValueError, match="region cannot be empty"):
            BedrockProvider(model_id="test-model", region="")

    def test_init_validates_timeout(self):
        """Test that non-positive timeout raises ValueError."""
        with pytest.raises(ValueError, match="timeout must be positive"):
            BedrockProvider(model_id="test-model", region="us-east-1", timeout=0)
        with pytest.raises(ValueError, match="timeout must be positive"):
            BedrockProvider(model_id="test-model", region="us-east-1", timeout=-1)

    def test_invoke_validates_prompt(self):
        """Test that empty prompt raises ValueError."""
        provider = BedrockProvider()
        with pytest.raises(ValueError, match="prompt cannot be empty"):
            provider.invoke("")

    @patch('claude_scraper.llm.bedrock.boto3')
    def test_invoke_success(self, mock_boto3):
        """Test successful LLM invocation."""
        # Mock response
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = b'{"content": [{"text": "2+2=4"}]}'

        mock_client = MagicMock()
        mock_client.invoke_model.return_value = mock_response
        mock_boto3.client.return_value = mock_client

        provider = BedrockProvider(
            model_id="anthropic.claude-sonnet-4-5-v2:0",
            region="us-east-1"
        )

        response = provider.invoke("What is 2+2?")

        assert response == "2+2=4"
        mock_client.invoke_model.assert_called_once()

    @patch('claude_scraper.llm.bedrock.boto3')
    @patch('claude_scraper.llm.bedrock.time.sleep')
    def test_invoke_retry_on_throttling(self, mock_sleep, mock_boto3):
        """Test retry logic on throttling errors."""
        from botocore.exceptions import ClientError

        # First call throttles, second succeeds
        mock_response_success = {
            "body": MagicMock()
        }
        mock_response_success["body"].read.return_value = b'{"content": [{"text": "Success"}]}'

        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = [
            ClientError(
                {"Error": {"Code": "ThrottlingException"}},
                "invoke_model"
            ),
            mock_response_success
        ]
        mock_boto3.client.return_value = mock_client

        provider = BedrockProvider(max_retries=3, base_delay=0.1)
        response = provider.invoke("Test")

        assert response == "Success"
        assert mock_client.invoke_model.call_count == 2
        mock_sleep.assert_called_once()

    @patch('claude_scraper.llm.bedrock.boto3')
    @patch('claude_scraper.llm.bedrock.time.sleep')
    def test_invoke_exponential_backoff_timing(self, mock_sleep, mock_boto3):
        """Test that exponential backoff uses correct delays: 1s, 2s, 4s."""
        from botocore.exceptions import ClientError

        # Mock response for final success
        mock_response_success = {
            "body": MagicMock()
        }
        mock_response_success["body"].read.return_value = b'{"content": [{"text": "Success"}]}'

        # Fail 3 times, then succeed on 4th attempt
        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = [
            ClientError({"Error": {"Code": "ThrottlingException"}}, "invoke_model"),
            ClientError({"Error": {"Code": "ThrottlingException"}}, "invoke_model"),
            ClientError({"Error": {"Code": "ThrottlingException"}}, "invoke_model"),
            mock_response_success
        ]
        mock_boto3.client.return_value = mock_client

        provider = BedrockProvider(max_retries=4, base_delay=1.0)
        response = provider.invoke("Test")

        assert response == "Success"
        assert mock_client.invoke_model.call_count == 4

        # Verify exponential backoff: 1s, 2s, 4s
        assert mock_sleep.call_count == 3
        calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert calls == [1.0, 2.0, 4.0], f"Expected [1.0, 2.0, 4.0] but got {calls}"


class TestAnthropicProvider:
    """Test AnthropicProvider adapter."""

    def test_init_validates_model_id(self):
        """Test that empty model_id raises ValueError."""
        with pytest.raises(ValueError, match="model_id cannot be empty"):
            AnthropicProvider(model_id="", api_key="test-key")

    def test_init_validates_timeout(self):
        """Test that non-positive timeout raises ValueError."""
        with pytest.raises(ValueError, match="timeout must be positive"):
            AnthropicProvider(model_id="test-model", api_key="test-key", timeout=0)
        with pytest.raises(ValueError, match="timeout must be positive"):
            AnthropicProvider(model_id="test-model", api_key="test-key", timeout=-1)

    def test_invoke_validates_prompt(self):
        """Test that empty prompt raises ValueError."""
        with patch('claude_scraper.llm.anthropic.Anthropic'):
            provider = AnthropicProvider(api_key="test-key")
            with pytest.raises(ValueError, match="prompt cannot be empty"):
                provider.invoke("")

    @patch('claude_scraper.llm.anthropic.Anthropic')
    def test_invoke_success(self, mock_anthropic_class):
        """Test successful LLM invocation."""
        # Mock response
        mock_content = MagicMock()
        mock_content.text = "2+2=4"

        mock_response = MagicMock()
        mock_response.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(
            model_id="claude-sonnet-4-5-20251101",
            api_key="test-key"
        )

        response = provider.invoke("What is 2+2?")

        assert response == "2+2=4"
        mock_client.messages.create.assert_called_once()

    @patch('claude_scraper.llm.anthropic.Anthropic')
    @patch('claude_scraper.llm.anthropic.time.sleep')
    def test_invoke_retry_on_rate_limit(self, mock_sleep, mock_anthropic_class):
        """Test retry logic on rate limit errors."""
        from anthropic import RateLimitError

        # Create mock httpx response for rate limit error
        mock_response = MagicMock()
        mock_response.status_code = 429

        # First call rate limited, second succeeds
        mock_content = MagicMock()
        mock_content.text = "Success"
        mock_response_success = MagicMock()
        mock_response_success.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            RateLimitError("Rate limited", response=mock_response, body=None),
            mock_response_success
        ]
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(
            api_key="test-key",
            max_retries=3,
            base_delay=0.1
        )
        response = provider.invoke("Test")

        assert response == "Success"
        assert mock_client.messages.create.call_count == 2
        mock_sleep.assert_called_once()

    @patch('claude_scraper.llm.anthropic.Anthropic')
    @patch('claude_scraper.llm.anthropic.time.sleep')
    def test_invoke_exponential_backoff_timing(self, mock_sleep, mock_anthropic_class):
        """Test that exponential backoff uses correct delays: 1s, 2s, 4s."""
        from anthropic import RateLimitError

        # Create mock httpx response for rate limit error
        mock_response = MagicMock()
        mock_response.status_code = 429

        # Mock successful response
        mock_content = MagicMock()
        mock_content.text = "Success"
        mock_response_success = MagicMock()
        mock_response_success.content = [mock_content]

        # Fail 3 times, then succeed on 4th attempt
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            RateLimitError("Rate limited", response=mock_response, body=None),
            RateLimitError("Rate limited", response=mock_response, body=None),
            RateLimitError("Rate limited", response=mock_response, body=None),
            mock_response_success
        ]
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(
            api_key="test-key",
            max_retries=4,
            base_delay=1.0
        )
        response = provider.invoke("Test")

        assert response == "Success"
        assert mock_client.messages.create.call_count == 4

        # Verify exponential backoff: 1s, 2s, 4s
        assert mock_sleep.call_count == 3
        calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert calls == [1.0, 2.0, 4.0], f"Expected [1.0, 2.0, 4.0] but got {calls}"


class TestLLMFactory:
    """Test LLM provider factory."""

    @patch('claude_scraper.llm.bedrock.boto3')
    def test_create_bedrock_provider(self, mock_boto3):
        """Test factory creates Bedrock provider."""
        config = Config.from_env(provider="bedrock")
        provider = create_llm_provider("bedrock", config)

        assert isinstance(provider, BedrockProvider)
        assert provider.model_id == config.model_id
        assert provider.region == config.region

    @patch('claude_scraper.llm.anthropic.Anthropic')
    def test_create_anthropic_provider(self, mock_anthropic):
        """Test factory creates Anthropic provider."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'sk-ant-test-key-12345'}):
            config = Config.from_env(provider="anthropic")
            provider = create_llm_provider("anthropic", config)

            assert isinstance(provider, AnthropicProvider)
            assert provider.model_id == config.model_id

    def test_create_invalid_provider(self):
        """Test factory raises error for invalid provider."""
        # Create a config manually with invalid provider to bypass Config.from_env validation
        from dataclasses import replace

        with patch.dict('os.environ', {'AWS_REGION': 'us-east-1'}):
            config = Config.from_env(provider="bedrock")
            # Modify config to have invalid provider
            config = replace(config, provider="invalid")

            with pytest.raises(ValueError, match="Unknown provider: invalid"):
                create_llm_provider("invalid", config)
