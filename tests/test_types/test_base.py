"""Tests for base models."""

import pytest
from datetime import datetime

from claude_scraper.types.base import ValidationResult, Metadata, BaseScraperConfig


def test_validation_result_valid() -> None:
    """Test ValidationResult with valid state."""
    result = ValidationResult(is_valid=True, errors=[], warnings=[])

    assert result.is_valid is True
    assert len(result.errors) == 0
    assert len(result.warnings) == 0


def test_validation_result_with_errors() -> None:
    """Test ValidationResult with errors."""
    result = ValidationResult(
        is_valid=False, errors=["Error 1", "Error 2"], warnings=["Warning 1"]
    )

    assert result.is_valid is False
    assert len(result.errors) == 2
    assert "Error 1" in result.errors
    assert "Error 2" in result.errors
    assert len(result.warnings) == 1
    assert "Warning 1" in result.warnings


def test_validation_result_immutable() -> None:
    """Test that ValidationResult is immutable."""
    result = ValidationResult(is_valid=True, errors=[], warnings=[])

    with pytest.raises(Exception):  # ValidationError or AttributeError
        result.is_valid = False  # type: ignore


def test_metadata_creation() -> None:
    """Test Metadata model creation."""
    today = datetime.now().strftime("%Y-%m-%d")

    metadata = Metadata(
        scraper_version="1.11.0",
        infrastructure_version="1.11.0",
        generated_date=today,
        last_updated=today,
        generator_agent="scraper-generator:http-collector",
    )

    assert metadata.scraper_version == "1.11.0"
    assert metadata.infrastructure_version == "1.11.0"
    assert metadata.generated_date == today
    assert metadata.last_updated == today
    assert metadata.generator_agent == "scraper-generator:http-collector"


def test_metadata_mutable() -> None:
    """Test that Metadata is mutable (for updates)."""
    today = datetime.now().strftime("%Y-%m-%d")

    metadata = Metadata(
        scraper_version="1.11.0",
        infrastructure_version="1.11.0",
        generated_date=today,
        last_updated=today,
        generator_agent="test",
    )

    # Should be able to update last_updated
    new_date = "2025-12-20"
    metadata.last_updated = new_date
    assert metadata.last_updated == new_date


def test_metadata_serialization() -> None:
    """Test Metadata JSON serialization."""
    today = datetime.now().strftime("%Y-%m-%d")

    metadata = Metadata(
        scraper_version="1.11.0",
        infrastructure_version="1.11.0",
        generated_date=today,
        last_updated=today,
        generator_agent="test",
    )

    # Serialize to JSON
    json_str = metadata.model_dump_json()
    assert isinstance(json_str, str)
    assert "1.11.0" in json_str

    # Deserialize from JSON
    loaded = Metadata.model_validate_json(json_str)
    assert loaded.scraper_version == metadata.scraper_version
    assert loaded.generator_agent == metadata.generator_agent


def test_base_scraper_config_abstract() -> None:
    """Test that BaseScraperConfig cannot be instantiated directly."""
    # BaseScraperConfig is abstract and should not be instantiable
    with pytest.raises(TypeError):
        BaseScraperConfig(  # type: ignore
            data_source="TEST",
            data_type="test",
            update_frequency="hourly",
            historical_support=False,
            authentication="None",
        )


def test_base_scraper_config_subclass() -> None:
    """Test that BaseScraperConfig can be subclassed."""

    class TestConfig(BaseScraperConfig):
        """Test config implementation."""

        def validate_config(self) -> ValidationResult:
            """Validate test config."""
            return ValidationResult(is_valid=True, errors=[], warnings=[])

    config = TestConfig(
        data_source="TEST",
        data_type="test_data",
        update_frequency="hourly",
        historical_support=True,
        authentication="API Key",
    )

    assert config.data_source == "TEST"
    assert config.data_type == "test_data"
    assert config.update_frequency == "hourly"
    assert config.historical_support is True
    assert config.authentication == "API Key"

    # Test validate_config works
    result = config.validate_config()
    assert result.is_valid is True


def test_base_scraper_config_validation() -> None:
    """Test BaseScraperConfig field validation."""

    class TestConfig(BaseScraperConfig):
        """Test config implementation."""

        def validate_config(self) -> ValidationResult:
            """Validate test config."""
            return ValidationResult(is_valid=True, errors=[], warnings=[])

    # Empty data_source should fail (min_length=1)
    with pytest.raises(Exception):  # ValidationError
        TestConfig(
            data_source="",  # Empty string
            data_type="test",
            update_frequency="hourly",
        )

    # Empty data_type should fail (min_length=1)
    with pytest.raises(Exception):  # ValidationError
        TestConfig(
            data_source="TEST",
            data_type="",  # Empty string
            update_frequency="hourly",
        )
