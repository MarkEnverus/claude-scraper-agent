"""Validation configuration for code generation."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationConfig:
    """Configuration for code validation.

    This class controls the behavior of the validation system including
    strictness levels, performance settings, and retry behavior.
    """

    # Strictness levels
    strict_mode: bool = True  # Fail on critical errors
    allow_warnings: bool = True  # Don't fail on warnings
    report_info: bool = False  # Report info-level messages

    # Performance settings
    enable_mypy: bool = False  # Run mypy type checking (disabled by default for speed)
    enable_ast: bool = True  # Run AST analysis
    enable_integration_tests: bool = False  # Run integration tests (slow)

    # Retry settings
    max_retries: int = 2  # Max retry attempts
    retry_with_feedback: bool = True  # Feed errors back to AI

    # Caching
    cache_validation_results: bool = True
    cache_ttl_seconds: int = 3600

    # Timeout limits
    validation_timeout_seconds: int = 30
    mypy_timeout_seconds: int = 10

    @classmethod
    def from_environment(cls) -> "ValidationConfig":
        """Load configuration from environment variables.

        Environment variables:
            VALIDATION_ENABLED: Enable/disable validation (default: true)
            VALIDATION_STRICT_MODE: Fail on critical errors (default: true)
            VALIDATION_ENABLE_MYPY: Run mypy type checking (default: false)
            VALIDATION_MAX_RETRIES: Maximum retry attempts (default: 2)

        Returns:
            ValidationConfig instance with environment overrides
        """
        # Check if validation is completely disabled
        if os.getenv("VALIDATION_ENABLED", "true").lower() == "false":
            return cls.disabled()

        return cls(
            strict_mode=os.getenv("VALIDATION_STRICT_MODE", "true").lower() == "true",
            enable_mypy=os.getenv("VALIDATION_ENABLE_MYPY", "false").lower() == "true",
            enable_ast=os.getenv("VALIDATION_ENABLE_AST", "true").lower() == "true",
            max_retries=int(os.getenv("VALIDATION_MAX_RETRIES", "2")),
        )

    @classmethod
    def development(cls) -> "ValidationConfig":
        """Development environment - fast, permissive.

        Optimized for rapid iteration:
        - No mypy (fast)
        - AST only (fast)
        - Single retry
        - Permissive mode (warnings only)

        Returns:
            ValidationConfig for development
        """
        return cls(
            strict_mode=False,
            enable_mypy=False,
            enable_ast=True,
            enable_integration_tests=False,
            max_retries=1,
        )

    @classmethod
    def production(cls) -> "ValidationConfig":
        """Production environment - thorough, strict.

        Optimized for quality:
        - Full type checking with mypy
        - AST analysis
        - Integration tests
        - Strict mode (fail on errors)
        - Multiple retries

        Returns:
            ValidationConfig for production
        """
        return cls(
            strict_mode=True,
            enable_mypy=True,
            enable_ast=True,
            enable_integration_tests=True,
            max_retries=2,
        )

    @classmethod
    def disabled(cls) -> "ValidationConfig":
        """Completely disabled validation.

        Use this for:
        - Emergency rollback
        - Debugging validation issues
        - Testing without validation overhead

        Returns:
            ValidationConfig with all validation disabled
        """
        return cls(
            strict_mode=False,
            enable_mypy=False,
            enable_ast=False,
            enable_integration_tests=False,
            max_retries=0,
            retry_with_feedback=False,
        )

    def is_enabled(self) -> bool:
        """Check if validation is enabled.

        Returns:
            True if any validation checks are enabled
        """
        return self.enable_ast or self.enable_mypy or self.enable_integration_tests
