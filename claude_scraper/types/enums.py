"""Enumerations for scraper specifications.

All enums provide a display_name property for human-readable output
in logs, UIs, and documentation.

Example:
    >>> method = ScraperMethod.HTTP_API
    >>> print(method.value)  # "http_api"
    >>> print(method.display_name)  # "HTTP/REST API"
"""

from enum import Enum

# Module-level display name mappings (avoid enum metaclass issues)
_SCRAPER_METHOD_NAMES = {
    "http_api": "HTTP/REST API",
    "website_parser": "Website Parsing",
    "ftp_client": "FTP/SFTP Client",
    "email_collector": "Email Attachments",
}

_DATA_FORMAT_NAMES = {
    "json": "JSON",
    "csv": "CSV",
    "xml": "XML",
    "html": "HTML",
    "binary": "Binary",
    "parquet": "Parquet",
    "unknown": "Unknown",
}

_AUTH_METHOD_NAMES = {
    "none": "None",
    "api_key": "API Key",
    "bearer_token": "Bearer Token",
    "oauth": "OAuth 2.0",
    "basic_auth": "Basic Auth",
    "cookie": "Cookie-based",
    "unknown": "Unknown",
}

_UPDATE_FREQUENCY_NAMES = {
    "realtime": "Real-time",
    "every_5_minutes": "Every 5 minutes",
    "hourly": "Hourly",
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
}


class ScraperMethod(str, Enum):
    """Scraper collection methods.

    Each value has a programmatic name and human-readable display name.

    Example:
        >>> method = ScraperMethod.HTTP_API
        >>> print(method.value)  # "http_api"
        >>> print(method.display_name)  # "HTTP/REST API"
        >>> assert method == "http_api"  # String comparison works
    """

    HTTP_API = "http_api"
    WEBSITE_PARSER = "website_parser"
    FTP_CLIENT = "ftp_client"
    EMAIL_COLLECTOR = "email_collector"

    @property
    def display_name(self) -> str:
        """Get human-readable display name.

        Returns:
            Display name for UI/logs

        Example:
            >>> ScraperMethod.HTTP_API.display_name
            'HTTP/REST API'
        """
        return _SCRAPER_METHOD_NAMES[self.value]


class DataFormat(str, Enum):
    """Data format types with auto-selection logic.

    JSON is preferred when multiple formats available.
    Preference order: JSON > CSV > XML > Parquet > HTML > Binary > Unknown

    Example:
        >>> fmt = DataFormat.auto_select(["xml", "json", "csv"])
        >>> assert fmt == DataFormat.JSON
        >>> print(fmt.display_name)  # "JSON"
    """

    JSON = "json"
    CSV = "csv"
    XML = "xml"
    HTML = "html"
    BINARY = "binary"
    PARQUET = "parquet"
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        """Get display name."""
        return _DATA_FORMAT_NAMES[self.value]

    @classmethod
    def auto_select(cls, available_formats: list[str]) -> "DataFormat":
        """Auto-select best format from available options.

        Preference order: JSON > CSV > XML > others

        Args:
            available_formats: List of format strings (case-insensitive)

        Returns:
            Best DataFormat from available options

        Example:
            >>> DataFormat.auto_select(["XML", "csv", "JSON"])
            DataFormat.JSON
            >>> DataFormat.auto_select(["xml", "csv"])
            DataFormat.CSV
            >>> DataFormat.auto_select(["unknown_format"])
            DataFormat.UNKNOWN
        """
        # Filter out None and non-string values, then normalize
        normalized = []
        for f in available_formats:
            if isinstance(f, str):
                normalized.append(f.lower().strip())

        # Preference order
        if "json" in normalized:
            return cls.JSON
        elif "csv" in normalized:
            return cls.CSV
        elif "xml" in normalized:
            return cls.XML
        elif "parquet" in normalized:
            return cls.PARQUET
        elif "html" in normalized:
            return cls.HTML
        elif "binary" in normalized or "bin" in normalized:
            return cls.BINARY
        else:
            return cls.UNKNOWN


class AuthenticationMethod(str, Enum):
    """Authentication methods for data sources."""

    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    OAUTH = "oauth"
    BASIC_AUTH = "basic_auth"
    COOKIE = "cookie"
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        """Get display name."""
        return _AUTH_METHOD_NAMES[self.value]


class UpdateFrequency(str, Enum):
    """Update frequency for data collection."""

    REALTIME = "realtime"
    EVERY_5_MINUTES = "every_5_minutes"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

    @property
    def display_name(self) -> str:
        """Get display name."""
        return _UPDATE_FREQUENCY_NAMES[self.value]
