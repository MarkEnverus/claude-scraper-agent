"""Tests for scraper specification models."""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from agentic_scraper.types import Metadata
from agentic_scraper.types.scraper_spec import (
    APIConfig,
    EmailConfig,
    FTPConfig,
    HTTPEndpoint,
    ScraperSpec,
    WebsiteConfig,
    WebsiteSelector,
)


# HTTPEndpoint Tests


def test_http_endpoint_creation() -> None:
    """Test HTTPEndpoint creation."""
    endpoint = HTTPEndpoint(path="/api/data", method="GET")
    assert endpoint.path == "/api/data"
    assert endpoint.method == "GET"
    assert endpoint.description == ""
    assert endpoint.params == {}
    assert endpoint.headers == {}


def test_http_endpoint_with_params() -> None:
    """Test HTTPEndpoint with parameters."""
    endpoint = HTTPEndpoint(
        path="/api/data",
        method="POST",
        description="Fetch data",
        params={"key": "value"},
        headers={"Content-Type": "application/json"},
    )
    assert endpoint.params == {"key": "value"}
    assert endpoint.headers == {"Content-Type": "application/json"}


def test_http_endpoint_empty_path() -> None:
    """Test HTTPEndpoint rejects empty path."""
    with pytest.raises(ValidationError):
        HTTPEndpoint(path="", method="GET")


# APIConfig Tests


def test_api_config_creation() -> None:
    """Test APIConfig creation."""
    config = APIConfig(
        data_source="NYISO",
        data_type="load_forecast",
        update_frequency="hourly",
        api_base_url="https://api.nyiso.com",
    )
    assert config.method == "http_api"
    assert config.data_source == "NYISO"
    assert config.api_base_url == "https://api.nyiso.com"
    assert config.data_format == "json"  # default
    assert config.rate_limit_requests == 60  # default


def test_api_config_invalid_url() -> None:
    """Test APIConfig rejects invalid URLs."""
    with pytest.raises(ValidationError):
        APIConfig(
            data_source="TEST",
            data_type="test",
            update_frequency="hourly",
            api_base_url="not-a-url",
        )


def test_api_config_with_endpoints() -> None:
    """Test APIConfig with endpoints."""
    endpoints = [
        HTTPEndpoint(path="/data", method="GET"),
        HTTPEndpoint(path="/forecast", method="POST"),
    ]
    config = APIConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="hourly",
        api_base_url="https://api.test.com",
        endpoints=endpoints,
    )
    assert len(config.endpoints) == 2
    assert config.endpoints[0].path == "/data"


def test_api_config_validation() -> None:
    """Test APIConfig validation method."""
    config = APIConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="hourly",
        api_base_url="https://api.test.com",
    )
    result = config.validate_config()
    assert result.is_valid
    assert len(result.warnings) > 0  # Should warn about no endpoints


def test_api_config_rate_limit_warning() -> None:
    """Test APIConfig warns about high rate limits."""
    config = APIConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="hourly",
        api_base_url="https://api.test.com",
        rate_limit_requests=1500,
    )
    result = config.validate_config()
    assert result.is_valid
    assert any("rate limit" in w.lower() for w in result.warnings)


# FTPConfig Tests


def test_ftp_config_creation() -> None:
    """Test FTPConfig creation."""
    config = FTPConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="daily",
        host="ftp.test.com",
    )
    assert config.method == "ftp_client"
    assert config.host == "ftp.test.com"
    assert config.port == 21  # default
    assert config.use_sftp is False  # default


def test_ftp_config_sftp() -> None:
    """Test FTPConfig with SFTP."""
    config = FTPConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="daily",
        host="sftp.test.com",
        port=22,
        use_sftp=True,
    )
    assert config.use_sftp is True
    assert config.port == 22


def test_ftp_config_validation() -> None:
    """Test FTPConfig validation method."""
    config = FTPConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="daily",
        host="ftp.test.com",
        use_sftp=True,
        port=21,  # Wrong port for SFTP
    )
    result = config.validate_config()
    assert result.is_valid
    assert any("port" in w.lower() for w in result.warnings)


# EmailConfig Tests


def test_email_config_creation() -> None:
    """Test EmailConfig creation."""
    config = EmailConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="hourly",
        imap_host="imap.test.com",
    )
    assert config.method == "email_collector"
    assert config.imap_host == "imap.test.com"
    assert config.imap_port == 993  # default
    assert config.mailbox == "INBOX"  # default


def test_email_config_with_filters() -> None:
    """Test EmailConfig with filters."""
    config = EmailConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="hourly",
        imap_host="imap.test.com",
        subject_filter="Data Report",
        sender_filter="reports@test.com",
    )
    assert config.subject_filter == "Data Report"
    assert config.sender_filter == "reports@test.com"


def test_email_config_validation() -> None:
    """Test EmailConfig validation method."""
    config = EmailConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="hourly",
        imap_host="imap.test.com",
    )
    result = config.validate_config()
    assert result.is_valid
    assert any("filter" in w.lower() for w in result.warnings)


def test_email_config_deletion_warning() -> None:
    """Test EmailConfig warns about deletion."""
    config = EmailConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="hourly",
        imap_host="imap.test.com",
        delete_after_processing=True,
    )
    result = config.validate_config()
    assert result.is_valid
    assert any("delete" in w.lower() for w in result.warnings)


# WebsiteSelector Tests


def test_website_selector_creation() -> None:
    """Test WebsiteSelector creation."""
    selector = WebsiteSelector(name="price", selector="div.price")
    assert selector.name == "price"
    assert selector.selector == "div.price"
    assert selector.selector_type == "css"  # default
    assert selector.attribute == ""


def test_website_selector_xpath() -> None:
    """Test WebsiteSelector with XPath."""
    selector = WebsiteSelector(
        name="title",
        selector="//div[@class='title']",
        selector_type="xpath",
    )
    assert selector.selector_type == "xpath"


# WebsiteConfig Tests


def test_website_config_creation() -> None:
    """Test WebsiteConfig creation."""
    config = WebsiteConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="daily",
        target_url="https://www.test.com",
    )
    assert config.method == "website_parser"
    assert config.target_url == "https://www.test.com"
    assert config.use_javascript is False  # default


def test_website_config_invalid_url() -> None:
    """Test WebsiteConfig rejects invalid URLs."""
    with pytest.raises(ValidationError):
        WebsiteConfig(
            data_source="TEST",
            data_type="test",
            update_frequency="daily",
            target_url="not-a-url",
        )


def test_website_config_with_selectors() -> None:
    """Test WebsiteConfig with selectors."""
    selectors = [
        WebsiteSelector(name="price", selector="div.price"),
        WebsiteSelector(name="title", selector="h1.title"),
    ]
    config = WebsiteConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="daily",
        target_url="https://www.test.com",
        selectors=selectors,
    )
    assert len(config.selectors) == 2


def test_website_config_validation() -> None:
    """Test WebsiteConfig validation method."""
    config = WebsiteConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="daily",
        target_url="https://www.test.com",
        use_javascript=True,
    )
    result = config.validate_config()
    assert result.is_valid
    assert any("javascript" in w.lower() for w in result.warnings)


# ScraperSpec Tests


def test_scraper_spec_api() -> None:
    """Test ScraperSpec with APIConfig."""
    from agentic_scraper.types.enums import ScraperMethod

    api_config = APIConfig(
        data_source="NYISO",
        data_type="load",
        update_frequency="hourly",
        api_base_url="https://api.nyiso.com",
    )
    metadata = Metadata(
        scraper_version="1.11.0",
        infrastructure_version="1.11.0",
        generated_date="2025-12-19",
        last_updated="2025-12-19",
        generator_agent="http-collector",
    )
    spec = ScraperSpec(
        method=ScraperMethod.HTTP_API,
        config=api_config,
        metadata=metadata,
    )
    assert spec.method == ScraperMethod.HTTP_API
    assert isinstance(spec.config, APIConfig)
    assert spec.config.data_source == "NYISO"


def test_scraper_spec_ftp() -> None:
    """Test ScraperSpec with FTPConfig."""
    from agentic_scraper.types.enums import ScraperMethod

    ftp_config = FTPConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="daily",
        host="ftp.test.com",
    )
    metadata = Metadata(
        scraper_version="1.11.0",
        infrastructure_version="1.11.0",
        generated_date="2025-12-19",
        last_updated="2025-12-19",
        generator_agent="ftp-collector",
    )
    spec = ScraperSpec(
        method=ScraperMethod.FTP_CLIENT,
        config=ftp_config,
        metadata=metadata,
    )
    assert spec.method == ScraperMethod.FTP_CLIENT
    assert isinstance(spec.config, FTPConfig)


def test_scraper_spec_validation() -> None:
    """Test ScraperSpec validation."""
    from agentic_scraper.types.enums import ScraperMethod

    config = APIConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="hourly",
        api_base_url="https://api.test.com",
    )
    metadata = Metadata(
        scraper_version="1.11.0",
        infrastructure_version="1.11.0",
        generated_date="2025-12-19",
        last_updated="2025-12-19",
        generator_agent="test",
    )
    spec = ScraperSpec(
        method=ScraperMethod.HTTP_API,
        config=config,
        metadata=metadata,
    )
    result = spec.validate_spec()
    assert isinstance(result.is_valid, bool)


def test_scraper_spec_serialization() -> None:
    """Test ScraperSpec JSON serialization."""
    from agentic_scraper.types.enums import ScraperMethod

    config = APIConfig(
        data_source="TEST",
        data_type="test",
        update_frequency="hourly",
        api_base_url="https://api.test.com",
    )
    metadata = Metadata(
        scraper_version="1.11.0",
        infrastructure_version="1.11.0",
        generated_date="2025-12-19",
        last_updated="2025-12-19",
        generator_agent="test",
    )
    spec = ScraperSpec(
        method=ScraperMethod.HTTP_API,
        config=config,
        metadata=metadata,
    )

    # Serialize
    json_str = spec.model_dump_json()
    assert isinstance(json_str, str)
    assert "http_api" in json_str

    # Deserialize
    spec2 = ScraperSpec.model_validate_json(json_str)
    assert spec2.method == spec.method
    assert spec2.config.data_source == spec.config.data_source
