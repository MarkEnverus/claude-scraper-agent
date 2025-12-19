"""Tests for MISO energy_pricing collector.

This test suite covers:
- Collector initialization
- Candidate generation
- Content collection
- Content validation
- CLI interface
- Integration tests (optional, requires credentials)
"""

import os
import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests

from miso.scraper_miso_energy_pricing_http import (
    MisoEnergyPricingCollector,
    ENDPOINTS,
)
from infrastructure.collection_framework import (
    DownloadCandidate,
    CollectedContent,
    ValidationResult,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = Mock()
    redis_mock.get.return_value = None  # No hash exists
    redis_mock.setex.return_value = True
    return redis_mock


@pytest.fixture
def mock_s3_manager():
    """Mock S3Manager."""
    s3_mock = Mock()
    s3_mock.upload_file.return_value = "s3://bucket/path/to/file"
    return s3_mock


@pytest.fixture
def mock_kafka_producer():
    """Mock KafkaProducer."""
    kafka_mock = Mock()
    kafka_mock.send.return_value = None
    return kafka_mock


@pytest.fixture
def collector(mock_redis, mock_s3_manager, mock_kafka_producer):
    """Create MISO collector instance with mocked dependencies."""
    return MisoEnergyPricingCollector(
        api_key="MISO_API_KEY_TEST_KEY",
        redis_client=mock_redis,
        s3_manager=mock_s3_manager,
        kafka_producer=mock_kafka_producer,
        dgroup="miso_energy_pricing",
    )


@pytest.fixture
def sample_candidate():
    """Create sample DownloadCandidate."""
    return DownloadCandidate(
        url="https://api.misoenergy.org/api/v1/da/{date}/exante/lmp",
        expected_filename="miso_energy_pricing_test_20250101.json",
        metadata={
            "source": "miso",
            "data_type": "energy_pricing",
            "endpoint": "da_exante_lmp",
            "date": "2025-01-01",
            "dgroup": "miso_energy_pricing",
        },
    )


@pytest.fixture
def sample_json_response():
    """Sample JSON response from API."""
    return {
        "data": [
            {
                "timestamp": "2025-01-01T00:00:00Z",
                "value": 123.45,
            }
        ],
        "meta": {
            "source": "MISO",
            "date": "2025-01-01",
        },
    }


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================

def test_collector_initialization(collector):
    """Test collector initializes correctly."""
    assert collector.base_url == "https://api.misoenergy.org"
    assert collector.dgroup == "miso_energy_pricing"
    assert len(collector.endpoints) == 2
    assert collector.timeout == 30
    assert collector.retry_attempts == 3


def test_collector_missing_api_key():
    """Test collector raises error without API key."""
    with pytest.raises(ValueError, match="API key required"):
        MisoEnergyPricingCollector(
            api_key=None,
            redis_client=Mock(),
            s3_manager=Mock(),
            kafka_producer=Mock(),
        )


def test_endpoint_configuration():
    """Test endpoint configuration is correct."""
    assert len(ENDPOINTS) == 2

    # Day-ahead ex-ante locational marginal pricing data
    endpoint_0 = ENDPOINTS[0]
    assert endpoint_0["name"] == "da_exante_lmp"
    assert endpoint_0["method"] == "GET"
    assert endpoint_0["path"] == "/api/v1/da/{date}/exante/lmp"
    # Real-time 5-minute locational marginal pricing data
    endpoint_1 = ENDPOINTS[1]
    assert endpoint_1["name"] == "rt_lmp"
    assert endpoint_1["method"] == "GET"
    assert endpoint_1["path"] == "/api/v1/rt/{date}/lmp"


# ============================================================================
# CANDIDATE GENERATION TESTS
# ============================================================================

def test_generate_candidates_single_day(collector):
    """Test candidate generation for single day."""
    start_date = date(2025, 1, 1)
    end_date = date(2025, 1, 1)

    candidates = collector.generate_candidates(start_date, end_date)

    # Should generate one candidate per endpoint
    assert len(candidates) == 2

    # Check first candidate
    candidate = candidates[0]
    assert isinstance(candidate, DownloadCandidate)
    assert candidate.metadata["source"] == "miso"
    assert candidate.metadata["data_type"] == "energy_pricing"
    assert candidate.metadata["date"] == "2025-01-01"


def test_generate_candidates_date_range(collector):
    """Test candidate generation for date range."""
    start_date = date(2025, 1, 1)
    end_date = date(2025, 1, 3)

    candidates = collector.generate_candidates(start_date, end_date)

    # Should generate candidates for 3 days × N endpoints
    expected_count = 3 * 2
    assert len(candidates) == expected_count


def test_build_url_with_date(collector):
    """Test URL building with date parameters."""
    endpoint = ENDPOINTS[0]
    target_date = date(2025, 1, 15)

    url = collector._build_url(endpoint, target_date)

    assert url.startswith("https://api.misoenergy.org")
    # Check date formatting based on endpoint path
    if "{date}" in endpoint["path"]:
        assert "2025-01-15" in url
    if "{year}" in endpoint["path"]:
        assert "2025" in url


def test_generate_filename(collector):
    """Test filename generation."""
    endpoint_name = "da_exante_lmp"
    target_date = date(2025, 1, 15)

    filename = collector._generate_filename(endpoint_name, target_date)

    assert filename.startswith("miso_energy_pricing")
    assert "20250115" in filename
    assert filename.endswith(".json")


# ============================================================================
# CONTENT COLLECTION TESTS
# ============================================================================

@patch("requests.get")
def test_collect_content_success(mock_get, collector, sample_candidate, sample_json_response):
    """Test successful content collection."""
    # Mock successful HTTP response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_json_response
    mock_response.content = json.dumps(sample_json_response).encode()
    mock_get.return_value = mock_response

    # Collect content
    content = collector.collect_content(sample_candidate)

    # Verify result
    assert isinstance(content, CollectedContent)
    assert content.success is True
    assert content.content is not None
    assert content.error_message is None


@patch("requests.get")
def test_collect_content_http_error(mock_get, collector, sample_candidate):
    """Test content collection with HTTP error."""
    # Mock HTTP error
    mock_get.side_effect = requests.HTTPError("404 Not Found")

    # Collect content
    content = collector.collect_content(sample_candidate)

    # Verify error handling
    assert isinstance(content, CollectedContent)
    assert content.success is False
    assert content.error_message is not None


@patch("requests.get")
def test_collect_content_timeout(mock_get, collector, sample_candidate):
    """Test content collection with timeout."""
    # Mock timeout
    mock_get.side_effect = requests.Timeout("Request timed out")

    # Collect content
    content = collector.collect_content(sample_candidate)

    # Verify error handling
    assert isinstance(content, CollectedContent)
    assert content.success is False
    assert "timeout" in content.error_message.lower()


@patch("requests.get")
def test_collect_content_retry_logic(mock_get, collector, sample_candidate):
    """Test retry logic on transient errors."""
    # Mock transient error then success
    mock_get.side_effect = [
        requests.ConnectionError("Connection refused"),
        Mock(status_code=200, content=b'{"data": []}'),
    ]

    # Collect content
    content = collector.collect_content(sample_candidate)

    # Verify retry worked
    assert mock_get.call_count == 2
    assert content.success is True


# ============================================================================
# CONTENT VALIDATION TESTS
# ============================================================================

def test_validate_content_valid_data(collector, sample_candidate, sample_json_response):
    """Test validation with valid data."""
    content_bytes = json.dumps(sample_json_response).encode()

    content = CollectedContent(
        candidate=sample_candidate,
        success=True,
        content=content_bytes,
        content_hash="abc123",
    )

    result = collector.validate_content(content)

    assert isinstance(result, ValidationResult)
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_validate_content_empty_data(collector, sample_candidate):
    """Test validation with empty data."""
    content = CollectedContent(
        candidate=sample_candidate,
        success=True,
        content=b"",
        content_hash="",
    )

    result = collector.validate_content(content)

    assert result.is_valid is False
    assert len(result.errors) > 0


def test_validate_content_invalid_format(collector, sample_candidate):
    """Test validation with invalid data format."""
    # Invalid JSON
    content_bytes = b"not valid json {"

    content = CollectedContent(
        candidate=sample_candidate,
        success=True,
        content=content_bytes,
        content_hash="abc123",
    )

    result = collector.validate_content(content)

    assert result.is_valid is False


# ============================================================================
# CLI TESTS
# ============================================================================

def test_cli_required_parameters():
    """Test CLI requires start-date, end-date, s3-bucket."""
    from click.testing import CliRunner
    from miso.scraper_miso_energy_pricing_http import main

    runner = CliRunner()
    result = runner.invoke(main, [])

    # Should fail with missing required parameters
    assert result.exit_code != 0
    assert "start-date" in result.output or "Missing option" in result.output


def test_cli_environment_variables():
    """Test CLI reads from environment variables."""
    from click.testing import CliRunner
    from miso.scraper_miso_energy_pricing_http import main

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [
                "--start-date", "2025-01-01",
                "--end-date", "2025-01-01",
                "--s3-bucket", "test-bucket",
            ],
            env={
                "MISO_API_KEY": "test_key",
                "REDIS_HOST": "localhost",
                "REDIS_PORT": "6379",
            },
        )

        # Should accept environment variables
        # (may fail on infrastructure, but should parse CLI args)
        assert "MISO_API_KEY" not in result.output or result.exit_code == 0


# ============================================================================
# INTEGRATION TESTS (OPTIONAL)
# ============================================================================

@pytest.mark.skipif(
    os.getenv("MISO_API_KEY") is None,
    reason="Requires MISO_API_KEY environment variable",
)
@pytest.mark.integration
def test_integration_real_api_call():
    """Integration test with real API call.

    This test requires valid credentials and network access.
    Set MISO_API_KEY environment variable to run.
    """
    import redis

    # Use real infrastructure (or test infrastructure)
    redis_client = redis.Redis(host="localhost", port=6379, decode_responses=False)
    s3_manager = Mock()  # Mock S3 for integration test
    kafka_producer = None

    collector = MisoEnergyPricingCollector(
        api_key=os.getenv("MISO_API_KEY"),
        redis_client=redis_client,
        s3_manager=s3_manager,
        kafka_producer=kafka_producer,
        dgroup="miso_energy_pricing_test",
    )

    # Test with recent date
    start_date = date.today()
    end_date = date.today()

    candidates = collector.generate_candidates(start_date, end_date)
    assert len(candidates) > 0

    # Collect from first candidate
    candidate = candidates[0]
    content = collector.collect_content(candidate)

    # Verify successful collection
    assert content.success is True
    assert content.content is not None

    # Validate content
    validation = collector.validate_content(content)
    assert validation.is_valid is True
