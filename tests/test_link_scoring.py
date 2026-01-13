"""Unit tests for link scoring utilities.

These tests validate the deterministic heuristic scoring logic
in the link_scoring module.
"""

import pytest
from agentic_scraper.business_analyst.utils.link_scoring import (
    score_link_deterministic,
    filter_links_by_domain,
    filter_visited_links,
    score_and_sort_links,
    HIGH_VALUE_KEYWORDS,
    LOW_VALUE_KEYWORDS,
)


class TestScoreLinkDeterministic:
    """Tests for score_link_deterministic function."""

    def test_high_value_keywords_boost_score(self):
        """High-value keywords should increase score."""
        url = "https://api.example.com/docs"
        text = "API Documentation"
        seed_url = "https://api.example.com"
        visited = set()

        score, reason = score_link_deterministic(url, text, seed_url, visited)

        # Base (0.5) + high-value keywords (0.4) = 0.9
        assert score == pytest.approx(0.9)
        assert "high-value keywords" in reason.lower()

    def test_low_value_keywords_reduce_score(self):
        """Low-value keywords should decrease score."""
        url = "https://example.com/about-us"
        text = "About Us"
        seed_url = "https://example.com"
        visited = set()

        score, reason = score_link_deterministic(url, text, seed_url, visited)

        # Base (0.5) + low-value keywords (-0.5) = 0.0
        assert score == pytest.approx(0.0)
        assert "low-value keywords" in reason.lower()

    def test_off_domain_reduces_score(self):
        """Off-domain links should decrease score."""
        url = "https://external.com/api"
        text = "External API"
        seed_url = "https://example.com"
        visited = set()

        score, reason = score_link_deterministic(url, text, seed_url, visited)

        # Base (0.5) + high-value (0.4) + off-domain (-0.3) = 0.6
        assert score == pytest.approx(0.6)
        assert "off-domain" in reason.lower()

    def test_visited_link_returns_negative_one(self):
        """Already visited links should return -1.0."""
        url = "https://example.com/docs"
        text = "Documentation"
        seed_url = "https://example.com"
        visited = {url}

        score, reason = score_link_deterministic(url, text, seed_url, visited)

        assert score == -1.0
        assert "already visited" in reason.lower()

    def test_same_domain_keeps_score_neutral(self):
        """Same domain links should not get domain penalty."""
        url = "https://example.com/page"
        text = "Some Page"
        seed_url = "https://example.com"
        visited = set()

        score, reason = score_link_deterministic(url, text, seed_url, visited)

        # Base (0.5) only, no keywords matched
        assert score == pytest.approx(0.5)
        assert "same domain" in reason.lower()

    def test_combined_signals(self):
        """Test multiple signals combined."""
        # High-value keyword + same domain
        url = "https://api.example.com/openapi.json"
        text = "OpenAPI Specification"
        seed_url = "https://api.example.com"
        visited = set()

        score, reason = score_link_deterministic(url, text, seed_url, visited)

        # Base (0.5) + high-value (0.4) = 0.9
        assert score == pytest.approx(0.9)
        assert "high-value" in reason.lower()


class TestFilterLinksByDomain:
    """Tests for filter_links_by_domain function."""

    def test_filters_to_seed_domain_when_no_allowed_domains(self):
        """Should only allow seed domain when allowed_domains is empty."""
        links = [
            {"url": "https://example.com/page1"},
            {"url": "https://external.com/page2"},
            {"url": "https://example.com/page3"},
        ]
        allowed_domains = []
        seed_url = "https://example.com"

        filtered = filter_links_by_domain(links, allowed_domains, seed_url)

        assert len(filtered) == 2
        assert all("example.com" in link["url"] for link in filtered)

    def test_filters_to_allowed_domains(self):
        """Should only allow specified domains."""
        links = [
            {"url": "https://example.com/page1"},
            {"url": "https://api.example.com/page2"},
            {"url": "https://external.com/page3"},
        ]
        allowed_domains = ["example.com", "api.example.com"]
        seed_url = "https://example.com"

        filtered = filter_links_by_domain(links, allowed_domains, seed_url)

        assert len(filtered) == 2
        assert not any("external.com" in link["url"] for link in filtered)


class TestFilterVisitedLinks:
    """Tests for filter_visited_links function."""

    def test_removes_visited_links(self):
        """Should remove links that are in visited set."""
        links = [
            {"url": "https://example.com/page1"},
            {"url": "https://example.com/page2"},
            {"url": "https://example.com/page3"},
        ]
        visited = {"https://example.com/page2"}

        filtered = filter_visited_links(links, visited)

        assert len(filtered) == 2
        assert not any(link["url"] == "https://example.com/page2" for link in filtered)

    def test_keeps_unvisited_links(self):
        """Should keep all links when visited set is empty."""
        links = [
            {"url": "https://example.com/page1"},
            {"url": "https://example.com/page2"},
        ]
        visited = set()

        filtered = filter_visited_links(links, visited)

        assert len(filtered) == 2


class TestScoreAndSortLinks:
    """Tests for score_and_sort_links function."""

    def test_scores_and_sorts_by_score_descending(self):
        """Should score all links and sort by score descending."""
        links = [
            {"url": "https://api.example.com/about", "text": "About Us"},
            {"url": "https://api.example.com/docs", "text": "API Docs"},
            {"url": "https://api.example.com/data", "text": "Data Downloads"},
        ]
        seed_url = "https://api.example.com"
        visited = set()

        scored = score_and_sort_links(links, seed_url, visited, min_score=0.0)

        # Should be sorted by score descending
        assert len(scored) == 3
        assert scored[0]["heuristic_score"] >= scored[1]["heuristic_score"]
        assert scored[1]["heuristic_score"] >= scored[2]["heuristic_score"]

        # API Docs should be highest
        assert "docs" in scored[0]["url"]

    def test_filters_below_minimum_score(self):
        """Should filter out links below minimum score."""
        links = [
            {"url": "https://example.com/api", "text": "API Docs"},
            {"url": "https://example.com/about", "text": "About Us"},
        ]
        seed_url = "https://example.com"
        visited = set()
        min_score = 0.5

        scored = score_and_sort_links(links, seed_url, visited, min_score=min_score)

        # "About Us" should be filtered out (score ~0.0)
        assert len(scored) == 1
        assert "api" in scored[0]["url"]

    def test_adds_heuristic_score_and_reason(self):
        """Should add heuristic_score and reason to each link."""
        links = [
            {"url": "https://example.com/api", "text": "API Docs"},
        ]
        seed_url = "https://example.com"
        visited = set()

        scored = score_and_sort_links(links, seed_url, visited, min_score=0.0)

        assert len(scored) == 1
        assert "heuristic_score" in scored[0]
        assert "reason" in scored[0]
        assert isinstance(scored[0]["heuristic_score"], float)
        assert isinstance(scored[0]["reason"], str)


class TestKeywordSets:
    """Tests for keyword constant sets."""

    def test_high_value_keywords_exist(self):
        """HIGH_VALUE_KEYWORDS should contain expected terms."""
        assert "api" in HIGH_VALUE_KEYWORDS
        assert "docs" in HIGH_VALUE_KEYWORDS
        assert "openapi" in HIGH_VALUE_KEYWORDS
        assert "data" in HIGH_VALUE_KEYWORDS

    def test_low_value_keywords_exist(self):
        """LOW_VALUE_KEYWORDS should contain expected terms."""
        assert "about" in LOW_VALUE_KEYWORDS
        assert "careers" in LOW_VALUE_KEYWORDS
        assert "privacy" in LOW_VALUE_KEYWORDS
        assert "contact" in LOW_VALUE_KEYWORDS

    def test_no_overlap_between_keyword_sets(self):
        """High and low value keywords should not overlap."""
        overlap = HIGH_VALUE_KEYWORDS.intersection(LOW_VALUE_KEYWORDS)
        assert len(overlap) == 0
