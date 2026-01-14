"""Tests for scraper specification enums."""

import pytest

from agentic_scraper.types.enums import (
    ScraperMethod,
    DataFormat,
    AuthenticationMethod,
    UpdateFrequency,
)


# ScraperMethod Tests


def test_scraper_method_values() -> None:
    """Test ScraperMethod enum values."""
    assert ScraperMethod.HTTP_API == "http_api"
    assert ScraperMethod.WEBSITE_PARSER == "website_parser"
    assert ScraperMethod.FTP_CLIENT == "ftp_client"
    assert ScraperMethod.EMAIL_COLLECTOR == "email_collector"


def test_scraper_method_display_names() -> None:
    """Test ScraperMethod display_name property."""
    assert ScraperMethod.HTTP_API.display_name == "HTTP/REST API"
    assert ScraperMethod.WEBSITE_PARSER.display_name == "Website Parsing"
    assert ScraperMethod.FTP_CLIENT.display_name == "FTP/SFTP Client"
    assert ScraperMethod.EMAIL_COLLECTOR.display_name == "Email Attachments"


def test_scraper_method_string_comparison() -> None:
    """Test ScraperMethod works with string comparison."""
    method = ScraperMethod.HTTP_API
    assert method == "http_api"
    assert method.value == "http_api"


# DataFormat Tests


def test_data_format_values() -> None:
    """Test DataFormat enum values."""
    assert DataFormat.JSON == "json"
    assert DataFormat.CSV == "csv"
    assert DataFormat.XML == "xml"
    assert DataFormat.HTML == "html"
    assert DataFormat.BINARY == "binary"
    assert DataFormat.PARQUET == "parquet"
    assert DataFormat.UNKNOWN == "unknown"


def test_data_format_display_names() -> None:
    """Test DataFormat display_name property."""
    assert DataFormat.JSON.display_name == "JSON"
    assert DataFormat.CSV.display_name == "CSV"
    assert DataFormat.XML.display_name == "XML"
    assert DataFormat.HTML.display_name == "HTML"
    assert DataFormat.BINARY.display_name == "Binary"
    assert DataFormat.PARQUET.display_name == "Parquet"
    assert DataFormat.UNKNOWN.display_name == "Unknown"


def test_data_format_auto_select_json_preference() -> None:
    """Test DataFormat.auto_select prefers JSON."""
    # JSON at end
    assert DataFormat.auto_select(["csv", "xml", "json"]) == DataFormat.JSON

    # JSON at beginning
    assert DataFormat.auto_select(["json", "csv", "xml"]) == DataFormat.JSON

    # JSON in middle
    assert DataFormat.auto_select(["xml", "json", "csv"]) == DataFormat.JSON


def test_data_format_auto_select_case_insensitive() -> None:
    """Test DataFormat.auto_select is case-insensitive."""
    assert DataFormat.auto_select(["JSON", "csv"]) == DataFormat.JSON
    assert DataFormat.auto_select(["Json", "csv"]) == DataFormat.JSON
    assert DataFormat.auto_select(["json", "CSV"]) == DataFormat.JSON
    assert DataFormat.auto_select(["XML"]) == DataFormat.XML


def test_data_format_auto_select_fallback_order() -> None:
    """Test DataFormat.auto_select fallback order."""
    # No JSON → CSV preferred
    assert DataFormat.auto_select(["csv", "xml"]) == DataFormat.CSV

    # No JSON or CSV → XML preferred
    assert DataFormat.auto_select(["xml", "html"]) == DataFormat.XML

    # No JSON, CSV, or XML → Parquet preferred
    assert DataFormat.auto_select(["parquet", "html"]) == DataFormat.PARQUET

    # No JSON, CSV, XML, or Parquet → HTML preferred
    assert DataFormat.auto_select(["html", "binary"]) == DataFormat.HTML

    # Binary
    assert DataFormat.auto_select(["binary"]) == DataFormat.BINARY
    assert DataFormat.auto_select(["bin"]) == DataFormat.BINARY


def test_data_format_auto_select_unknown() -> None:
    """Test DataFormat.auto_select returns UNKNOWN for unrecognized formats."""
    assert DataFormat.auto_select(["unknown_format"]) == DataFormat.UNKNOWN
    assert DataFormat.auto_select(["weird", "strange"]) == DataFormat.UNKNOWN


def test_data_format_auto_select_empty_list() -> None:
    """Test DataFormat.auto_select handles empty list."""
    assert DataFormat.auto_select([]) == DataFormat.UNKNOWN


def test_data_format_auto_select_whitespace() -> None:
    """Test DataFormat.auto_select handles whitespace."""
    assert DataFormat.auto_select(["  json  ", "csv"]) == DataFormat.JSON
    assert DataFormat.auto_select(["  CSV  "]) == DataFormat.CSV


# AuthenticationMethod Tests


def test_authentication_method_values() -> None:
    """Test AuthenticationMethod enum values."""
    assert AuthenticationMethod.NONE == "none"
    assert AuthenticationMethod.API_KEY == "api_key"
    assert AuthenticationMethod.BEARER_TOKEN == "bearer_token"
    assert AuthenticationMethod.OAUTH == "oauth"
    assert AuthenticationMethod.BASIC_AUTH == "basic_auth"
    assert AuthenticationMethod.COOKIE == "cookie"
    assert AuthenticationMethod.UNKNOWN == "unknown"


def test_authentication_method_display_names() -> None:
    """Test AuthenticationMethod display_name property."""
    assert AuthenticationMethod.NONE.display_name == "None"
    assert AuthenticationMethod.API_KEY.display_name == "API Key"
    assert AuthenticationMethod.BEARER_TOKEN.display_name == "Bearer Token"
    assert AuthenticationMethod.OAUTH.display_name == "OAuth 2.0"
    assert AuthenticationMethod.BASIC_AUTH.display_name == "Basic Auth"
    assert AuthenticationMethod.COOKIE.display_name == "Cookie-based"
    assert AuthenticationMethod.UNKNOWN.display_name == "Unknown"


# UpdateFrequency Tests


def test_update_frequency_values() -> None:
    """Test UpdateFrequency enum values."""
    assert UpdateFrequency.REALTIME == "realtime"
    assert UpdateFrequency.EVERY_5_MINUTES == "every_5_minutes"
    assert UpdateFrequency.HOURLY == "hourly"
    assert UpdateFrequency.DAILY == "daily"
    assert UpdateFrequency.WEEKLY == "weekly"
    assert UpdateFrequency.MONTHLY == "monthly"


def test_update_frequency_display_names() -> None:
    """Test UpdateFrequency display_name property."""
    assert UpdateFrequency.REALTIME.display_name == "Real-time"
    assert UpdateFrequency.EVERY_5_MINUTES.display_name == "Every 5 minutes"
    assert UpdateFrequency.HOURLY.display_name == "Hourly"
    assert UpdateFrequency.DAILY.display_name == "Daily"
    assert UpdateFrequency.WEEKLY.display_name == "Weekly"
    assert UpdateFrequency.MONTHLY.display_name == "Monthly"


# Serialization Tests


def test_enum_json_serialization() -> None:
    """Test that enums serialize correctly to JSON."""
    import json

    # ScraperMethod
    data = {"method": ScraperMethod.HTTP_API}
    json_str = json.dumps(data, default=str)
    assert "http_api" in json_str


# Edge Case Tests


def test_data_format_auto_select_with_none() -> None:
    """Test DataFormat.auto_select handles None values in list."""
    # None in list should be ignored
    assert DataFormat.auto_select(["json", None, "csv"]) == DataFormat.JSON
    assert DataFormat.auto_select([None, "csv", None]) == DataFormat.CSV
    assert DataFormat.auto_select([None, None]) == DataFormat.UNKNOWN


def test_data_format_auto_select_with_non_strings() -> None:
    """Test DataFormat.auto_select handles non-string types."""
    # Numbers should be ignored
    assert DataFormat.auto_select([123, "json", 456]) == DataFormat.JSON
    assert DataFormat.auto_select([123, "csv"]) == DataFormat.CSV

    # Mixed types should be ignored
    assert DataFormat.auto_select([None, 123, "xml", [], {}]) == DataFormat.XML

    # All non-strings should return UNKNOWN
    assert DataFormat.auto_select([None, 123, [], {}]) == DataFormat.UNKNOWN


def test_enum_invalid_value() -> None:
    """Test that invalid enum values raise ValueError."""
    import pytest

    with pytest.raises(ValueError):
        ScraperMethod("invalid_method")

    with pytest.raises(ValueError):
        DataFormat("invalid_format")


def test_enum_string_comparison() -> None:
    """Test enum comparison with strings works correctly."""
    method = ScraperMethod.HTTP_API
    assert method == "http_api"
    assert "http_api" == method
    assert method != "website_parser"
