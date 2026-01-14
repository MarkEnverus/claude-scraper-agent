"""Unit tests for prompt generation functions."""

import pytest
from agentic_scraper.prompts.scraper_generator import (
    generate_collect_content_prompt,
    generate_validate_content_prompt,
    generate_complex_auth_prompt
)


def test_generate_collect_content_prompt():
    """Test collect_content prompt generation."""
    prompt = generate_collect_content_prompt(
        ba_spec_json='{"source": "test"}',
        endpoint="https://api.example.com/data",
        auth_method="API_KEY",
        data_format="JSON",
        timeout_seconds=30,
        retry_attempts=3
    )

    # Verify prompt contains all expected elements
    assert "collect_content" in prompt
    assert "API_KEY" in prompt
    assert "30" in prompt or "30 seconds" in prompt
    assert "3" in prompt or "3 attempts" in prompt
    assert "https://api.example.com/data" in prompt
    assert "JSON" in prompt
    assert "METHOD BODY ONLY" in prompt
    assert "BA Specification" in prompt
    assert "requests" in prompt
    assert "retry" in prompt.lower()


def test_generate_validate_content_prompt():
    """Test validate_content prompt generation."""
    prompt = generate_validate_content_prompt(
        ba_spec_json='{"source": "test"}',
        endpoint="https://api.example.com/data",
        data_format="JSON",
        validation_requirements='{"required_fields": ["id", "name"]}'
    )

    # Verify prompt contains all expected elements
    assert "validate_content" in prompt
    assert "JSON" in prompt
    assert "https://api.example.com/data" in prompt
    assert '{"required_fields": ["id", "name"]}' in prompt
    assert "METHOD BODY ONLY" in prompt
    assert "BA Specification" in prompt
    assert "validation" in prompt.lower()
    assert "ValueError" in prompt


def test_generate_complex_auth_prompt():
    """Test complex auth prompt generation."""
    prompt = generate_complex_auth_prompt(
        auth_spec='{"type": "OAUTH", "scopes": ["read"]}',
        auth_method="OAUTH",
        registration_url="https://oauth.example.com"
    )

    # Verify prompt contains all expected elements
    assert "OAUTH" in prompt
    assert "__init__" in prompt
    assert "https://oauth.example.com" in prompt
    assert '{"type": "OAUTH", "scopes": ["read"]}' in prompt
    assert "authentication" in prompt.lower()
    assert "environment" in prompt.lower()


def test_generate_collect_content_prompt_with_bearer_token():
    """Test collect_content prompt with BEARER_TOKEN auth."""
    prompt = generate_collect_content_prompt(
        ba_spec_json='{"source": "test_api"}',
        endpoint="https://api.example.com/v2/data",
        auth_method="BEARER_TOKEN",
        data_format="XML",
        timeout_seconds=60,
        retry_attempts=5
    )

    assert "BEARER_TOKEN" in prompt
    assert "60" in prompt or "60 seconds" in prompt
    assert "5" in prompt or "5 attempts" in prompt
    assert "XML" in prompt


def test_generate_validate_content_prompt_with_csv():
    """Test validate_content prompt with CSV format."""
    prompt = generate_validate_content_prompt(
        ba_spec_json='{"source": "csv_source"}',
        endpoint="https://data.example.com/export.csv",
        data_format="CSV",
        validation_requirements='{"min_rows": 10}'
    )

    assert "CSV" in prompt
    assert '{"min_rows": 10}' in prompt


def test_generate_complex_auth_prompt_no_registration_url():
    """Test complex auth prompt without registration URL."""
    prompt = generate_complex_auth_prompt(
        auth_spec='{"type": "SAML"}',
        auth_method="SAML",
        registration_url=""
    )

    assert "SAML" in prompt
    assert "N/A" in prompt or "registration_url" in prompt.lower()


def test_prompt_functions_return_strings():
    """Test that all prompt functions return non-empty strings."""
    prompt1 = generate_collect_content_prompt(
        ba_spec_json='{}',
        endpoint="http://test",
        auth_method="NONE",
        data_format="JSON",
        timeout_seconds=10,
        retry_attempts=1
    )
    assert isinstance(prompt1, str)
    assert len(prompt1) > 100  # Should be substantial

    prompt2 = generate_validate_content_prompt(
        ba_spec_json='{}',
        endpoint="http://test",
        data_format="JSON",
        validation_requirements='{}'
    )
    assert isinstance(prompt2, str)
    assert len(prompt2) > 100

    prompt3 = generate_complex_auth_prompt(
        auth_spec='{}',
        auth_method="OAUTH"
    )
    assert isinstance(prompt3, str)
    assert len(prompt3) > 100
