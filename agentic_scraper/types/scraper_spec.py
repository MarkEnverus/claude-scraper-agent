"""Scraper specification models.

This module defines method-specific scraper configurations (API, FTP, Email, Website)
and the main ScraperSpec model that uses discriminated unions for type-safe
scraper generation.

Example:
    >>> from agentic_scraper.types.scraper_spec import APIConfig, ScraperSpec
    >>> config = APIConfig(
    ...     data_source="example_source",
    ...     data_type="data_forecast",
    ...     update_frequency="hourly",
    ...     api_base_url="https://api.example.com",
    ...     endpoints=[{"path": "/forecast", "method": "GET"}]
    ... )
    >>> spec = ScraperSpec(method="http_api", config=config)
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agentic_scraper.types.base import BaseScraperConfig, Metadata, ValidationResult
from agentic_scraper.types.enums import (
    AuthenticationMethod,
    DataFormat,
    ScraperMethod,
    UpdateFrequency,
)


# HTTP/REST API Configuration


class HTTPEndpoint(BaseModel):
    """HTTP endpoint configuration.

    Attributes:
        path: Endpoint path (e.g., "/api/data")
        method: HTTP method (GET, POST, etc.)
        description: Optional endpoint description
        params: Optional query parameters
        headers: Optional custom headers
    """

    model_config = ConfigDict(frozen=False)

    path: str = Field(..., min_length=1, description="Endpoint path")
    method: str = Field(default="GET", description="HTTP method")
    description: str = Field(default="", description="Endpoint description")
    params: dict[str, Any] = Field(default_factory=dict, description="Query parameters")
    headers: dict[str, str] = Field(default_factory=dict, description="Custom headers")


class APIConfig(BaseScraperConfig):
    """HTTP/REST API scraper configuration.

    Inherits from BaseScraperConfig and adds API-specific fields.

    Attributes:
        method: Always "http_api" (discriminator)
        api_base_url: Base URL for API
        endpoints: List of endpoint configurations
        data_format: Expected data format (e.g., "json", "xml")
        auth_method: Authentication method
        rate_limit_requests: Max requests per minute (0 = unlimited)
        timeout_seconds: Request timeout in seconds
        retry_attempts: Number of retry attempts on failure
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    method: Literal["http_api"] = Field(default="http_api", description="Scraper method")
    api_base_url: str = Field(..., min_length=1, description="API base URL")
    endpoints: list[HTTPEndpoint] = Field(
        default_factory=list, description="API endpoints"
    )
    data_format: str = Field(default="json", description="Expected data format")
    auth_method: str = Field(default="none", description="Authentication method")
    rate_limit_requests: int = Field(default=60, ge=0, description="Requests per minute")
    timeout_seconds: int = Field(default=30, ge=1, description="Request timeout")
    retry_attempts: int = Field(default=3, ge=0, description="Retry attempts")

    @field_validator("api_base_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("api_base_url must start with http:// or https://")
        return v

    def validate_config(self) -> ValidationResult:
        """Validate API configuration.

        Returns:
            ValidationResult with errors and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check endpoints
        if not self.endpoints:
            warnings.append("No endpoints configured")

        # Check rate limiting
        if self.rate_limit_requests > 1000:
            warnings.append("Rate limit > 1000 req/min may cause issues")

        # Check timeout
        if self.timeout_seconds > 300:
            warnings.append("Timeout > 5 minutes may be excessive")

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )


# FTP/SFTP Configuration


class FTPConfig(BaseScraperConfig):
    """FTP/SFTP scraper configuration.

    Attributes:
        method: Always "ftp_client" (discriminator)
        host: FTP server hostname
        port: FTP server port
        use_sftp: Use SFTP instead of FTP
        remote_directory: Remote directory path
        file_pattern: File pattern to match (e.g., "*.csv")
        data_format: Expected file format
        passive_mode: Use passive FTP mode
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    method: Literal["ftp_client"] = Field(default="ftp_client", description="Scraper method")
    host: str = Field(..., min_length=1, description="FTP server hostname")
    port: int = Field(default=21, ge=1, le=65535, description="FTP server port")
    use_sftp: bool = Field(default=False, description="Use SFTP")
    remote_directory: str = Field(default="/", description="Remote directory path")
    file_pattern: str = Field(default="*", description="File pattern to match")
    data_format: str = Field(default="csv", description="Expected file format")
    passive_mode: bool = Field(default=True, description="Use passive mode")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port for SFTP default."""
        # Note: use_sftp not available in validator context, will check in validate_config
        return v

    def validate_config(self) -> ValidationResult:
        """Validate FTP configuration.

        Returns:
            ValidationResult with errors and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check SFTP port
        if self.use_sftp and self.port == 21:
            warnings.append("SFTP typically uses port 22, not 21")

        # Check file pattern
        if self.file_pattern == "*":
            warnings.append("File pattern '*' will match all files")

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )


# Email Configuration


class EmailConfig(BaseScraperConfig):
    """Email attachment scraper configuration.

    Attributes:
        method: Always "email_collector" (discriminator)
        imap_host: IMAP server hostname
        imap_port: IMAP server port
        mailbox: Mailbox name to monitor
        subject_filter: Subject line filter (regex)
        sender_filter: Sender email filter
        attachment_pattern: Attachment filename pattern
        data_format: Expected attachment format
        mark_as_read: Mark emails as read after processing
        delete_after_processing: Delete emails after processing
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    method: Literal["email_collector"] = Field(
        default="email_collector", description="Scraper method"
    )
    imap_host: str = Field(..., min_length=1, description="IMAP server hostname")
    imap_port: int = Field(default=993, ge=1, le=65535, description="IMAP server port")
    mailbox: str = Field(default="INBOX", description="Mailbox name")
    subject_filter: str = Field(default="", description="Subject line filter")
    sender_filter: str = Field(default="", description="Sender email filter")
    attachment_pattern: str = Field(default="*", description="Attachment filename pattern")
    data_format: str = Field(default="csv", description="Expected attachment format")
    mark_as_read: bool = Field(default=True, description="Mark as read after processing")
    delete_after_processing: bool = Field(
        default=False, description="Delete after processing"
    )

    def validate_config(self) -> ValidationResult:
        """Validate email configuration.

        Returns:
            ValidationResult with errors and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check filters
        if not self.subject_filter and not self.sender_filter:
            warnings.append("No subject or sender filter - will process all emails")

        # Check deletion
        if self.delete_after_processing:
            warnings.append("delete_after_processing=True - emails will be permanently deleted")

        # Check attachment pattern
        if self.attachment_pattern == "*":
            warnings.append("Attachment pattern '*' will match all attachments")

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )


# Website Parsing Configuration


class WebsiteSelector(BaseModel):
    """CSS/XPath selector for website parsing.

    Attributes:
        name: Selector name (e.g., "price", "title")
        selector: CSS selector or XPath expression
        selector_type: Type of selector ("css" or "xpath")
        attribute: Optional attribute to extract (e.g., "href")
    """

    model_config = ConfigDict(frozen=False)

    name: str = Field(..., min_length=1, description="Selector name")
    selector: str = Field(..., min_length=1, description="Selector expression")
    selector_type: Literal["css", "xpath"] = Field(default="css", description="Selector type")
    attribute: str = Field(default="", description="Attribute to extract")


class WebsiteConfig(BaseScraperConfig):
    """Website parsing scraper configuration.

    Attributes:
        method: Always "website_parser" (discriminator)
        target_url: URL to scrape
        selectors: List of CSS/XPath selectors
        data_format: Expected data format (usually "html")
        use_javascript: Use headless browser for JavaScript rendering
        wait_time_seconds: Wait time for page load (if using JavaScript)
        pagination_selector: Optional pagination selector
        max_pages: Maximum pages to scrape (0 = unlimited)
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    method: Literal["website_parser"] = Field(
        default="website_parser", description="Scraper method"
    )
    target_url: str = Field(..., min_length=1, description="URL to scrape")
    selectors: list[WebsiteSelector] = Field(
        default_factory=list, description="CSS/XPath selectors"
    )
    data_format: str = Field(default="html", description="Expected data format")
    use_javascript: bool = Field(default=False, description="Use headless browser")
    wait_time_seconds: int = Field(default=3, ge=0, description="Page load wait time")
    pagination_selector: str = Field(default="", description="Pagination selector")
    max_pages: int = Field(default=1, ge=0, description="Maximum pages to scrape")

    @field_validator("target_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("target_url must start with http:// or https://")
        return v

    def validate_config(self) -> ValidationResult:
        """Validate website configuration.

        Returns:
            ValidationResult with errors and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check selectors
        if not self.selectors:
            warnings.append("No selectors configured")

        # Check JavaScript
        if self.use_javascript:
            warnings.append("JavaScript rendering requires additional dependencies")

        # Check pagination
        if self.max_pages > 100:
            warnings.append("max_pages > 100 may take significant time")

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )


# Main ScraperSpec with discriminated unions


ScraperConfig = APIConfig | FTPConfig | EmailConfig | WebsiteConfig


class ScraperSpec(BaseModel):
    """Complete scraper specification with discriminated unions.

    Uses the 'method' field to discriminate between config types.

    Attributes:
        method: Scraper method (discriminator)
        config: Method-specific configuration
        metadata: Generation metadata

    Example:
        >>> api_config = APIConfig(
        ...     data_source="example_source",
        ...     data_type="data",
        ...     update_frequency="hourly",
        ...     api_base_url="https://api.example.com"
        ... )
        >>> spec = ScraperSpec(
        ...     method="http_api",
        ...     config=api_config,
        ...     metadata=Metadata(...)
        ... )
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    method: ScraperMethod = Field(..., description="Scraper method")
    config: ScraperConfig = Field(..., discriminator="method", description="Configuration")
    metadata: Metadata = Field(..., description="Generation metadata")

    def validate_spec(self) -> ValidationResult:
        """Validate entire scraper specification.

        Returns:
            ValidationResult combining config validation
        """
        return self.config.validate_config()
