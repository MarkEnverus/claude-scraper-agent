"""Business Analyst - LangGraph-based BA analyzer for API documentation discovery."""

__version__ = "2.0.0"

# Public API exports
from agentic_scraper.business_analyst.graph import create_ba_graph
from agentic_scraper.business_analyst.cli import run_analysis, create_initial_state
from agentic_scraper.business_analyst.config import BAConfig
from agentic_scraper.business_analyst.state import (
    BAAnalystState,
    PageArtifact,
    EndpointFinding,
    SiteReport,
    LinkInfo,
    AuthSignals
)
from agentic_scraper.business_analyst.output import save_results, load_state

__all__ = [
    # Main functions
    "create_ba_graph",
    "run_analysis",
    "create_initial_state",

    # Configuration
    "BAConfig",

    # State models
    "BAAnalystState",
    "PageArtifact",
    "EndpointFinding",
    "SiteReport",
    "LinkInfo",
    "AuthSignals",

    # Output
    "save_results",
    "load_state",
]
