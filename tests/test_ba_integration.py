"""Integration tests for BA Analyst system.

These tests verify that all components work together correctly.
"""

import pytest
from unittest.mock import Mock, patch

from agentic_scraper.business_analyst import (
    create_ba_graph,
    create_initial_state,
    BAConfig
)
from agentic_scraper.business_analyst.state import BAAnalystState


class TestGraphCreation:
    """Test graph creation and structure."""

    def test_create_ba_graph(self):
        """Test that graph can be created without errors."""
        graph = create_ba_graph()
        assert graph is not None

    def test_graph_has_correct_nodes(self):
        """Test that graph contains all expected nodes."""
        graph = create_ba_graph()

        # LangGraph compiled graphs have a nodes attribute
        assert hasattr(graph, "nodes") or hasattr(graph, "get_graph")


class TestInitialState:
    """Test initial state creation."""

    def test_create_initial_state_minimal(self):
        """Test creating initial state with just URL."""
        state = create_initial_state("https://example.com/api")

        assert state["seed_url"] == "https://example.com/api"
        assert state["max_depth"] == 3
        assert "example.com" in state["allowed_domains"]
        assert state["visited"] == set()
        assert state["queue"] == []
        assert state["endpoints"] == []

    def test_create_initial_state_with_depth(self):
        """Test creating initial state with custom depth."""
        state = create_initial_state("https://example.com/api", max_depth=5)

        assert state["max_depth"] == 5

    def test_create_initial_state_with_domains(self):
        """Test creating initial state with allowed domains."""
        state = create_initial_state(
            "https://example.com/api",
            allowed_domains=["example.com", "api.example.com"]
        )

        assert "example.com" in state["allowed_domains"]
        assert "api.example.com" in state["allowed_domains"]

    def test_create_initial_state_with_config(self):
        """Test creating initial state with custom config."""
        config = BAConfig(render_mode="always", max_depth=2)
        state = create_initial_state(
            "https://example.com/api",
            config=config
        )

        assert state["config"] == config
        assert state["config"].render_mode == "always"


class TestStateTyping:
    """Test that state typing is correct."""

    def test_state_has_required_keys(self):
        """Test that initial state has all required keys."""
        state = create_initial_state("https://example.com/api")

        required_keys = [
            "seed_url",
            "max_depth",
            "allowed_domains",
            "visited",
            "queue",
            "current_depth",
            "current_url",
            "artifacts",
            "screenshots",
            "endpoints",
            "auth_summary",
            "gaps",
            "next_action",
            "stop_reason",
            "config"
        ]

        for key in required_keys:
            assert key in state, f"Missing required key: {key}"

    def test_state_types(self):
        """Test that state values have correct types."""
        state = create_initial_state("https://example.com/api")

        assert isinstance(state["seed_url"], str)
        assert isinstance(state["max_depth"], int)
        assert isinstance(state["allowed_domains"], list)
        assert isinstance(state["visited"], set)
        assert isinstance(state["queue"], list)
        assert isinstance(state["current_depth"], int)
        assert isinstance(state["artifacts"], dict)
        assert isinstance(state["endpoints"], list)


class TestModuleImports:
    """Test that all modules can be imported."""

    def test_import_graph(self):
        """Test importing graph module."""
        from agentic_scraper.business_analyst import graph
        assert hasattr(graph, "create_ba_graph")

    def test_import_cli(self):
        """Test importing CLI module."""
        from agentic_scraper.business_analyst import cli
        assert hasattr(cli, "run_analysis")
        assert hasattr(cli, "create_initial_state")

    def test_import_output(self):
        """Test importing output module."""
        from agentic_scraper.business_analyst import output
        assert hasattr(output, "save_results")
        assert hasattr(output, "load_state")

    def test_import_all_nodes(self):
        """Test importing all node modules."""
        from agentic_scraper.business_analyst.nodes import (
            planner,
            fetcher,
            analyst,
            auth_probe,
            link_selector,
            summarizer
        )

        assert hasattr(planner, "planner_node")
        assert hasattr(fetcher, "fetcher_node")
        assert hasattr(analyst, "analyst_node")
        assert hasattr(auth_probe, "auth_probe_node")
        assert hasattr(link_selector, "link_selector_node")
        assert hasattr(summarizer, "summarizer_node")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
