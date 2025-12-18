"""Pure Python endpoint QA testing with HTTP requests.

This module provides endpoint testing functionality using HTTP requests
and a deterministic decision matrix. NO LLM calls are made.

The decision matrix maps HTTP status codes to actions:
- 200/201/204/401/403/405: keep (endpoint exists)
- 404: remove (endpoint does not exist)
- 429/500/502/503: flag (cannot determine validity)

Rate limiting: 1 request per second
Timeout: 10 seconds per request

Example:
    >>> from baml_client.types import EndpointSpec, HTTPMethod, ResponseFormat
    >>> from claude_scraper.agents.endpoint_qa import EndpointQATester
    >>>
    >>> tester = EndpointQATester()
    >>> endpoint = EndpointSpec(
    ...     endpoint_id="test_1",
    ...     path="https://api.example.com/v1/data",
    ...     method=HTTPMethod.GET,
    ...     description="Test endpoint",
    ...     parameters=[],
    ...     response_format=ResponseFormat.JSON,
    ...     authentication_mentioned=False
    ... )
    >>> result = tester.test_endpoint(endpoint)
    >>> print(result["decision"])  # "keep", "remove", or "flag"
"""

import httpx
import time
import logging
from typing import Literal

from baml_client.baml_client.types import EndpointSpec
from claude_scraper.storage.repository import AnalysisRepository

logger = logging.getLogger(__name__)

# Decision type for endpoint QA
EndpointDecision = Literal["keep", "remove", "flag"]


class EndpointQATester:
    """Pure Python endpoint testing with HTTP requests.

    Tests endpoints using HTTP requests and applies a deterministic
    decision matrix based on response status codes. No LLM calls.

    Recommended usage with context manager:

        with EndpointQATester() as tester:
            results = tester.test_all_endpoints(endpoints)

    This ensures proper cleanup of HTTP client resources.

    Attributes:
        RATE_LIMIT_DELAY: Delay between requests (1 second)
        REQUEST_TIMEOUT: HTTP request timeout (10 seconds)
        DECISION_MATRIX: Maps status codes to decisions
        repository: File repository for storing results
        client: HTTP client for making requests
        last_request_time: Timestamp of last request for rate limiting

    Example:
        >>> tester = EndpointQATester()
        >>> results = tester.test_all_endpoints(endpoints)
        >>> print(f"Kept: {results['keep']}, Removed: {results['remove']}")
    """

    # Rate limiting: 1 request per second per plan
    RATE_LIMIT_DELAY = 1.0
    REQUEST_TIMEOUT = 10.0

    # Decision matrix (HTTP status code -> action)
    DECISION_MATRIX = {
        200: "keep",      # Success - endpoint valid
        201: "keep",      # Created - endpoint valid
        202: "keep",      # Accepted - async processing, endpoint valid
        203: "keep",      # Non-Authoritative Information - endpoint valid
        204: "keep",      # No content - endpoint valid
        206: "keep",      # Partial Content - endpoint valid
        301: "keep",      # Moved Permanently - endpoint exists, redirects
        302: "keep",      # Found - endpoint exists, redirects
        307: "keep",      # Temporary Redirect - endpoint exists, redirects
        308: "keep",      # Permanent Redirect - endpoint exists, redirects
        401: "keep",      # Unauthorized - endpoint exists, needs auth
        403: "keep",      # Forbidden - endpoint exists, needs auth
        404: "remove",    # Not found - invalid endpoint
        405: "keep",      # Method not allowed - endpoint exists, wrong method
        429: "flag",      # Rate limited - can't determine validity
        500: "flag",      # Server error - can't determine validity
        502: "flag",      # Bad gateway - can't determine validity
        503: "flag",      # Service unavailable - can't determine validity
    }

    def __init__(self, repository: AnalysisRepository | None = None) -> None:
        """Initialize endpoint QA tester.

        Args:
            repository: Optional repository for storing results.
                       Defaults to AnalysisRepository()

        Example:
            >>> tester = EndpointQATester()
            >>> custom_repo = AnalysisRepository("custom_dir")
            >>> tester_custom = EndpointQATester(repository=custom_repo)
        """
        self.repository = repository or AnalysisRepository()
        self.client = httpx.Client(timeout=self.REQUEST_TIMEOUT)
        self.last_request_time = 0.0

    def __del__(self) -> None:
        """Clean up HTTP client."""
        try:
            self.client.close()
        except Exception:
            pass  # Ignore cleanup errors

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - clean up resources."""
        self.client.close()
        return False

    def _enforce_rate_limit(self) -> None:
        """Enforce 1 request per second rate limiting.

        Sleeps if necessary to maintain rate limit.
        """
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)

    def test_endpoint(self, endpoint: EndpointSpec) -> dict:
        """Test a single endpoint and return results.

        Makes HTTP request to endpoint and applies decision matrix
        based on response status code.

        Args:
            endpoint: EndpointSpec to test

        Returns:
            Dictionary with test results:
                - endpoint: str - endpoint path
                - method: str - HTTP method
                - status_code: int | None - response status code
                - decision: EndpointDecision - keep/remove/flag
                - response_time_ms: float | None - response time
                - error: str | None - error message if request failed

        Example:
            >>> endpoint = EndpointSpec(
            ...     endpoint_id="test_1",
            ...     path="https://api.example.com/v1/data",
            ...     method=HTTPMethod.GET,
            ...     description="Test",
            ...     parameters=[],
            ...     response_format=ResponseFormat.JSON,
            ...     authentication_mentioned=False
            ... )
            >>> result = tester.test_endpoint(endpoint)
            >>> print(result["decision"])
        """
        self._enforce_rate_limit()

        # Set timestamp immediately before making request
        self.last_request_time = time.time()

        logger.info(f"Testing endpoint: {endpoint.method} {endpoint.path}")

        try:
            response = self.client.request(
                method=endpoint.method.value,  # Convert enum to string
                url=endpoint.path,
                headers={"User-Agent": "Claude-Scraper-QA/1.0"},
                follow_redirects=False
            )

            status_code = response.status_code
            decision = self._get_decision(status_code)

            logger.info(f"  Status: {status_code} -> Decision: {decision}")

            return {
                "endpoint": endpoint.path,
                "method": endpoint.method.value,
                "status_code": status_code,
                "decision": decision,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "error": None
            }

        except httpx.TimeoutException:
            logger.warning(f"  Timeout testing {endpoint.path}")
            return {
                "endpoint": endpoint.path,
                "method": endpoint.method.value,
                "status_code": None,
                "decision": "flag",
                "response_time_ms": None,
                "error": "timeout"
            }
        except httpx.NetworkError as e:
            logger.warning(f"  Network error: {e}")
            return {
                "endpoint": endpoint.path,
                "method": endpoint.method.value,
                "status_code": None,
                "decision": "flag",
                "response_time_ms": None,
                "error": f"network: {e}"
            }
        except Exception as e:
            logger.error(f"  Unexpected error: {e}")
            return {
                "endpoint": endpoint.path,
                "method": endpoint.method.value,
                "status_code": None,
                "decision": "flag",
                "response_time_ms": None,
                "error": f"unexpected: {e}"
            }

    def _get_decision(self, status_code: int) -> EndpointDecision:
        """Get decision from status code using decision matrix.

        Args:
            status_code: HTTP response status code

        Returns:
            EndpointDecision: "keep", "remove", or "flag"

        Example:
            >>> tester = EndpointQATester()
            >>> tester._get_decision(200)
            'keep'
            >>> tester._get_decision(404)
            'remove'
            >>> tester._get_decision(500)
            'flag'
        """
        decision = self.DECISION_MATRIX.get(status_code)

        if decision is None:
            logger.warning(
                f"Unknown HTTP status code {status_code} encountered - flagging for review",
                extra={"status_code": status_code}
            )
            return "flag"

        return decision

    def test_all_endpoints(self, endpoints: list[EndpointSpec]) -> dict:
        """Test all endpoints and return summary.

        Tests each endpoint sequentially with rate limiting and
        generates summary statistics. Saves results to repository.

        Args:
            endpoints: List of EndpointSpec objects to test

        Returns:
            Dictionary with summary:
                - total_tested: int - number of endpoints tested
                - keep: int - number of endpoints to keep
                - remove: int - number of endpoints to remove
                - flag: int - number of endpoints flagged
                - results: list[dict] - individual test results

        Example:
            >>> endpoints = [endpoint1, endpoint2, endpoint3]
            >>> summary = tester.test_all_endpoints(endpoints)
            >>> print(f"Kept {summary['keep']} of {summary['total_tested']}")
        """
        logger.info(f"Testing {len(endpoints)} endpoints")

        results = []
        for endpoint in endpoints:
            result = self.test_endpoint(endpoint)
            results.append(result)

        # Generate summary
        summary = {
            "total_tested": len(endpoints),
            "keep": sum(1 for r in results if r["decision"] == "keep"),
            "remove": sum(1 for r in results if r["decision"] == "remove"),
            "flag": sum(1 for r in results if r["decision"] == "flag"),
            "results": results
        }

        # Save results
        self.repository.save("endpoint_qa_results.json", summary)

        logger.info(
            f"QA complete: {summary['keep']} kept, "
            f"{summary['remove']} removed, {summary['flag']} flagged"
        )

        return summary

    def filter_endpoints(
        self,
        endpoints: list[EndpointSpec],
        test_results: dict
    ) -> list[EndpointSpec]:
        """Filter endpoints based on QA test results.

        Returns only endpoints with "keep" decision from test results.

        Args:
            endpoints: Original list of endpoints
            test_results: Test results from test_all_endpoints()

        Returns:
            Filtered list containing only endpoints marked as "keep"

        Example:
            >>> endpoints = [endpoint1, endpoint2, endpoint3]
            >>> results = tester.test_all_endpoints(endpoints)
            >>> valid_endpoints = tester.filter_endpoints(endpoints, results)
            >>> print(f"Filtered {len(endpoints)} -> {len(valid_endpoints)}")
        """
        # Create lookup of path -> decision
        decisions = {
            r["endpoint"]: r["decision"]
            for r in test_results["results"]
        }

        # Keep only endpoints with "keep" decision
        filtered = []
        for e in endpoints:
            decision = decisions.get(e.path)

            if decision == "keep":
                filtered.append(e)
            elif decision is None:
                # Endpoint was not in test results - this is unexpected
                logger.warning(
                    f"Endpoint not found in test results: {e.path}",
                    extra={"endpoint": e.path, "method": e.method}
                )
                # Conservative: exclude endpoints that weren't tested
            # "remove" and "flag" decisions are silently excluded

        logger.info(f"Filtered {len(endpoints)} -> {len(filtered)} endpoints")
        return filtered
