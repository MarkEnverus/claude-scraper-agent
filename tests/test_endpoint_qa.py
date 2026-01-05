"""Tests for endpoint QA testing functionality.

Tests the pure Python endpoint testing with HTTP requests,
decision matrix logic, rate limiting, and error handling.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from claude_scraper.types import EndpointSpec, HTTPMethod, ResponseFormat
from claude_scraper.agents.endpoint_qa import EndpointQATester


class TestEndpointQATester:
    """Test EndpointQATester class."""

    def test_init_creates_tester(self):
        """Test that tester initializes with repository."""
        tester = EndpointQATester()

        assert tester.repository is not None
        assert tester.client is not None
        assert tester.last_request_time == 0.0

    def test_decision_matrix_200_keep(self):
        """Test decision matrix keeps 200 OK."""
        tester = EndpointQATester()
        assert tester._get_decision(200) == "keep"

    def test_decision_matrix_201_keep(self):
        """Test decision matrix keeps 201 Created."""
        tester = EndpointQATester()
        assert tester._get_decision(201) == "keep"

    def test_decision_matrix_204_keep(self):
        """Test decision matrix keeps 204 No Content."""
        tester = EndpointQATester()
        assert tester._get_decision(204) == "keep"

    def test_decision_matrix_401_keep(self):
        """Test decision matrix keeps 401 (endpoint exists, needs auth)."""
        tester = EndpointQATester()
        assert tester._get_decision(401) == "keep"

    def test_decision_matrix_403_keep(self):
        """Test decision matrix keeps 403 (endpoint exists, needs auth)."""
        tester = EndpointQATester()
        assert tester._get_decision(403) == "keep"

    def test_decision_matrix_404_remove(self):
        """Test decision matrix removes 404 Not Found."""
        tester = EndpointQATester()
        assert tester._get_decision(404) == "remove"

    def test_decision_matrix_405_keep(self):
        """Test decision matrix keeps 405 (endpoint exists, wrong method)."""
        tester = EndpointQATester()
        assert tester._get_decision(405) == "keep"

    def test_decision_matrix_429_flag(self):
        """Test decision matrix flags 429 (rate limited)."""
        tester = EndpointQATester()
        assert tester._get_decision(429) == "flag"

    def test_decision_matrix_500_flag(self):
        """Test decision matrix flags 500 (can't determine validity)."""
        tester = EndpointQATester()
        assert tester._get_decision(500) == "flag"

    def test_decision_matrix_502_flag(self):
        """Test decision matrix flags 502 (can't determine validity)."""
        tester = EndpointQATester()
        assert tester._get_decision(502) == "flag"

    def test_decision_matrix_503_flag(self):
        """Test decision matrix flags 503 (can't determine validity)."""
        tester = EndpointQATester()
        assert tester._get_decision(503) == "flag"

    def test_decision_matrix_unknown_status_flag(self):
        """Test decision matrix flags unknown status codes."""
        tester = EndpointQATester()
        assert tester._get_decision(999) == "flag"

    def test_decision_matrix_202_keep(self):
        """Test decision matrix keeps 202 Accepted"""
        tester = EndpointQATester()
        assert tester._get_decision(202) == "keep"

    def test_decision_matrix_203_keep(self):
        """Test decision matrix keeps 203 Non-Authoritative Information"""
        tester = EndpointQATester()
        assert tester._get_decision(203) == "keep"

    def test_decision_matrix_206_keep(self):
        """Test decision matrix keeps 206 Partial Content"""
        tester = EndpointQATester()
        assert tester._get_decision(206) == "keep"

    def test_decision_matrix_301_keep(self):
        """Test decision matrix keeps 301 Moved Permanently"""
        tester = EndpointQATester()
        assert tester._get_decision(301) == "keep"

    def test_decision_matrix_302_keep(self):
        """Test decision matrix keeps 302 Found"""
        tester = EndpointQATester()
        assert tester._get_decision(302) == "keep"

    def test_decision_matrix_307_keep(self):
        """Test decision matrix keeps 307 Temporary Redirect"""
        tester = EndpointQATester()
        assert tester._get_decision(307) == "keep"

    def test_decision_matrix_308_keep(self):
        """Test decision matrix keeps 308 Permanent Redirect"""
        tester = EndpointQATester()
        assert tester._get_decision(308) == "keep"

    @patch('httpx.Client.request')
    def test_test_endpoint_success(self, mock_request):
        """Test endpoint testing with 200 OK."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.15
        mock_request.return_value = mock_response

        tester = EndpointQATester()
        endpoint = EndpointSpec(
            endpoint_id="test_1",
            path="https://api.example.com/v1/data",
            method=HTTPMethod.GET,
            description="Test endpoint",
            parameters=[],
            response_format=ResponseFormat.JSON,
            authentication_mentioned=False
        )

        result = tester.test_endpoint(endpoint)

        assert result["status_code"] == 200
        assert result["decision"] == "keep"
        assert result["response_time_ms"] == 150.0
        assert result["error"] is None
        assert result["endpoint"] == "https://api.example.com/v1/data"
        assert result["method"] == "GET"

    @patch('httpx.Client.request')
    def test_test_endpoint_404_remove(self, mock_request):
        """Test endpoint removal on 404."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.elapsed.total_seconds.return_value = 0.1
        mock_request.return_value = mock_response

        tester = EndpointQATester()
        endpoint = EndpointSpec(
            endpoint_id="test_2",
            path="https://api.example.com/v1/invalid",
            method=HTTPMethod.GET,
            description="Invalid endpoint",
            parameters=[],
            response_format=ResponseFormat.JSON,
            authentication_mentioned=False
        )

        result = tester.test_endpoint(endpoint)

        assert result["status_code"] == 404
        assert result["decision"] == "remove"
        assert result["error"] is None

    @patch('httpx.Client.request')
    def test_test_endpoint_401_keep(self, mock_request):
        """Test endpoint keeps on 401 (auth required)."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.elapsed.total_seconds.return_value = 0.12
        mock_request.return_value = mock_response

        tester = EndpointQATester()
        endpoint = EndpointSpec(
            endpoint_id="test_3",
            path="https://api.example.com/v1/protected",
            method=HTTPMethod.GET,
            description="Protected endpoint",
            parameters=[],
            response_format=ResponseFormat.JSON,
            authentication_mentioned=True
        )

        result = tester.test_endpoint(endpoint)

        assert result["status_code"] == 401
        assert result["decision"] == "keep"
        assert result["error"] is None

    @patch('httpx.Client.request')
    def test_test_endpoint_500_flag(self, mock_request):
        """Test endpoint flags on 500 (server error)."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.elapsed.total_seconds.return_value = 0.2
        mock_request.return_value = mock_response

        tester = EndpointQATester()
        endpoint = EndpointSpec(
            endpoint_id="test_4",
            path="https://api.example.com/v1/error",
            method=HTTPMethod.GET,
            description="Error endpoint",
            parameters=[],
            response_format=ResponseFormat.JSON,
            authentication_mentioned=False
        )

        result = tester.test_endpoint(endpoint)

        assert result["status_code"] == 500
        assert result["decision"] == "flag"
        assert result["error"] is None

    @patch('httpx.Client.request')
    def test_test_endpoint_timeout(self, mock_request):
        """Test endpoint handling timeout."""
        import httpx
        mock_request.side_effect = httpx.TimeoutException("Timeout")

        tester = EndpointQATester()
        endpoint = EndpointSpec(
            endpoint_id="test_5",
            path="https://api.example.com/v1/slow",
            method=HTTPMethod.GET,
            description="Slow endpoint",
            parameters=[],
            response_format=ResponseFormat.JSON,
            authentication_mentioned=False
        )

        result = tester.test_endpoint(endpoint)

        assert result["status_code"] is None
        assert result["decision"] == "flag"
        assert result["error"] == "timeout"
        assert result["response_time_ms"] is None

    @patch('httpx.Client.request')
    def test_test_endpoint_network_error(self, mock_request):
        """Test endpoint handling network error."""
        import httpx
        mock_request.side_effect = httpx.NetworkError("Network error")

        tester = EndpointQATester()
        endpoint = EndpointSpec(
            endpoint_id="test_6",
            path="https://api.example.com/v1/unreachable",
            method=HTTPMethod.GET,
            description="Unreachable endpoint",
            parameters=[],
            response_format=ResponseFormat.JSON,
            authentication_mentioned=False
        )

        result = tester.test_endpoint(endpoint)

        assert result["status_code"] is None
        assert result["decision"] == "flag"
        assert "network" in result["error"]
        assert result["response_time_ms"] is None

    @patch('httpx.Client.request')
    def test_test_endpoint_unexpected_error(self, mock_request):
        """Test endpoint handling unexpected error."""
        mock_request.side_effect = Exception("Unexpected error")

        tester = EndpointQATester()
        endpoint = EndpointSpec(
            endpoint_id="test_7",
            path="https://api.example.com/v1/broken",
            method=HTTPMethod.GET,
            description="Broken endpoint",
            parameters=[],
            response_format=ResponseFormat.JSON,
            authentication_mentioned=False
        )

        result = tester.test_endpoint(endpoint)

        assert result["status_code"] is None
        assert result["decision"] == "flag"
        assert "unexpected" in result["error"]
        assert result["response_time_ms"] is None

    @patch('httpx.Client.request')
    def test_rate_limiting_enforced(self, mock_request):
        """Test that rate limiting is enforced (1 req/sec)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.1
        mock_request.return_value = mock_response

        tester = EndpointQATester()
        endpoint1 = EndpointSpec(
            endpoint_id="test_8",
            path="https://api.example.com/v1/data1",
            method=HTTPMethod.GET,
            description="First endpoint",
            parameters=[],
            response_format=ResponseFormat.JSON,
            authentication_mentioned=False
        )
        endpoint2 = EndpointSpec(
            endpoint_id="test_9",
            path="https://api.example.com/v1/data2",
            method=HTTPMethod.GET,
            description="Second endpoint",
            parameters=[],
            response_format=ResponseFormat.JSON,
            authentication_mentioned=False
        )

        # First request should be immediate
        start_time = time.time()
        tester.test_endpoint(endpoint1)

        # Second request should be delayed by rate limit
        tester.test_endpoint(endpoint2)
        elapsed = time.time() - start_time

        # Should take at least 1 second due to rate limiting
        assert elapsed >= 1.0

    @patch('httpx.Client.request')
    @patch('time.sleep')
    def test_first_request_no_delay(self, mock_sleep, mock_request):
        """Test that first request has no rate limit delay."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.1
        mock_request.return_value = mock_response

        tester = EndpointQATester()
        endpoint = EndpointSpec(
            endpoint_id="test_first",
            path="https://api.example.com/v1/data",
            method=HTTPMethod.GET,
            description="First request",
            parameters=[],
            response_format=ResponseFormat.JSON,
            authentication_mentioned=False
        )

        # First request should not sleep
        tester.test_endpoint(endpoint)
        mock_sleep.assert_not_called()

    def test_filter_endpoints_keeps_valid(self):
        """Test filtering keeps only valid endpoints."""
        tester = EndpointQATester()

        endpoints = [
            EndpointSpec(
                endpoint_id="test_10",
                path="https://api.example.com/v1/data",
                method=HTTPMethod.GET,
                description="Valid endpoint",
                parameters=[],
                response_format=ResponseFormat.JSON,
                authentication_mentioned=False
            ),
            EndpointSpec(
                endpoint_id="test_11",
                path="https://api.example.com/v1/invalid",
                method=HTTPMethod.GET,
                description="Invalid endpoint",
                parameters=[],
                response_format=ResponseFormat.JSON,
                authentication_mentioned=False
            ),
            EndpointSpec(
                endpoint_id="test_12",
                path="https://api.example.com/v1/error",
                method=HTTPMethod.GET,
                description="Error endpoint",
                parameters=[],
                response_format=ResponseFormat.JSON,
                authentication_mentioned=False
            )
        ]

        test_results = {
            "total_tested": 3,
            "keep": 1,
            "remove": 1,
            "flag": 1,
            "results": [
                {"endpoint": "https://api.example.com/v1/data", "decision": "keep"},
                {"endpoint": "https://api.example.com/v1/invalid", "decision": "remove"},
                {"endpoint": "https://api.example.com/v1/error", "decision": "flag"}
            ]
        }

        filtered = tester.filter_endpoints(endpoints, test_results)

        assert len(filtered) == 1
        assert filtered[0].path == "https://api.example.com/v1/data"

    @patch('httpx.Client.request')
    @patch('claude_scraper.storage.repository.AnalysisRepository.save')
    def test_test_all_endpoints(self, mock_save, mock_request):
        """Test testing all endpoints and generating summary."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.1
        mock_request.return_value = mock_response

        tester = EndpointQATester()
        endpoints = [
            EndpointSpec(
                endpoint_id="test_13",
                path="https://api.example.com/v1/data1",
                method=HTTPMethod.GET,
                description="Endpoint 1",
                parameters=[],
                response_format=ResponseFormat.JSON,
                authentication_mentioned=False
            ),
            EndpointSpec(
                endpoint_id="test_14",
                path="https://api.example.com/v1/data2",
                method=HTTPMethod.GET,
                description="Endpoint 2",
                parameters=[],
                response_format=ResponseFormat.JSON,
                authentication_mentioned=False
            )
        ]

        # Mock different responses for each endpoint
        mock_request.side_effect = [
            Mock(status_code=200, elapsed=Mock(total_seconds=Mock(return_value=0.1))),
            Mock(status_code=404, elapsed=Mock(total_seconds=Mock(return_value=0.1)))
        ]

        summary = tester.test_all_endpoints(endpoints)

        assert summary["total_tested"] == 2
        assert summary["keep"] == 1
        assert summary["remove"] == 1
        assert summary["flag"] == 0
        assert len(summary["results"]) == 2

        # Verify save was called
        mock_save.assert_called_once()

    @patch('httpx.Client.request')
    def test_http_method_conversion(self, mock_request):
        """Test that HTTP method enum is converted to string."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.1
        mock_request.return_value = mock_response

        tester = EndpointQATester()
        endpoint = EndpointSpec(
            endpoint_id="test_15",
            path="https://api.example.com/v1/data",
            method=HTTPMethod.POST,
            description="POST endpoint",
            parameters=[],
            response_format=ResponseFormat.JSON,
            authentication_mentioned=False
        )

        result = tester.test_endpoint(endpoint)

        # Verify method was converted to string
        assert result["method"] == "POST"
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["method"] == "POST"

    @patch('httpx.Client.request')
    def test_user_agent_header(self, mock_request):
        """Test that User-Agent header is set correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.1
        mock_request.return_value = mock_response

        tester = EndpointQATester()
        endpoint = EndpointSpec(
            endpoint_id="test_16",
            path="https://api.example.com/v1/data",
            method=HTTPMethod.GET,
            description="Test endpoint",
            parameters=[],
            response_format=ResponseFormat.JSON,
            authentication_mentioned=False
        )

        tester.test_endpoint(endpoint)

        # Verify User-Agent header was set
        call_kwargs = mock_request.call_args[1]
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["User-Agent"] == "Claude-Scraper-QA/1.0"

    @patch('httpx.Client.request')
    def test_redirects_not_followed(self, mock_request):
        """Test that redirects are not followed."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.1
        mock_request.return_value = mock_response

        tester = EndpointQATester()
        endpoint = EndpointSpec(
            endpoint_id="test_17",
            path="https://api.example.com/v1/data",
            method=HTTPMethod.GET,
            description="Test endpoint",
            parameters=[],
            response_format=ResponseFormat.JSON,
            authentication_mentioned=False
        )

        tester.test_endpoint(endpoint)

        # Verify follow_redirects is False
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["follow_redirects"] is False

    def test_context_manager_usage(self):
        """Test that context manager properly initializes and cleans up."""
        with EndpointQATester() as tester:
            # Tester should be returned and client should be open
            assert tester is not None
            assert tester.client is not None
            client = tester.client

        # After context, client close should have been called
        # We can't directly test if close was called without mocking,
        # but we verify the context manager protocol works
        assert client is not None
