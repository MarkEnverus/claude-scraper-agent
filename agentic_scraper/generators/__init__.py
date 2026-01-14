"""Hybrid template + BAML scraper generation system.

This package provides code generation for scrapers using:
- Jinja2 templates for structural boilerplate
- BAML functions for complex logic generation (OAuth, navigation, pagination)
- Variable transformation to bridge BA Analyzer output to templates
"""

from agentic_scraper.generators.hybrid_generator import HybridGenerator
from agentic_scraper.generators.template_renderer import TemplateRenderer
from agentic_scraper.generators.variable_transformer import VariableTransformer
from agentic_scraper.generators.orchestrator import (
    ScraperOrchestrator,
    OrchestrationResult,
)
from agentic_scraper.types.errors import (
    OrchestrationError,
    BAAnalysisError,
    GenerationError,
)

__all__ = [
    "HybridGenerator",
    "TemplateRenderer",
    "VariableTransformer",
    "ScraperOrchestrator",
    "OrchestrationResult",
    "OrchestrationError",
    "BAAnalysisError",
    "GenerationError",
]
