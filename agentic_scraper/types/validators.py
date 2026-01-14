"""Business logic validators for scraper configurations.

This module provides validation utilities that check business rules
beyond basic type validation. These validators help ensure scrapers
are configured correctly and will work as expected.

Example:
    >>> from agentic_scraper.types.validators import validate_url_accessible
    >>> result = validate_url_accessible("https://api.example.com")
    >>> if not result.is_valid:
    ...     print(result.errors)
"""

import re
from typing import Any
from urllib.parse import urlparse

from agentic_scraper.types.base import ValidationResult


def validate_url_format(url: str) -> ValidationResult:
    """Validate URL format and structure.

    Args:
        url: URL to validate

    Returns:
        ValidationResult with errors for invalid URLs

    Example:
        >>> validate_url_format("https://api.example.com/data")
        ValidationResult(is_valid=True, errors=[], warnings=[])
        >>> validate_url_format("not-a-url")
        ValidationResult(is_valid=False, errors=['Invalid URL format'], warnings=[])
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme not in ("http", "https"):
            errors.append(f"URL scheme must be http or https, got: {parsed.scheme}")

        # Check netloc (hostname)
        if not parsed.netloc:
            errors.append("URL missing hostname")

        # Check for common issues
        if " " in url:
            errors.append("URL contains spaces")

        if parsed.scheme == "http":
            warnings.append("Using insecure HTTP protocol (consider HTTPS)")

    except Exception as e:
        errors.append(f"Invalid URL format: {e}")

    return ValidationResult(
        is_valid=len(errors) == 0, errors=errors, warnings=warnings
    )


def validate_email_address(email: str) -> ValidationResult:
    """Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        ValidationResult with errors for invalid emails

    Example:
        >>> validate_email_address("user@example.com")
        ValidationResult(is_valid=True, errors=[], warnings=[])
        >>> validate_email_address("invalid-email")
        ValidationResult(is_valid=False, errors=['Invalid email format'], warnings=[])
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Simple email regex (not RFC 5322 compliant, but catches most errors)
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(email_pattern, email):
        errors.append("Invalid email format")

    return ValidationResult(
        is_valid=len(errors) == 0, errors=errors, warnings=warnings
    )


def validate_hostname(hostname: str) -> ValidationResult:
    """Validate hostname format.

    Args:
        hostname: Hostname to validate

    Returns:
        ValidationResult with errors for invalid hostnames

    Example:
        >>> validate_hostname("api.example.com")
        ValidationResult(is_valid=True, errors=[], warnings=[])
        >>> validate_hostname("invalid..hostname")
        ValidationResult(is_valid=False, errors=['Invalid hostname format'], warnings=[])
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Hostname validation regex
    hostname_pattern = r"^(?=.{1,253}$)(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.[a-zA-Z0-9-]{1,63})*$"

    if not re.match(hostname_pattern, hostname):
        errors.append("Invalid hostname format")

    # Check for localhost
    if hostname in ("localhost", "127.0.0.1", "::1"):
        warnings.append("Hostname points to localhost")

    return ValidationResult(
        is_valid=len(errors) == 0, errors=errors, warnings=warnings
    )


def validate_file_pattern(pattern: str) -> ValidationResult:
    """Validate file pattern (glob) format.

    Args:
        pattern: File pattern to validate

    Returns:
        ValidationResult with errors for invalid patterns

    Example:
        >>> validate_file_pattern("*.csv")
        ValidationResult(is_valid=True, errors=[], warnings=[])
        >>> validate_file_pattern("data_[0-9].csv")
        ValidationResult(is_valid=True, errors=[], warnings=[])
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Check for empty pattern
    if not pattern:
        errors.append("File pattern cannot be empty")
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    # Warn about overly broad patterns
    if pattern in ("*", "*.*"):
        warnings.append("Pattern matches all files")

    # Check for invalid characters (OS-specific, being conservative)
    invalid_chars = ["<", ">", '"', "|", "\0"]
    for char in invalid_chars:
        if char in pattern:
            errors.append(f"File pattern contains invalid character: {char}")

    return ValidationResult(
        is_valid=len(errors) == 0, errors=errors, warnings=warnings
    )


def validate_css_selector(selector: str) -> ValidationResult:
    """Validate CSS selector syntax (basic check).

    Args:
        selector: CSS selector to validate

    Returns:
        ValidationResult with errors for invalid selectors

    Example:
        >>> validate_css_selector("div.container > p")
        ValidationResult(is_valid=True, errors=[], warnings=[])
        >>> validate_css_selector("")
        ValidationResult(is_valid=False, errors=['CSS selector cannot be empty'], warnings=[])
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not selector:
        errors.append("CSS selector cannot be empty")
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    # Basic syntax checks
    if selector.startswith((" ", ">", "+", "~")):
        errors.append("CSS selector has invalid leading character")

    if selector.endswith((" ", ">", "+", "~")):
        errors.append("CSS selector has invalid trailing character")

    # Check for common mistakes
    if ".." in selector or "##" in selector:
        errors.append("CSS selector contains consecutive special characters")

    return ValidationResult(
        is_valid=len(errors) == 0, errors=errors, warnings=warnings
    )


def validate_xpath_selector(selector: str) -> ValidationResult:
    """Validate XPath selector syntax (basic check).

    Args:
        selector: XPath selector to validate

    Returns:
        ValidationResult with errors for invalid selectors

    Example:
        >>> validate_xpath_selector("//div[@class='container']/p")
        ValidationResult(is_valid=True, errors=[], warnings=[])
        >>> validate_xpath_selector("")
        ValidationResult(is_valid=False, errors=['XPath selector cannot be empty'], warnings=[])
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not selector:
        errors.append("XPath selector cannot be empty")
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    # Basic syntax checks
    if not selector.startswith(("/", ".")):
        warnings.append("XPath selector should start with / or . for proper context")

    # Check for balanced brackets
    if selector.count("[") != selector.count("]"):
        errors.append("XPath selector has unbalanced brackets")

    if selector.count("(") != selector.count(")"):
        errors.append("XPath selector has unbalanced parentheses")

    return ValidationResult(
        is_valid=len(errors) == 0, errors=errors, warnings=warnings
    )


def validate_regex_pattern(pattern: str) -> ValidationResult:
    """Validate regex pattern syntax.

    Args:
        pattern: Regex pattern to validate

    Returns:
        ValidationResult with errors for invalid patterns

    Example:
        >>> validate_regex_pattern(r"data_\\d{4}\\.csv")
        ValidationResult(is_valid=True, errors=[], warnings=[])
        >>> validate_regex_pattern(r"[invalid")
        ValidationResult(is_valid=False, errors=['Invalid regex: ...'], warnings=[])
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not pattern:
        warnings.append("Empty regex pattern matches nothing")
        return ValidationResult(is_valid=True, errors=errors, warnings=warnings)

    try:
        re.compile(pattern)
    except re.error as e:
        errors.append(f"Invalid regex: {e}")

    return ValidationResult(
        is_valid=len(errors) == 0, errors=errors, warnings=warnings
    )


def validate_json_path(path: str) -> ValidationResult:
    """Validate JSON path format (basic check).

    Args:
        path: JSON path to validate (e.g., "$.data.items[0].name")

    Returns:
        ValidationResult with errors for invalid paths

    Example:
        >>> validate_json_path("$.data.items[0]")
        ValidationResult(is_valid=True, errors=[], warnings=[])
        >>> validate_json_path("data")
        ValidationResult(is_valid=False, errors=['JSON path should start with $'], warnings=[])
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not path:
        errors.append("JSON path cannot be empty")
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    if not path.startswith("$"):
        errors.append("JSON path should start with $")

    # Check for balanced brackets
    if path.count("[") != path.count("]"):
        errors.append("JSON path has unbalanced brackets")

    return ValidationResult(
        is_valid=len(errors) == 0, errors=errors, warnings=warnings
    )
