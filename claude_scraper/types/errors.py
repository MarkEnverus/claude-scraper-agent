"""Custom exception classes for orchestration errors.

This module defines exception classes used throughout the orchestration
pipeline to provide more specific error handling and context preservation.

Example:
    >>> from claude_scraper.types.errors import Run1AnalysisError
    >>> try:
    ...     # Run 1 analysis code
    ...     raise Exception("Phase 0 failed")
    ... except Exception as e:
    ...     raise Run1AnalysisError(f"Run 1 failed: {e}") from e
"""


class OrchestrationError(Exception):
    """Base exception for all orchestration errors.

    This is the base class for all custom exceptions raised during
    the BA analysis pipeline orchestration. It allows catching all
    orchestration-related errors with a single exception type.

    Attributes:
        message: Error message describing what went wrong
        url: Optional URL being analyzed when error occurred
        phase: Optional phase name where error occurred

    Example:
        >>> try:
        ...     # orchestration code
        ... except OrchestrationError as e:
        ...     logger.error(f"Orchestration failed: {e}")
    """

    def __init__(self, message: str, url: str | None = None, phase: str | None = None):
        """Initialize orchestration error.

        Args:
            message: Error message
            url: Optional URL being analyzed
            phase: Optional phase where error occurred
        """
        self.message = message
        self.url = url
        self.phase = phase
        super().__init__(message)

    def __str__(self) -> str:
        """String representation with context."""
        parts = [self.message]
        if self.url:
            parts.append(f"url={self.url}")
        if self.phase:
            parts.append(f"phase={self.phase}")
        return " | ".join(parts)


class Run1AnalysisError(OrchestrationError):
    """Run 1 analysis failed.

    Raised when any phase of Run 1 analysis fails (Phase 0-3 or validation).
    This indicates a critical failure in the initial analysis pass.

    Example:
        >>> raise Run1AnalysisError(
        ...     "Phase 0 detection failed",
        ...     url="https://api.example.com",
        ...     phase="phase0"
        ... )
    """

    pass


class Run2AnalysisError(OrchestrationError):
    """Run 2 analysis failed.

    Raised when any phase of Run 2 analysis fails. This is less critical
    than Run1AnalysisError since Run 1 has already completed, but it means
    the focused re-analysis could not improve the results.

    Example:
        >>> raise Run2AnalysisError(
        ...     "Phase 1 re-analysis failed",
        ...     url="https://api.example.com",
        ...     phase="phase1"
        ... )
    """

    pass


class CollationError(OrchestrationError):
    """Collation of Run 1 + Run 2 failed.

    Raised when the BACollator fails to merge Run 1 and Run 2 results
    into a final specification.

    Example:
        >>> raise CollationError("Failed to merge specifications")
    """

    pass


class QATestingError(OrchestrationError):
    """Endpoint QA testing failed.

    Raised when the EndpointQATester fails to test endpoints in the
    final specification.

    Example:
        >>> raise QATestingError("Failed to test endpoints")
    """

    pass


class BAAnalysisError(OrchestrationError):
    """BA Analyzer failed during analysis.

    Raised when the BA Analyzer fails to analyze a URL or produce
    a validated datasource specification.

    Example:
        >>> raise BAAnalysisError(
        ...     "BA Analyzer failed to detect endpoints",
        ...     url="https://api.example.com"
        ... )
    """

    pass


class GenerationError(OrchestrationError):
    """Scraper generation failed.

    Raised when scraper generation fails after BA analysis succeeds.
    This could be due to template rendering errors, validation failures,
    or file I/O issues.

    Example:
        >>> raise GenerationError("Template rendering failed for HTTP scraper")
    """

    pass
