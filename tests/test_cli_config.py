"""Tests for CLI configuration module"""

import os
import pytest
from claude_scraper.cli.config import Config


def test_bedrock_config_defaults():
    """Test Bedrock configuration with default values (DEPRECATED)"""
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        config = Config.from_env("bedrock")
        # Should get deprecation warning
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "deprecated" in str(w[0].message).lower()

    assert config.provider == "bedrock"
    assert config.model_id == "anthropic.claude-3-5-sonnet-20240620-v1:0"
    assert config.region == "us-west-2"
    assert config.api_key is None


def test_bedrock_config_custom_env(monkeypatch):
    """Test Bedrock configuration with custom environment variables"""
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-opus-4-5-20251101-v1:0")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    config = Config.from_env("bedrock")
    assert config.provider == "bedrock"
    assert config.model_id == "anthropic.claude-opus-4-5-20251101-v1:0"
    assert config.region == "us-east-1"
    assert config.api_key is None


def test_default_provider_is_anthropic(monkeypatch):
    """Test that Anthropic is now the default provider"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-123")

    # Call without specifying provider - should default to Anthropic
    config = Config.from_env()
    assert config.provider == "anthropic"
    assert config.model_id == "claude-sonnet-4-5-20250929"
    assert config.region is None
    assert config.api_key == "sk-ant-test-key-123"


def test_anthropic_config_with_api_key(monkeypatch):
    """Test Anthropic configuration with API key"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-123")

    config = Config.from_env("anthropic")
    assert config.provider == "anthropic"
    assert config.model_id == "claude-sonnet-4-5-20250929"
    assert config.region is None
    assert config.api_key == "sk-ant-test-key-123"


def test_anthropic_config_missing_api_key(monkeypatch):
    """Test Anthropic configuration fails without API key"""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ValueError) as excinfo:
        Config.from_env("anthropic")

    assert "ANTHROPIC_API_KEY" in str(excinfo.value)


def test_invalid_provider():
    """Test configuration fails with invalid provider"""
    with pytest.raises(ValueError) as excinfo:
        Config.from_env("invalid")  # type: ignore[arg-type]  # Testing invalid input

    assert "Unknown provider" in str(excinfo.value)
    assert "bedrock" in str(excinfo.value)
    assert "anthropic" in str(excinfo.value)


def test_config_immutable():
    """Test that config is immutable (frozen dataclass)"""
    config = Config.from_env("bedrock")

    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        config.provider = "anthropic"  # type: ignore


def test_bedrock_invalid_model_id(monkeypatch):
    """Test Bedrock configuration fails with invalid model_id prefix"""
    monkeypatch.setenv("BEDROCK_MODEL_ID", "invalid-model-id")

    with pytest.raises(ValueError) as excinfo:
        Config.from_env("bedrock")

    assert "Invalid Bedrock model_id" in str(excinfo.value)
    assert "anthropic.claude-" in str(excinfo.value)


def test_anthropic_invalid_api_key_format(monkeypatch):
    """Test Anthropic configuration fails with invalid API key format"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "invalid-key-format")

    with pytest.raises(ValueError) as excinfo:
        Config.from_env("anthropic")

    assert "Invalid ANTHROPIC_API_KEY format" in str(excinfo.value)
    assert "sk-ant-" in str(excinfo.value)
