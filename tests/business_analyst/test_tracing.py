"""Tests for the tracing module.

Tests cover:
- should_enable_tracing() decision logic
- prepare_langsmith_env() env var normalization
- build_run_config() config generation
- build_planner_run_config() planner-specific config
- disable_tracing_for_tests() utility
"""

import os
import pytest
from unittest.mock import patch

from agentic_scraper.business_analyst.config import BAConfig
from agentic_scraper.business_analyst.tracing import (
    should_enable_tracing,
    prepare_langsmith_env,
    build_run_config,
    build_planner_run_config,
    disable_tracing_for_tests,
)


class TestShouldEnableTracing:
    """Tests for should_enable_tracing() decision logic."""

    def test_disabled_when_no_api_key(self):
        """Tracing disabled when no API key present."""
        env = {k: v for k, v in os.environ.items() if "LANGSMITH" not in k and "LANGCHAIN" not in k}
        with patch.dict(os.environ, env, clear=True):
            assert should_enable_tracing() is False

    def test_enabled_when_langsmith_key_present(self):
        """Tracing enabled when LANGSMITH_API_KEY present."""
        with patch.dict(os.environ, {"LANGSMITH_API_KEY": "lsv2_test"}, clear=False):
            assert should_enable_tracing() is True

    def test_enabled_when_langchain_key_present(self):
        """Tracing enabled when LANGCHAIN_API_KEY present."""
        env = {k: v for k, v in os.environ.items() if "LANGSMITH_API_KEY" not in k}
        env["LANGCHAIN_API_KEY"] = "lsv2_test"
        with patch.dict(os.environ, env, clear=True):
            assert should_enable_tracing() is True


class TestPrepareLangsmithEnv:
    """Tests for prepare_langsmith_env() env var normalization."""

    def test_bridges_api_key(self):
        """API key bridged between LangSmith and LangChain styles."""
        env = {"LANGSMITH_API_KEY": "test-key-123"}
        with patch.dict(os.environ, env, clear=True):
            prepare_langsmith_env()
            assert os.environ.get("LANGCHAIN_API_KEY") == "test-key-123"

    def test_bridges_project_name(self):
        """Project name bridged and defaults correctly."""
        env = {"LANGSMITH_API_KEY": "test-key", "LANGSMITH_PROJECT": "my-project"}
        with patch.dict(os.environ, env, clear=True):
            prepare_langsmith_env()
            assert os.environ.get("LANGCHAIN_PROJECT") == "my-project"

    def test_sets_default_project_name(self):
        """Default project name set when not specified."""
        env = {"LANGSMITH_API_KEY": "test-key"}
        with patch.dict(os.environ, env, clear=True):
            prepare_langsmith_env()
            assert os.environ.get("LANGSMITH_PROJECT") == "ba-analyst"
            assert os.environ.get("LANGCHAIN_PROJECT") == "ba-analyst"

    def test_enables_tracing_flags(self):
        """Both LANGSMITH_TRACING and LANGCHAIN_TRACING_V2 set."""
        env = {"LANGSMITH_API_KEY": "test-key"}
        with patch.dict(os.environ, env, clear=True):
            prepare_langsmith_env()
            assert os.environ.get("LANGSMITH_TRACING") == "true"
            assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"

    def test_sets_default_endpoint(self):
        """Default endpoint set when not specified."""
        env = {"LANGSMITH_API_KEY": "test-key"}
        with patch.dict(os.environ, env, clear=True):
            prepare_langsmith_env()
            assert os.environ.get("LANGSMITH_ENDPOINT") == "https://api.smith.langchain.com"
            assert os.environ.get("LANGCHAIN_ENDPOINT") == "https://api.smith.langchain.com"


class TestBuildRunConfig:
    """Tests for build_run_config() config generation."""

    def test_sanitized_thread_id(self):
        """Thread ID is sanitized (no raw URL)."""
        config = BAConfig()
        run_config = build_run_config("https://api.example.com/docs?token=secret", config)

        thread_id = run_config["configurable"]["thread_id"]
        assert thread_id.startswith("ba-")
        assert "token=secret" not in thread_id
        assert "https://" not in thread_id

    def test_thread_id_stable(self):
        """Same URL produces same thread_id."""
        config = BAConfig()
        url = "https://api.example.com/docs"

        config1 = build_run_config(url, config)
        config2 = build_run_config(url, config)

        assert config1["configurable"]["thread_id"] == config2["configurable"]["thread_id"]

    def test_run_name_includes_hostname(self):
        """Run name includes hostname."""
        config = BAConfig()
        run_config = build_run_config("https://api.example.com/docs", config)

        assert run_config["run_name"] == "BA Analyze: api.example.com"

    def test_tags_included(self):
        """Standard tags included."""
        config = BAConfig()
        run_config = build_run_config("https://api.example.com/docs", config)

        tags = run_config["tags"]
        assert "component=ba" in tags
        assert "subsystem=langgraph" in tags
        assert "provider=bedrock" in tags

    def test_metadata_includes_key_fields(self):
        """Metadata includes hostname, max_depth, etc."""
        config = BAConfig(max_depth=5, max_steps=100)
        run_config = build_run_config("https://api.example.com/docs", config)

        metadata = run_config["metadata"]
        assert metadata["hostname"] == "api.example.com"
        assert metadata["max_depth"] == 5
        assert metadata["max_steps"] == 100
        assert "recursion_limit" in metadata

    def test_full_url_in_metadata(self):
        """Full URL including query params preserved in metadata."""
        config = BAConfig()
        run_config = build_run_config("https://api.example.com/docs?token=secret&page=1", config)

        metadata = run_config["metadata"]
        assert metadata["seed_url"] == "https://api.example.com/docs?token=secret&page=1"

    def test_recursion_limit_customizable(self):
        """Recursion limit can be customized."""
        config = BAConfig()
        run_config = build_run_config("https://api.example.com", config, recursion_limit=200)

        assert run_config["recursion_limit"] == 200
        assert run_config["metadata"]["recursion_limit"] == 200

    def test_additional_tags_merged(self):
        """Additional tags merged with defaults."""
        config = BAConfig()
        run_config = build_run_config(
            "https://api.example.com",
            config,
            additional_tags=["custom=tag", "env=dev"]
        )

        tags = run_config["tags"]
        assert "component=ba" in tags  # Default
        assert "custom=tag" in tags  # Additional
        assert "env=dev" in tags  # Additional

    def test_additional_metadata_merged(self):
        """Additional metadata merged with defaults."""
        config = BAConfig()
        run_config = build_run_config(
            "https://api.example.com",
            config,
            additional_metadata={"custom_field": "value", "git_sha": "abc123"}
        )

        metadata = run_config["metadata"]
        assert metadata["hostname"] == "api.example.com"  # Default
        assert metadata["custom_field"] == "value"  # Additional
        assert metadata["git_sha"] == "abc123"  # Additional


class TestBuildPlannerRunConfig:
    """Tests for build_planner_run_config() planner-specific config."""

    def test_planner_run_name(self):
        """Planner run name format."""
        config = BAConfig()
        run_config = build_planner_run_config("https://api.example.com", config)

        assert run_config["run_name"] == "Planner: api.example.com"

    def test_planner_tags_include_node(self):
        """Planner tags include node=planner_react."""
        config = BAConfig()
        run_config = build_planner_run_config("https://api.example.com", config)

        assert "node=planner_react" in run_config["tags"]

    def test_planner_thread_id_derived_from_parent(self):
        """Planner thread_id derived from parent when provided."""
        config = BAConfig()
        run_config = build_planner_run_config(
            "https://api.example.com",
            config,
            parent_thread_id="ba-example-abc123"
        )

        thread_id = run_config["configurable"]["thread_id"]
        assert thread_id == "ba-example-abc123-planner"

    def test_planner_thread_id_standalone(self):
        """Planner thread_id generated standalone when no parent."""
        config = BAConfig()
        run_config = build_planner_run_config("https://api.example.com", config)

        thread_id = run_config["configurable"]["thread_id"]
        assert thread_id.startswith("ba-")
        assert thread_id.endswith("-planner")

    def test_planner_full_url_in_metadata(self):
        """Full URL preserved in planner metadata."""
        config = BAConfig()
        run_config = build_planner_run_config("https://api.example.com/docs?token=abc", config)

        metadata = run_config["metadata"]
        assert metadata["seed_url"] == "https://api.example.com/docs?token=abc"


class TestDisableTracingForTests:
    """Tests for disable_tracing_for_tests() utility."""

    def test_disables_langchain_tracing_v2(self):
        """Sets LANGCHAIN_TRACING_V2=false."""
        env = {}
        with patch.dict(os.environ, env, clear=True):
            disable_tracing_for_tests()
            assert os.environ.get("LANGCHAIN_TRACING_V2") == "false"

    def test_disables_langsmith_tracing(self):
        """Sets LANGSMITH_TRACING=false."""
        env = {}
        with patch.dict(os.environ, env, clear=True):
            disable_tracing_for_tests()
            assert os.environ.get("LANGSMITH_TRACING") == "false"
