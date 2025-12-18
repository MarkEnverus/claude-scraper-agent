"""Tests for MISO Energy Pricing HTTP collector."""

import json
from datetime import datetime, date
from unittest.mock import Mock, patch, MagicMock

import pytest
import redis
import requests

from sourcing.scraping.miso.scraper_miso_energy_pricing_http import (
    MISOEnergyPricingCollector,
    MISO_ENDPOINTS
)
from sourcing.scraping.commons.collection_framework import DownloadCandidate
from sourcing.exceptions import ScrapingError


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    client = Mock(spec=redis.Redis)
    client.ping.return_value = True
    client.exists.return_value = 0
    client.setex.return_value = True
    client.get.return_value = None
    return client


@pytest.fixture
def collector(mock_redis):
    """Initialize collector with mocked dependencies."""
    return MISOEnergyPricingCollector(
        dgroup="miso_energy_pricing_test",
        s3_bucket="test-bucket",
        s3_prefix="sourcing",
        redis_client=mock_redis,
        environment="dev",
        api_key="test-api-key-12345",
        timeout=30
    )


@pytest.fixture
def sample_lmp_response():
    """Sample LMP API response."""
    return {
        "effectiveDate": "2025-01-15",
        "marketType": "DA",
        "dataType": "LMP",
        "locations": [
            {
                "locationId": "LOC1",
                "locationName": "Node 1",
                "hourlyData": [
                    {
                        "hour": 1,
                        "lmp": 25.50,
                        "mcc": 5.25,
                        "mlc": 20.25
                    },
                    {
                        "hour": 2,
                        "lmp": 26.75,
                        "mcc": 5.50,
                        "mlc": 21.25
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_mcp_response():
    """Sample MCP API response."""
    return {
        "effectiveDate": "2025-01-15",
        "marketType": "RT",
        "dataType": "MCP",
        "locations": [
            {
                "locationId": "LOC2",
                "locationName": "Hub 2",
                "intervalData": [
                    {
                        "timestamp": "2025-01-15T00:05:00Z",
                        "mcp": 3.25
                    },
                    {
                        "timestamp": "2025-01-15T00:10:00Z",
                        "mcp": 3.50
                    }
                ]
            }
        ]
    }


class TestMISOEnergyPricingCollector:
    """Test suite for MISOEnergyPricingCollector."""

    def test_initialization(self, mock_redis):
        """Test collector initialization."""
        collector = MISOEnergyPricingCollector(
            dgroup="miso_energy_pricing",
            s3_bucket="test-bucket",
            s3_prefix="sourcing",
            redis_client=mock_redis,
            environment="dev",
            api_key="test-key"
        )

        assert collector.dgroup == "miso_energy_pricing"
        assert collector.s3_bucket == "test-bucket"
        assert collector.api_key == "test-key"
        assert collector.base_url == "https://data-exchange.misoenergy.org"
        assert collector.timeout == 30
        assert "Ocp-Apim-Subscription-Key" in collector.session.headers
        assert collector.session.headers["Ocp-Apim-Subscription-Key"] == "test-key"

    def test_initialization_without_api_key(self, mock_redis):
        """Test initialization fails without API key."""
        with pytest.raises(ValueError, match="MISO API key is required"):
            MISOEnergyPricingCollector(
                dgroup="miso_test",
                s3_bucket="test-bucket",
                s3_prefix="sourcing",
                redis_client=mock_redis,
                environment="dev",
                api_key=""
            )

    def test_generate_candidates_single_day(self, collector):
        """Test candidate generation for a single day."""
        start_date = datetime(2025, 1, 15)
        end_date = datetime(2025, 1, 16)

        candidates = collector.generate_candidates(
            start_date=start_date,
            end_date=end_date
        )

        # Should generate 12 candidates (one per endpoint)
        assert len(candidates) == 12

        # Check first candidate (DA_EXANTE_LMP)
        first = candidates[0]
        assert isinstance(first, DownloadCandidate)
        assert first.identifier == "miso_da_exante_lmp_20250115.json"
        assert "https://data-exchange.misoenergy.org/api/v1/da/2025-01-15/exante/lmp" in first.source_location
        assert first.metadata["data_source"] == "miso"
        assert first.metadata["endpoint_name"] == "DA_EXANTE_LMP"
        assert first.metadata["market_type"] == "day-ahead"
        assert first.metadata["data_type"] == "lmp"
        assert first.metadata["timing"] == "ex-ante"
        assert first.metadata["date"] == "2025-01-15"
        assert first.file_date == date(2025, 1, 15)

        # Verify all 12 endpoints are represented
        endpoint_names = {c.metadata["endpoint_name"] for c in candidates}
        expected_names = {ep["name"] for ep in MISO_ENDPOINTS}
        assert endpoint_names == expected_names

    def test_generate_candidates_multiple_days(self, collector):
        """Test candidate generation for multiple days."""
        start_date = datetime(2025, 1, 15)
        end_date = datetime(2025, 1, 18)  # 3 days

        candidates = collector.generate_candidates(
            start_date=start_date,
            end_date=end_date
        )

        # Should generate 12 endpoints * 3 days = 36 candidates
        assert len(candidates) == 36

        # Check that all dates are represented
        dates = {c.file_date for c in candidates}
        assert dates == {
            date(2025, 1, 15),
            date(2025, 1, 16),
            date(2025, 1, 17)
        }

        # Check that each date has all 12 endpoints
        for test_date in dates:
            date_candidates = [c for c in candidates if c.file_date == test_date]
            assert len(date_candidates) == 12
            endpoint_names = {c.metadata["endpoint_name"] for c in date_candidates}
            assert len(endpoint_names) == 12

    def test_generate_candidates_date_formatting(self, collector):
        """Test that date formatting in URLs is correct."""
        start_date = datetime(2025, 1, 5)  # Single-digit day
        end_date = datetime(2025, 1, 6)

        candidates = collector.generate_candidates(
            start_date=start_date,
            end_date=end_date
        )

        # Check that date is formatted with leading zero
        first = candidates[0]
        assert "2025-01-05" in first.source_location
        assert first.identifier == "miso_da_exante_lmp_20250105.json"

    def test_collect_content_success(self, collector, sample_lmp_response):
        """Test successful content collection."""
        candidate = DownloadCandidate(
            identifier="miso_da_exante_lmp_20250115.json",
            source_location="https://data-exchange.misoenergy.org/api/v1/da/2025-01-15/exante/lmp",
            metadata={"data_source": "miso", "endpoint_name": "DA_EXANTE_LMP"},
            collection_params={"method": "GET"},
            file_date=date(2025, 1, 15)
        )

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(sample_lmp_response).encode()

        with patch.object(collector.session, "get", return_value=mock_response):
            content = collector.collect_content(candidate)

        assert content == mock_response.content
        assert json.loads(content) == sample_lmp_response

    def test_collect_content_http_error(self, collector):
        """Test collection with HTTP error."""
        candidate = DownloadCandidate(
            identifier="miso_da_exante_lmp_20250115.json",
            source_location="https://data-exchange.misoenergy.org/api/v1/da/2025-01-15/exante/lmp",
            metadata={"data_source": "miso"},
            collection_params={"method": "GET"},
            file_date=date(2025, 1, 15)
        )

        # Mock 404 error
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason = "Not Found"

        with patch.object(collector.session, "get", return_value=mock_response):
            with pytest.raises(ScrapingError, match="HTTP 404"):
                collector.collect_content(candidate)

    def test_collect_content_timeout(self, collector):
        """Test collection with timeout."""
        candidate = DownloadCandidate(
            identifier="miso_da_exante_lmp_20250115.json",
            source_location="https://data-exchange.misoenergy.org/api/v1/da/2025-01-15/exante/lmp",
            metadata={"data_source": "miso"},
            collection_params={"method": "GET"},
            file_date=date(2025, 1, 15)
        )

        with patch.object(
            collector.session,
            "get",
            side_effect=requests.exceptions.Timeout("Request timed out")
        ):
            with pytest.raises(ScrapingError, match="Request timeout"):
                collector.collect_content(candidate)

    def test_collect_content_connection_error(self, collector):
        """Test collection with connection error."""
        candidate = DownloadCandidate(
            identifier="miso_da_exante_lmp_20250115.json",
            source_location="https://data-exchange.misoenergy.org/api/v1/da/2025-01-15/exante/lmp",
            metadata={"data_source": "miso"},
            collection_params={"method": "GET"},
            file_date=date(2025, 1, 15)
        )

        with patch.object(
            collector.session,
            "get",
            side_effect=requests.exceptions.ConnectionError("Connection refused")
        ):
            with pytest.raises(ScrapingError, match="Connection error"):
                collector.collect_content(candidate)

    def test_validate_content_valid_dict(self, collector, sample_lmp_response):
        """Test content validation with valid JSON dict."""
        candidate = Mock()
        candidate.identifier = "test.json"

        content = json.dumps(sample_lmp_response).encode()
        assert collector.validate_content(content, candidate) is True

    def test_validate_content_valid_list(self, collector):
        """Test content validation with valid JSON list."""
        candidate = Mock()
        candidate.identifier = "test.json"

        data = [{"id": 1, "value": 100}, {"id": 2, "value": 200}]
        content = json.dumps(data).encode()
        assert collector.validate_content(content, candidate) is True

    def test_validate_content_empty_content(self, collector):
        """Test validation fails for empty content."""
        candidate = Mock()
        candidate.identifier = "test.json"

        assert collector.validate_content(b"", candidate) is False

    def test_validate_content_empty_json_dict(self, collector):
        """Test validation fails for empty JSON dict."""
        candidate = Mock()
        candidate.identifier = "test.json"

        content = json.dumps({}).encode()
        assert collector.validate_content(content, candidate) is False

    def test_validate_content_empty_json_array(self, collector):
        """Test validation fails for empty JSON array."""
        candidate = Mock()
        candidate.identifier = "test.json"

        content = json.dumps([]).encode()
        assert collector.validate_content(content, candidate) is False

    def test_validate_content_invalid_json(self, collector):
        """Test validation fails for invalid JSON."""
        candidate = Mock()
        candidate.identifier = "test.json"

        content = b"not valid json {[["
        assert collector.validate_content(content, candidate) is False

    def test_endpoint_configuration_completeness(self):
        """Test that all 12 endpoints are properly configured."""
        assert len(MISO_ENDPOINTS) == 12

        # Check Day-Ahead endpoints (6 total)
        da_endpoints = [ep for ep in MISO_ENDPOINTS if ep["market_type"] == "day-ahead"]
        assert len(da_endpoints) == 6

        # Check Real-Time endpoints (6 total)
        rt_endpoints = [ep for ep in MISO_ENDPOINTS if ep["market_type"] == "real-time"]
        assert len(rt_endpoints) == 6

        # Check data types coverage
        lmp_endpoints = [ep for ep in MISO_ENDPOINTS if ep["data_type"] == "lmp"]
        mcp_endpoints = [ep for ep in MISO_ENDPOINTS if ep["data_type"] == "mcp"]
        mcc_endpoints = [ep for ep in MISO_ENDPOINTS if ep["data_type"] == "mcc"]

        assert len(lmp_endpoints) == 4  # DA ex-ante, DA ex-post, RT 5-min, RT hourly
        assert len(mcp_endpoints) == 4
        assert len(mcc_endpoints) == 4

    def test_endpoint_path_formatting(self):
        """Test that endpoint paths are correctly formatted."""
        for endpoint in MISO_ENDPOINTS:
            # Check path contains placeholder
            assert "{date}" in endpoint["path"]

            # Check path starts correctly
            assert endpoint["path"].startswith("/api/v1/")

            # Check path structure matches market type
            if endpoint["market_type"] == "day-ahead":
                assert "/da/" in endpoint["path"]
            elif endpoint["market_type"] == "real-time":
                assert "/rt/" in endpoint["path"]

    @patch("sourcing.scraping.miso.scraper_miso_energy_pricing_http.setup_logging")
    def test_session_headers(self, mock_setup_logging, mock_redis):
        """Test that session headers are correctly configured."""
        api_key = "test-key-abc123"
        collector = MISOEnergyPricingCollector(
            dgroup="miso_test",
            s3_bucket="test-bucket",
            s3_prefix="sourcing",
            redis_client=mock_redis,
            environment="dev",
            api_key=api_key
        )

        headers = collector.session.headers
        assert headers["Ocp-Apim-Subscription-Key"] == api_key
        assert headers["Accept"] == "application/json"
        assert "User-Agent" in headers

    def test_timeout_configuration(self, mock_redis):
        """Test timeout can be customized."""
        collector = MISOEnergyPricingCollector(
            dgroup="miso_test",
            s3_bucket="test-bucket",
            s3_prefix="sourcing",
            redis_client=mock_redis,
            environment="dev",
            api_key="test-key",
            timeout=60
        )

        assert collector.timeout == 60

    @patch("sourcing.scraping.miso.scraper_miso_energy_pricing_http.setup_logging")
    def test_all_endpoints_generate_unique_identifiers(self, mock_setup_logging, collector):
        """Test that all endpoints generate unique identifiers."""
        start_date = datetime(2025, 1, 15)
        end_date = datetime(2025, 1, 16)

        candidates = collector.generate_candidates(
            start_date=start_date,
            end_date=end_date
        )

        # Extract all identifiers
        identifiers = [c.identifier for c in candidates]

        # Check uniqueness
        assert len(identifiers) == len(set(identifiers))

        # Check naming pattern
        for identifier in identifiers:
            assert identifier.startswith("miso_")
            assert identifier.endswith(".json")
            assert "_20250115.json" in identifier
