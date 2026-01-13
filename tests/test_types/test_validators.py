"""Tests for business logic validators."""

from agentic_scraper.types.validators import (
    validate_css_selector,
    validate_email_address,
    validate_file_pattern,
    validate_hostname,
    validate_json_path,
    validate_regex_pattern,
    validate_url_format,
    validate_xpath_selector,
)


# URL Validation Tests


def test_validate_url_format_valid() -> None:
    """Test validate_url_format with valid URLs."""
    result = validate_url_format("https://api.example.com")
    assert result.is_valid
    assert len(result.errors) == 0


def test_validate_url_format_http_warning() -> None:
    """Test validate_url_format warns about HTTP."""
    result = validate_url_format("http://api.example.com")
    assert result.is_valid
    assert any("insecure" in w.lower() for w in result.warnings)


def test_validate_url_format_invalid_scheme() -> None:
    """Test validate_url_format rejects invalid schemes."""
    result = validate_url_format("ftp://example.com")
    assert not result.is_valid
    assert any("scheme" in e.lower() for e in result.errors)


def test_validate_url_format_no_hostname() -> None:
    """Test validate_url_format rejects URLs without hostname."""
    result = validate_url_format("https://")
    assert not result.is_valid
    assert any("hostname" in e.lower() for e in result.errors)


def test_validate_url_format_with_spaces() -> None:
    """Test validate_url_format rejects URLs with spaces."""
    result = validate_url_format("https://api.example.com/path with spaces")
    assert not result.is_valid
    assert any("spaces" in e.lower() for e in result.errors)


# Email Validation Tests


def test_validate_email_address_valid() -> None:
    """Test validate_email_address with valid emails."""
    assert validate_email_address("user@example.com").is_valid
    assert validate_email_address("test.user+tag@example.co.uk").is_valid


def test_validate_email_address_invalid() -> None:
    """Test validate_email_address with invalid emails."""
    assert not validate_email_address("invalid-email").is_valid
    assert not validate_email_address("@example.com").is_valid
    assert not validate_email_address("user@").is_valid
    assert not validate_email_address("user @example.com").is_valid


# Hostname Validation Tests


def test_validate_hostname_valid() -> None:
    """Test validate_hostname with valid hostnames."""
    assert validate_hostname("api.example.com").is_valid
    assert validate_hostname("subdomain.api.example.com").is_valid
    assert validate_hostname("example.com").is_valid


def test_validate_hostname_invalid() -> None:
    """Test validate_hostname with invalid hostnames."""
    assert not validate_hostname("invalid..hostname").is_valid
    assert not validate_hostname("-invalid.com").is_valid
    assert not validate_hostname("invalid-.com").is_valid


def test_validate_hostname_localhost_warning() -> None:
    """Test validate_hostname warns about localhost."""
    result = validate_hostname("localhost")
    assert result.is_valid
    assert any("localhost" in w.lower() for w in result.warnings)


# File Pattern Validation Tests


def test_validate_file_pattern_valid() -> None:
    """Test validate_file_pattern with valid patterns."""
    assert validate_file_pattern("*.csv").is_valid
    assert validate_file_pattern("data_*.json").is_valid
    assert validate_file_pattern("report_[0-9][0-9].txt").is_valid


def test_validate_file_pattern_empty() -> None:
    """Test validate_file_pattern rejects empty patterns."""
    result = validate_file_pattern("")
    assert not result.is_valid
    assert any("empty" in e.lower() for e in result.errors)


def test_validate_file_pattern_wildcard_warning() -> None:
    """Test validate_file_pattern warns about broad patterns."""
    result = validate_file_pattern("*")
    assert result.is_valid
    assert any("all files" in w.lower() for w in result.warnings)


def test_validate_file_pattern_invalid_chars() -> None:
    """Test validate_file_pattern rejects invalid characters."""
    result = validate_file_pattern("file<name>.csv")
    assert not result.is_valid
    assert any("invalid character" in e.lower() for e in result.errors)


# CSS Selector Validation Tests


def test_validate_css_selector_valid() -> None:
    """Test validate_css_selector with valid selectors."""
    assert validate_css_selector("div.container").is_valid
    assert validate_css_selector("div > p").is_valid
    assert validate_css_selector("#main-content").is_valid
    assert validate_css_selector("ul li:first-child").is_valid


def test_validate_css_selector_empty() -> None:
    """Test validate_css_selector rejects empty selectors."""
    result = validate_css_selector("")
    assert not result.is_valid
    assert any("empty" in e.lower() for e in result.errors)


def test_validate_css_selector_invalid_leading() -> None:
    """Test validate_css_selector rejects invalid leading characters."""
    result = validate_css_selector(" div.container")
    assert not result.is_valid
    assert any("leading" in e.lower() for e in result.errors)


def test_validate_css_selector_invalid_trailing() -> None:
    """Test validate_css_selector rejects invalid trailing characters."""
    result = validate_css_selector("div.container >")
    assert not result.is_valid
    assert any("trailing" in e.lower() for e in result.errors)


def test_validate_css_selector_consecutive_special() -> None:
    """Test validate_css_selector rejects consecutive special characters."""
    result = validate_css_selector("div..container")
    assert not result.is_valid
    assert any("consecutive" in e.lower() for e in result.errors)


# XPath Selector Validation Tests


def test_validate_xpath_selector_valid() -> None:
    """Test validate_xpath_selector with valid selectors."""
    assert validate_xpath_selector("//div[@class='container']").is_valid
    assert validate_xpath_selector("//div[@class='container']/p").is_valid
    assert validate_xpath_selector(".//p[@id='main']").is_valid


def test_validate_xpath_selector_empty() -> None:
    """Test validate_xpath_selector rejects empty selectors."""
    result = validate_xpath_selector("")
    assert not result.is_valid
    assert any("empty" in e.lower() for e in result.errors)


def test_validate_xpath_selector_context_warning() -> None:
    """Test validate_xpath_selector warns about context."""
    result = validate_xpath_selector("div[@class='container']")
    assert result.is_valid
    assert len(result.warnings) > 0


def test_validate_xpath_selector_unbalanced_brackets() -> None:
    """Test validate_xpath_selector rejects unbalanced brackets."""
    result = validate_xpath_selector("//div[@class='container'")
    assert not result.is_valid
    assert any("brackets" in e.lower() for e in result.errors)


def test_validate_xpath_selector_unbalanced_parens() -> None:
    """Test validate_xpath_selector rejects unbalanced parentheses."""
    result = validate_xpath_selector("//div[contains(@class, 'container'")
    assert not result.is_valid
    assert any("parentheses" in e.lower() for e in result.errors)


# Regex Pattern Validation Tests


def test_validate_regex_pattern_valid() -> None:
    """Test validate_regex_pattern with valid patterns."""
    assert validate_regex_pattern(r"\d{4}-\d{2}-\d{2}").is_valid
    assert validate_regex_pattern(r"[A-Z][a-z]+").is_valid
    assert validate_regex_pattern(r"data_\d+\.csv").is_valid


def test_validate_regex_pattern_empty() -> None:
    """Test validate_regex_pattern warns about empty patterns."""
    result = validate_regex_pattern("")
    assert result.is_valid  # Empty is valid, just warns
    assert len(result.warnings) > 0


def test_validate_regex_pattern_invalid() -> None:
    """Test validate_regex_pattern rejects invalid regex."""
    result = validate_regex_pattern(r"[invalid")
    assert not result.is_valid
    assert any("invalid regex" in e.lower() for e in result.errors)


def test_validate_regex_pattern_unbalanced_parens() -> None:
    """Test validate_regex_pattern rejects unbalanced parentheses."""
    result = validate_regex_pattern(r"(group\d+")
    assert not result.is_valid


# JSON Path Validation Tests


def test_validate_json_path_valid() -> None:
    """Test validate_json_path with valid paths."""
    assert validate_json_path("$.data").is_valid
    assert validate_json_path("$.data.items[0]").is_valid
    assert validate_json_path("$.data.items[*].name").is_valid


def test_validate_json_path_empty() -> None:
    """Test validate_json_path rejects empty paths."""
    result = validate_json_path("")
    assert not result.is_valid
    assert any("empty" in e.lower() for e in result.errors)


def test_validate_json_path_no_root() -> None:
    """Test validate_json_path rejects paths without $."""
    result = validate_json_path("data.items")
    assert not result.is_valid
    assert any("should start with $" in e.lower() for e in result.errors)


def test_validate_json_path_unbalanced_brackets() -> None:
    """Test validate_json_path rejects unbalanced brackets."""
    result = validate_json_path("$.data.items[0")
    assert not result.is_valid
    assert any("brackets" in e.lower() for e in result.errors)
