"""Base models for scraper specifications.

This module defines the abstract base classes and shared data structures
used across all scraper configurations. All method-specific configs
(APIConfig, WebsiteConfig, etc.) inherit from BaseScraperConfig.

Example:
    >>> from claude_scraper.types.base import BaseScraperConfig, ValidationResult
    >>> class MyConfig(BaseScraperConfig):
    ...     def validate_config(self) -> ValidationResult:
    ...         return ValidationResult(is_valid=True, errors=[], warnings=[])
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class ValidationResult(BaseModel):
    """Result of validation operation.

    Attributes:
        is_valid: Whether validation passed
        errors: List of error messages (validation failures)
        warnings: List of warning messages (potential issues)

    Example:
        >>> result = ValidationResult(
        ...     is_valid=False,
        ...     errors=["URL format invalid"],
        ...     warnings=["Rate limit not specified"]
        ... )
        >>> if not result.is_valid:
        ...     print(f"Errors: {result.errors}")
    """

    model_config = ConfigDict(frozen=True)

    is_valid: bool = Field(..., description="Validation passed")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")


class Metadata(BaseModel):
    """Generation metadata for scrapers.

    Tracks versions, dates, and generator agent for change management.

    Attributes:
        scraper_version: Version of scraper generator plugin
        infrastructure_version: Version of collection framework
        generated_date: Date scraper was generated (YYYY-MM-DD)
        last_updated: Date scraper was last modified (YYYY-MM-DD)
        generator_agent: Name of generator agent used

    Example:
        >>> metadata = Metadata(
        ...     scraper_version="1.11.0",
        ...     infrastructure_version="1.11.0",
        ...     generated_date="2025-12-19",
        ...     last_updated="2025-12-19",
        ...     generator_agent="scraper-generator:http-collector"
        ... )
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    scraper_version: str = Field(..., description="Scraper plugin version")
    infrastructure_version: str = Field(..., description="Framework version")
    generated_date: str = Field(..., description="Generation date (YYYY-MM-DD)")
    last_updated: str = Field(..., description="Last update date (YYYY-MM-DD)")
    generator_agent: str = Field(..., description="Generator agent name")


class BaseScraperConfig(BaseModel, ABC):
    """Abstract base for all scraper configurations.

    All method-specific configs inherit from this and must
    implement the validate_config() method.

    Attributes:
        data_source: Name of data source (e.g., "NYISO", "MISO")
        data_type: Type of data (e.g., "load_forecast", "price_actual")
        update_frequency: How often data updates (e.g., "hourly", "daily")
        historical_support: Whether historical data is available
        authentication: Authentication method description

    Example:
        >>> class APIConfig(BaseScraperConfig):
        ...     api_base_url: str
        ...     def validate_config(self) -> ValidationResult:
        ...         return ValidationResult(is_valid=True, errors=[], warnings=[])
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    data_source: str = Field(..., min_length=1, description="Data source name")
    data_type: str = Field(..., min_length=1, description="Data type identifier")
    update_frequency: str = Field(..., description="Update frequency")
    historical_support: bool = Field(default=False, description="Historical data available")
    authentication: str = Field(default="None", description="Authentication method")

    @abstractmethod
    def validate_config(self) -> ValidationResult:
        """Validate config for completeness and correctness.

        Returns:
            ValidationResult with is_valid, errors, warnings
        """
        pass
