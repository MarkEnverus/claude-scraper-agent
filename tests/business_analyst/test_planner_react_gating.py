"""Unit tests for planner_react URL gating logic."""
import pytest
from agentic_scraper.business_analyst.nodes.planner_react import url_key, extract_artifacts_from_messages, parse_agent_decision
from langchain_core.messages import ToolMessage


class TestURLCanonicalization:
    """Test URL canonicalization for comparison."""

    def test_lowercase_scheme_netloc(self):
        """Scheme and netloc should be lowercased."""
        url = "HTTPS://Data-Exchange.MISOEnergy.org/api-details"
        expected = "https://data-exchange.misoenergy.org/api-details"
        assert url_key(url) == expected

    def test_preserve_meaningful_fragment(self):
        """Fragments with api= should be preserved."""
        url = "https://data-exchange.misoenergy.org/api-details#api=pricing-api"
        result = url_key(url)
        assert "#api=pricing-api" in result

    def test_drop_meaningless_fragment(self):
        """Fragments without api= should be dropped."""
        url = "https://portal.spp.org/page#section-intro"
        result = url_key(url)
        assert "#" not in result

    def test_strip_trailing_slash(self):
        """Trailing slashes should be removed."""
        url = "https://portal.spp.org/groups/integrated-marketplace/"
        expected = "https://portal.spp.org/groups/integrated-marketplace"
        assert url_key(url) == expected

    def test_preserve_case_in_path(self):
        """Path case should be preserved (server-dependent)."""
        url = "https://example.com/API/Details"
        result = url_key(url)
        assert "/API/Details" in result  # Not lowercased


class TestAllowedURLComputation:
    """Test allowed URL set computation."""

    def test_excludes_analyzed_urls(self):
        """Analyzed URLs should not be in allowed set."""
        from agentic_scraper.business_analyst.nodes.planner_react import url_key

        state = {
            "queue": [
                {"url": "https://example.com/page1"},
                {"url": "https://example.com/page2"},
            ],
            "analyzed_urls": {"https://example.com/page1"},
            "seed_url": "https://example.com/home"
        }
        # Compute allowed (pseudo-code for what Step 2 does)
        analyzed_keys = {url_key(u) for u in state["analyzed_urls"]}
        queue_candidates = [
            item["url"] for item in state["queue"]
            if url_key(item["url"]) not in analyzed_keys
        ]
        assert len(queue_candidates) == 1
        assert queue_candidates[0] == "https://example.com/page2"


class TestBlockedToolResultHandling:
    """Test that blocked tool results don't create artifacts."""

    def test_blocked_render_no_artifact(self):
        """Blocked render should not create PageArtifact."""
        blocked_msg = ToolMessage(
            content={
                "blocked": True,
                "url": "https://example.com/page",
                "reason": "already_analyzed"
            },
            name="render_page_with_js",
            tool_call_id="123"
        )

        # Call extract_artifacts_from_messages with blocked message
        result = extract_artifacts_from_messages([blocked_msg], {})

        # Should not create artifacts
        assert len(result["artifacts"]) == 0
        assert len(result["visited"]) == 0

    def test_blocked_render_returns_continue(self):
        """parse_agent_decision should return continue for blocked render."""
        blocked_msg = ToolMessage(
            content={
                "blocked": True,
                "url": "https://example.com/page",
                "reason": "already_analyzed"
            },
            name="render_page_with_js",
            tool_call_id="123"
        )

        decision = parse_agent_decision([blocked_msg], {})

        assert decision["action"] == "continue"
        assert decision["url"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
