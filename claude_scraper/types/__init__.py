"""Type definitions and shared models"""

from claude_scraper.types.base import (
    BaseScraperConfig,
    Metadata,
    ValidationResult,
)
from claude_scraper.types.enums import (
    AuthenticationMethod,
    DataFormat,
    ScraperMethod,
    UpdateFrequency,
)
from claude_scraper.types.errors import (
    BAAnalysisError,
    CollationError,
    GenerationError,
    OrchestrationError,
    QATestingError,
    Run1AnalysisError,
    Run2AnalysisError,
)
from claude_scraper.types.scraper_spec import (
    APIConfig,
    EmailConfig,
    FTPConfig,
    HTTPEndpoint,
    ScraperConfig,
    ScraperSpec,
    WebsiteConfig,
    WebsiteSelector,
)

__all__ = [
    # Base models
    "BaseScraperConfig",
    "Metadata",
    "ValidationResult",
    # Enums
    "AuthenticationMethod",
    "DataFormat",
    "ScraperMethod",
    "UpdateFrequency",
    # Scraper specs
    "ScraperSpec",
    "ScraperConfig",
    "APIConfig",
    "FTPConfig",
    "EmailConfig",
    "WebsiteConfig",
    "HTTPEndpoint",
    "WebsiteSelector",
    # Errors
    "OrchestrationError",
    "Run1AnalysisError",
    "Run2AnalysisError",
    "CollationError",
    "QATestingError",
    "BAAnalysisError",
    "GenerationError",
]
