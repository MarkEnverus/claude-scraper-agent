"""Unit tests for BA Analyst tools.

Tests the LangChain tool wrappers for Botasaurus and HTTP utilities.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from agentic_scraper.business_analyst.tools import (
    render_page_with_js,
    extract_links,
    capture_network_events,
    interact_and_capture,
    http_get_headers,
    http_get_robots,
)


class TestRenderPageWithJs:
    """Tests for render_page_with_js tool."""

    @patch("agentic_scraper.business_analyst.tools.BotasaurusTool")
    def test_successful_extraction(self, mock_botasaurus_cls):
        """Test successful comprehensive data extraction."""
        # Arrange
        mock_bot = Mock()
        mock_botasaurus_cls.return_value = mock_bot

        expected_data = {
            "full_text": "Sample page content",
            "markdown": "# Sample\nContent here",
            "navigation_links": [
                {"text": "API Docs", "href": "https://example.com/docs", "className": "nav-link", "source": "nav"}
            ],
            "network_events": [
                {"url": "https://api.example.com/v1/data", "initiator_type": "fetch", "trigger": "page_load"}
            ],
            "expanded_sections": 5,
            "screenshot": "datasource_analysis/page_screenshot.png",
            "extraction_error": None
        }
        mock_bot.extract_comprehensive_data.return_value = expected_data

        # Act
        result = render_page_with_js.invoke({"url": "https://example.com"})

        # Assert
        assert result == expected_data
        mock_bot.extract_comprehensive_data.assert_called_once_with("https://example.com")

    @patch("agentic_scraper.business_analyst.tools.BotasaurusTool")
    def test_extraction_error(self, mock_botasaurus_cls):
        """Test error handling during extraction."""
        # Arrange
        mock_bot = Mock()
        mock_botasaurus_cls.return_value = mock_bot
        mock_bot.extract_comprehensive_data.side_effect = RuntimeError("Browser crashed")

        # Act
        result = render_page_with_js.invoke({"url": "https://example.com"})

        # Assert
        assert result["extraction_error"] == "Browser crashed"
        assert result["full_text"] == ""
        assert result["navigation_links"] == []
        assert result["network_events"] == []

    @patch("agentic_scraper.business_analyst.tools.BotasaurusTool")
    def test_with_wait_for_selector(self, mock_botasaurus_cls):
        """Test extraction with wait_for selector."""
        # Arrange
        mock_bot = Mock()
        mock_botasaurus_cls.return_value = mock_bot
        mock_bot.extract_comprehensive_data.return_value = {
            "full_text": "Content",
            "markdown": "# Content",
            "navigation_links": [],
            "network_events": [],
            "expanded_sections": 0,
            "screenshot": None,
            "extraction_error": None
        }

        # Act
        result = render_page_with_js.invoke({
            "url": "https://example.com",
            "wait_for": ".api-section"
        })

        # Assert
        assert result["extraction_error"] is None
        mock_bot.extract_comprehensive_data.assert_called_once_with("https://example.com")


class TestExtractLinks:
    """Tests for extract_links tool."""

    @patch("agentic_scraper.business_analyst.tools.BotasaurusTool")
    def test_successful_link_extraction(self, mock_botasaurus_cls):
        """Test successful link extraction."""
        # Arrange
        mock_bot = Mock()
        mock_botasaurus_cls.return_value = mock_bot

        expected_links = [
            {"text": "API Docs", "href": "https://example.com/docs", "className": "nav-link", "source": "nav"},
            {"text": "Download", "href": "https://example.com/download", "className": "button", "source": "main"}
        ]
        mock_bot.extract_comprehensive_data.return_value = {
            "navigation_links": expected_links,
            "full_text": "...",
            "markdown": "...",
            "network_events": [],
            "expanded_sections": 0,
            "screenshot": None,
            "extraction_error": None
        }

        # Act
        result = extract_links.invoke({"url": "https://example.com"})

        # Assert
        assert result == expected_links
        assert len(result) == 2
        assert result[0]["text"] == "API Docs"

    @patch("agentic_scraper.business_analyst.tools.BotasaurusTool")
    def test_extraction_error_returns_empty_list(self, mock_botasaurus_cls):
        """Test error handling returns empty list."""
        # Arrange
        mock_bot = Mock()
        mock_botasaurus_cls.return_value = mock_bot
        mock_bot.extract_comprehensive_data.side_effect = RuntimeError("Network timeout")

        # Act
        result = extract_links.invoke({"url": "https://example.com"})

        # Assert
        assert result == []


class TestCaptureNetworkEvents:
    """Tests for capture_network_events tool."""

    @patch("agentic_scraper.business_analyst.tools.BotasaurusTool")
    def test_successful_network_capture(self, mock_botasaurus_cls):
        """Test successful network event capture."""
        # Arrange
        mock_bot = Mock()
        mock_botasaurus_cls.return_value = mock_bot

        expected_events = [
            {"url": "https://api.example.com/v1/users", "initiator_type": "fetch", "trigger": "page_load"},
            {"url": "https://api.example.com/v1/data", "initiator_type": "xmlhttprequest", "trigger": "page_load"},
            {"url": "https://cdn.example.com/config.json", "initiator_type": "fetch", "trigger": "page_load"},
        ]
        mock_bot.extract_network_events.return_value = expected_events

        # Act
        result = capture_network_events.invoke({"url": "https://example.com"})

        # Assert
        assert result == expected_events
        assert len(result) == 3
        mock_bot.extract_network_events.assert_called_once_with("https://example.com")

    @patch("agentic_scraper.business_analyst.tools.BotasaurusTool")
    def test_network_capture_error(self, mock_botasaurus_cls):
        """Test error handling returns empty list."""
        # Arrange
        mock_bot = Mock()
        mock_botasaurus_cls.return_value = mock_bot
        mock_bot.extract_network_events.side_effect = Exception("CDP disconnected")

        # Act
        result = capture_network_events.invoke({"url": "https://example.com"})

        # Assert
        assert result == []


class TestInteractAndCapture:
    """Tests for interact_and_capture tool (E1)."""

    @patch("agentic_scraper.business_analyst.tools.BotasaurusTool")
    def test_successful_interaction(self, mock_botasaurus_cls):
        """Test successful UI interaction and network capture."""
        # Arrange
        mock_bot = Mock()
        mock_botasaurus_cls.return_value = mock_bot

        expected_result = {
            "network_events": [
                {"url": "https://api.example.com/search?q=test", "initiator_type": "fetch", "trigger": "interaction_script"}
            ],
            "actions_executed": 2,
            "errors": [],
            "markdown": "# Search Results"
        }
        mock_bot.interact_and_capture.return_value = expected_result

        # Act
        result = interact_and_capture.invoke({
            "url": "https://example.com",
            "actions": [
                {"action": "type", "selector": "#search-input", "text": "test"},
                {"action": "click", "selector": "#search-btn"}
            ]
        })

        # Assert
        assert result == expected_result
        assert result["actions_executed"] == 2
        assert len(result["network_events"]) == 1
        assert result["network_events"][0]["trigger"] == "interaction_script"

    @patch("agentic_scraper.business_analyst.tools.BotasaurusTool")
    def test_interaction_with_errors(self, mock_botasaurus_cls):
        """Test interaction that partially fails."""
        # Arrange
        mock_bot = Mock()
        mock_botasaurus_cls.return_value = mock_bot

        expected_result = {
            "network_events": [],
            "actions_executed": 1,
            "errors": ["Action 2 (click) failed: Element not found"],
            "markdown": "# Page Content"
        }
        mock_bot.interact_and_capture.return_value = expected_result

        # Act
        result = interact_and_capture.invoke({
            "url": "https://example.com",
            "actions": [
                {"action": "type", "selector": "#search", "text": "test"},
                {"action": "click", "selector": "#nonexistent"}
            ]
        })

        # Assert
        assert result["actions_executed"] == 1
        assert len(result["errors"]) == 1
        assert "Element not found" in result["errors"][0]

    @patch("agentic_scraper.business_analyst.tools.BotasaurusTool")
    def test_interaction_error_returns_safe_default(self, mock_botasaurus_cls):
        """Test that errors return safe default structure."""
        # Arrange
        mock_bot = Mock()
        mock_botasaurus_cls.return_value = mock_bot
        mock_bot.interact_and_capture.side_effect = RuntimeError("Browser crashed")

        # Act
        result = interact_and_capture.invoke({
            "url": "https://example.com",
            "actions": [{"action": "click", "selector": "#btn"}]
        })

        # Assert
        assert result["network_events"] == []
        assert result["actions_executed"] == 0
        assert "Browser crashed" in result["errors"][0]
        assert result["markdown"] == ""

    @patch("agentic_scraper.business_analyst.tools.BotasaurusTool")
    def test_wait_action(self, mock_botasaurus_cls):
        """Test wait action."""
        # Arrange
        mock_bot = Mock()
        mock_botasaurus_cls.return_value = mock_bot

        expected_result = {
            "network_events": [],
            "actions_executed": 1,
            "errors": [],
            "markdown": ""
        }
        mock_bot.interact_and_capture.return_value = expected_result

        # Act
        result = interact_and_capture.invoke({
            "url": "https://example.com",
            "actions": [{"action": "wait", "value": 2000}]
        })

        # Assert
        assert result["actions_executed"] == 1
        mock_bot.interact_and_capture.assert_called_once()


class TestHttpGetHeaders:
    """Tests for http_get_headers tool."""

    @patch("agentic_scraper.business_analyst.tools.httpx.Client")
    def test_successful_head_request(self, mock_client_cls):
        """Test successful HEAD request."""
        # Arrange
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json", "Server": "nginx"}
        mock_response.url = "https://example.com"
        mock_client.head.return_value = mock_response

        # Act
        result = http_get_headers.invoke({"url": "https://example.com"})

        # Assert
        assert result["status_code"] == 200
        assert result["headers"]["content-type"] == "application/json"
        assert result["redirected_to"] is None
        assert result["error"] is None

    @patch("agentic_scraper.business_analyst.tools.httpx.Client")
    def test_redirect_detected(self, mock_client_cls):
        """Test redirect detection."""
        # Arrange
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Location": "https://example.com/login"}
        mock_response.url = "https://example.com/login"  # Redirected URL
        mock_client.head.return_value = mock_response

        # Act
        result = http_get_headers.invoke({"url": "https://example.com"})

        # Assert
        assert result["redirected_to"] == "https://example.com/login"

    @patch("agentic_scraper.business_analyst.tools.httpx.Client")
    def test_auth_required_detection(self, mock_client_cls):
        """Test 401 and WWW-Authenticate header detection."""
        # Arrange
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.headers = {"WWW-Authenticate": "Bearer"}
        mock_response.url = "https://api.example.com"
        mock_client.head.return_value = mock_response

        # Act
        result = http_get_headers.invoke({"url": "https://api.example.com"})

        # Assert
        assert result["status_code"] == 401
        assert result["headers"]["www-authenticate"] == "Bearer"

    @patch("agentic_scraper.business_analyst.tools.httpx.Client")
    def test_network_error(self, mock_client_cls):
        """Test network error handling."""
        # Arrange
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.head.side_effect = Exception("Connection timeout")

        # Act
        result = http_get_headers.invoke({"url": "https://example.com"})

        # Assert
        assert result["status_code"] == 0
        assert result["error"] == "Connection timeout"


class TestHttpGetRobots:
    """Tests for http_get_robots tool."""

    @patch("agentic_scraper.business_analyst.tools.httpx.Client")
    def test_successful_robots_fetch(self, mock_client_cls):
        """Test successful robots.txt fetch and parse."""
        # Arrange
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        robots_content = """User-agent: *
Disallow: /admin/
Disallow: /private/
Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/sitemap-news.xml
"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = robots_content
        mock_client.get.return_value = mock_response

        # Act
        result = http_get_robots.invoke({"url": "https://example.com/any/path"})

        # Assert
        assert result["content"] == robots_content
        assert "/admin/" in result["disallowed_paths"]
        assert "/private/" in result["disallowed_paths"]
        assert len(result["sitemaps"]) == 2
        assert "https://example.com/sitemap.xml" in result["sitemaps"]
        assert result["error"] is None

    @patch("agentic_scraper.business_analyst.tools.httpx.Client")
    def test_robots_not_found(self, mock_client_cls):
        """Test robots.txt not found (404)."""
        # Arrange
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        mock_response = Mock()
        mock_response.status_code = 404
        mock_client.get.return_value = mock_response

        # Act
        result = http_get_robots.invoke({"url": "https://example.com"})

        # Assert
        assert result["error"] == "HTTP 404"
        assert result["content"] == ""
        assert result["disallowed_paths"] == []

    @patch("agentic_scraper.business_analyst.tools.httpx.Client")
    def test_empty_robots_file(self, mock_client_cls):
        """Test empty robots.txt file."""
        # Arrange
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_client.get.return_value = mock_response

        # Act
        result = http_get_robots.invoke({"url": "https://example.com"})

        # Assert
        assert result["content"] == ""
        assert result["disallowed_paths"] == []
        assert result["sitemaps"] == []
        assert result["error"] is None

    @patch("agentic_scraper.business_analyst.tools.httpx.Client")
    def test_robots_url_construction(self, mock_client_cls):
        """Test robots.txt URL is correctly constructed from any URL."""
        # Arrange
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_client.get.return_value = mock_response

        # Act
        http_get_robots.invoke({"url": "https://api.example.com/v1/docs/endpoint"})

        # Assert
        mock_client.get.assert_called_once_with("https://api.example.com/robots.txt")

    @patch("agentic_scraper.business_analyst.tools.httpx.Client")
    def test_network_error(self, mock_client_cls):
        """Test network error handling."""
        # Arrange
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = Exception("DNS resolution failed")

        # Act
        result = http_get_robots.invoke({"url": "https://example.com"})

        # Assert
        assert result["error"] == "DNS resolution failed"
        assert result["content"] == ""


class TestToolIntegration:
    """Integration tests for tool interactions."""

    @patch("agentic_scraper.business_analyst.tools.BotasaurusTool")
    def test_tools_are_langchain_compatible(self, mock_botasaurus_cls):
        """Test that tools work with LangChain's .invoke() method."""
        # Arrange
        mock_bot = Mock()
        mock_botasaurus_cls.return_value = mock_bot
        mock_bot.extract_comprehensive_data.return_value = {
            "full_text": "Test",
            "markdown": "# Test",
            "navigation_links": [],
            "network_events": [],
            "expanded_sections": 0,
            "screenshot": None,
            "extraction_error": None
        }

        # Act - use LangChain's .invoke() syntax
        result = render_page_with_js.invoke({"url": "https://example.com"})

        # Assert
        assert isinstance(result, dict)
        assert "full_text" in result

    def test_tool_has_proper_metadata(self):
        """Test that tools have proper LangChain metadata."""
        # All tools should have name and description
        assert render_page_with_js.name == "render_page_with_js"
        assert render_page_with_js.description is not None
        assert len(render_page_with_js.description) > 50

        assert extract_links.name == "extract_links"
        assert extract_links.description is not None

        assert capture_network_events.name == "capture_network_events"
        assert capture_network_events.description is not None

        assert http_get_headers.name == "http_get_headers"
        assert http_get_headers.description is not None

        assert http_get_robots.name == "http_get_robots"
        assert http_get_robots.description is not None

        assert interact_and_capture.name == "interact_and_capture"
        assert interact_and_capture.description is not None
        assert "UI interactions" in interact_and_capture.description
