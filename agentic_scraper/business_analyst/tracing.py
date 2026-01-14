"""LangSmith Tracing Module for BA Analyst.

This module provides centralized control over LangSmith/LangChain tracing:
- Tracing auto-enables when API key is present in environment
- Version-proof env var bridging (LangSmith + LangChain style)
- Run config builder (tags, metadata, thread_id, run_name)

Usage:
    from agentic_scraper.business_analyst.tracing import (
        should_enable_tracing,
        prepare_langsmith_env,
        build_run_config,
    )

    if should_enable_tracing():
        prepare_langsmith_env()
        run_config = build_run_config(seed_url, config)
        graph.invoke(state, config={**graph_config, **run_config})
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from agentic_scraper.business_analyst.config import BAConfig

logger = logging.getLogger(__name__)

# Default project name if not set in env
DEFAULT_PROJECT_NAME = "ba-analyst"


def should_enable_tracing() -> bool:
    """Determine if LangSmith tracing should be enabled.

    Tracing is enabled when a LangSmith API key is present in environment.

    Returns:
        True if tracing should be enabled, False otherwise

    Example:
        >>> os.environ["LANGSMITH_API_KEY"] = "lsv2_..."
        >>> should_enable_tracing()
        True
    """
    # Check for API key (either LangSmith or LangChain style)
    api_key = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")

    if not api_key:
        logger.info(
            "LangSmith tracing disabled: no API key found. "
            "Set LANGSMITH_API_KEY or LANGCHAIN_API_KEY to enable tracing."
        )
        return False

    logger.debug("Tracing enabled: API key present")
    return True


def prepare_langsmith_env() -> None:
    """Normalize environment variables for LangSmith/LangChain tracing.

    This ensures both LangSmith-style and LangChain-style env vars are set
    consistently, which is critical because different versions/components
    of the LangChain ecosystem honor different env var names.

    Bridged env vars:
    - LANGSMITH_PROJECT <-> LANGCHAIN_PROJECT
    - LANGSMITH_ENDPOINT <-> LANGCHAIN_ENDPOINT
    - LANGSMITH_API_KEY <-> LANGCHAIN_API_KEY
    - LANGSMITH_TRACING=true <-> LANGCHAIN_TRACING_V2=true

    Note:
        This should only be called after should_enable_tracing() returns True.
        It modifies os.environ for the current process.
    """
    # Bridge API key
    api_key = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
    if api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", api_key)
        os.environ.setdefault("LANGCHAIN_API_KEY", api_key)

    # Bridge endpoint
    endpoint = os.environ.get("LANGSMITH_ENDPOINT") or os.environ.get("LANGCHAIN_ENDPOINT")
    if endpoint:
        os.environ.setdefault("LANGSMITH_ENDPOINT", endpoint)
        os.environ.setdefault("LANGCHAIN_ENDPOINT", endpoint)
    else:
        # Default to LangSmith cloud endpoint
        default_endpoint = "https://api.smith.langchain.com"
        os.environ.setdefault("LANGSMITH_ENDPOINT", default_endpoint)
        os.environ.setdefault("LANGCHAIN_ENDPOINT", default_endpoint)

    # Bridge project name
    project = (
        os.environ.get("LANGSMITH_PROJECT")
        or os.environ.get("LANGCHAIN_PROJECT")
        or DEFAULT_PROJECT_NAME
    )
    os.environ["LANGSMITH_PROJECT"] = project
    os.environ["LANGCHAIN_PROJECT"] = project

    # Enable tracing (both styles)
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"

    logger.info(f"LangSmith tracing configured: project={project}")


def _sanitize_url_for_id(url: str) -> str:
    """Create a sanitized, deterministic identifier from a URL.

    The raw URL should not be used directly as thread_id because:
    1. URLs can be very long
    2. Special characters may cause issues

    This creates a short, stable hash-based identifier.

    Args:
        url: Raw URL to sanitize

    Returns:
        Sanitized identifier like "data-exchange.misoenergy.org-a1b2c3d4"
    """
    parsed = urlparse(url)
    hostname = parsed.netloc.replace(":", "-").replace(".", "-")

    # Create short hash of full URL for uniqueness
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]

    return f"{hostname}-{url_hash}"


def _extract_hostname(url: str) -> str:
    """Extract hostname from URL for display purposes.

    Args:
        url: URL to parse

    Returns:
        Hostname portion (e.g., "data-exchange.misoenergy.org")
    """
    parsed = urlparse(url)
    return parsed.netloc or "unknown"


def build_run_config(
    seed_url: str,
    config: BAConfig,
    recursion_limit: int = 150,
    additional_tags: list[str] | None = None,
    additional_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build configuration dict for LangGraph/LangChain invoke.

    Creates a standardized run configuration with:
    - Sanitized thread_id (short hash-based)
    - Human-friendly run_name
    - Consistent tags (component, subsystem, provider)
    - Rich metadata (seed_url, hostname, config values)

    Args:
        seed_url: The seed URL being analyzed
        config: BAConfig instance
        recursion_limit: LangGraph recursion limit (default: 150)
        additional_tags: Extra tags to include
        additional_metadata: Extra metadata to include

    Returns:
        Dict suitable for merging into graph.invoke() config:
        {
            "configurable": {"thread_id": "ba-..."},
            "recursion_limit": 150,
            "tags": [...],
            "metadata": {...},
            "run_name": "BA Analyze: ..."
        }

    Example:
        >>> config = BAConfig()
        >>> run_config = build_run_config("https://api.example.com/docs", config)
        >>> final_state = graph.invoke(initial_state, config=run_config)
    """
    hostname = _extract_hostname(seed_url)
    sanitized_id = _sanitize_url_for_id(seed_url)

    # Build thread_id
    thread_id = f"ba-{sanitized_id}"

    # Build run_name (human-friendly)
    run_name = f"BA Analyze: {hostname}"

    # Build tags
    tags = [
        "component=ba",
        "subsystem=langgraph",
        "provider=bedrock",
    ]
    if additional_tags:
        tags.extend(additional_tags)

    # Build metadata - include full URL for visibility
    metadata: dict[str, Any] = {
        "seed_url": seed_url,
        "hostname": hostname,
        "max_depth": config.max_depth,
        "max_steps": config.max_steps,
        "recursion_limit": recursion_limit,
        "render_mode": config.render_mode,
        "model_fast": config.model_fast,
        "model_reasoning": config.model_reasoning,
        "model_vision": config.model_vision,
    }

    # Add optional package version if available
    try:
        from importlib.metadata import version
        metadata["package_version"] = version("agentic-scraper")
    except Exception:
        pass

    if additional_metadata:
        metadata.update(additional_metadata)

    return {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": recursion_limit,
        "tags": tags,
        "metadata": metadata,
        "run_name": run_name,
    }


def build_planner_run_config(
    seed_url: str,
    config: BAConfig,
    parent_thread_id: str | None = None,
) -> dict[str, Any]:
    """Build run configuration for planner agent invocation.

    Similar to build_run_config but specialized for the planner ReAct agent.
    Aligns with the parent run context for proper trace hierarchy.

    Args:
        seed_url: The seed URL being analyzed
        config: BAConfig instance
        parent_thread_id: Thread ID from parent graph run (for alignment)

    Returns:
        Dict suitable for agent.invoke() config

    Example:
        >>> planner_config = build_planner_run_config(seed_url, config, parent_thread_id)
        >>> result = agent.invoke({"messages": [...]}, config=planner_config)
    """
    hostname = _extract_hostname(seed_url)

    # Use parent thread_id if provided, otherwise create aligned child ID
    if parent_thread_id:
        # Derive child thread_id from parent for trace alignment
        thread_id = f"{parent_thread_id}-planner"
    else:
        sanitized_id = _sanitize_url_for_id(seed_url)
        thread_id = f"ba-{sanitized_id}-planner"

    run_name = f"Planner: {hostname}"

    tags = [
        "component=ba",
        "subsystem=langgraph",
        "node=planner_react",
        "provider=bedrock",
    ]

    # Full URL in metadata for visibility
    metadata = {
        "seed_url": seed_url,
        "hostname": hostname,
        "node": "planner_react",
    }

    return {
        "configurable": {
            "thread_id": thread_id,
        },
        "tags": tags,
        "metadata": metadata,
        "run_name": run_name,
    }


def disable_tracing_for_tests() -> None:
    """Explicitly disable tracing for test environments.

    Call this in test fixtures or conftest.py to ensure tests
    don't make accidental network calls to LangSmith.

    This sets LANGCHAIN_TRACING_V2=false which is the most
    reliable way to disable tracing across all LangChain versions.
    """
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGSMITH_TRACING"] = "false"
    logger.debug("Tracing explicitly disabled for test environment")


# Export public API
__all__ = [
    "should_enable_tracing",
    "prepare_langsmith_env",
    "build_run_config",
    "build_planner_run_config",
    "disable_tracing_for_tests",
]
