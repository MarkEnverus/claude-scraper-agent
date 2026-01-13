"""Agent implementations for scraper architecture.

This package contains agents for endpoint QA and other testing.
The new BA Analyzer is in claude_scraper.business_analyst (LangGraph-based).
"""

from agentic_scraper.agents.endpoint_qa import EndpointQATester

__all__ = ["EndpointQATester"]
