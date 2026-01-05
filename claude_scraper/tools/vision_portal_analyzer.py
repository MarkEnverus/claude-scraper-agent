"""Generic vision-based API portal analyzer.

Uses Claude's vision capabilities to understand any API documentation portal
without hard-coded patterns or portal-specific logic.
"""

from typing import Optional, Dict, List, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PortalAnalysis:
    """Generic portal analysis result."""

    # What Claude sees
    visual_description: str

    # How operations are presented
    operations_presentation: str  # e.g., "sidebar list", "dropdown menu", "table rows"
    operations_location: str  # e.g., "left sidebar", "main content area", "navigation bar"

    # How to identify operations
    operation_indicators: List[str]  # e.g., ["GET", "POST", "endpoint names", "URLs"]

    # How to extract them
    extraction_guidance: str  # Natural language guidance from Claude

    # Confidence
    confidence: float  # 0.0-1.0

    # Specific findings
    operations_visible: List[str]  # Actual operation names Claude can see
    url_pattern: Optional[str]  # URL pattern if detectable

    # Metadata
    appears_to_be_api_docs: bool
    appears_to_be_interactive: bool  # Needs clicking/interaction
    appears_to_be_single_page_app: bool


class VisionPortalAnalyzer:
    """Generic vision-based portal analyzer.

    Analyzes any API documentation portal using vision without hard-coded patterns.
    """

    def __init__(self, llm_provider):
        """Initialize analyzer.

        Args:
            llm_provider: LLM provider with vision support
        """
        self.llm = llm_provider

    def analyze_portal(
        self,
        url: str,
        screenshot_path: str,
        markdown_content: Optional[str] = None,
        page_text: Optional[str] = None
    ) -> Optional[PortalAnalysis]:
        """Analyze portal using vision to understand its structure.

        Args:
            url: URL of the portal
            screenshot_path: Path to screenshot
            markdown_content: Optional markdown of page HTML
            page_text: Optional extracted text content

        Returns:
            PortalAnalysis with extraction guidance, or None if not API docs
        """
        logger.info("=== VISION-BASED PORTAL ANALYSIS ===")
        logger.info(f"Analyzing: {url}")

        # Build context for Claude
        context_parts = [f"URL: {url}"]
        if page_text:
            context_parts.append(f"\nPage text preview (first 2000 chars):\n{page_text[:2000]}")

        context = "\n".join(context_parts)

        # Generic open-ended analysis prompt
        prompt = f"""Analyze this webpage and determine if it's API documentation.

{context}

Please analyze:

1. **Is this API documentation?**
   - Look for: endpoint lists, operation names, request/response examples, API references
   - Could be: Swagger UI, API portal, REST docs, GraphQL docs, custom API docs, etc.
   - Answer: yes/no + confidence (0.0-1.0)

2. **If yes, describe what you see:**
   - What does the page look like?
   - Where are the API operations/endpoints listed?
   - How are they presented? (list, tree, table, dropdown, etc.)
   - What visual indicators show something is an operation? (HTTP methods, icons, formatting)

3. **List visible operations:**
   - What operation names/endpoints can you actually see on screen?
   - Are there indicators of more operations not visible? (scroll, pagination, tabs)
   - Approximately how many total operations exist?

4. **Extraction guidance:**
   - If I need to get ALL operations from this page, what should I do?
   - Do I need to click/expand anything?
   - Are operations in HTML links? JavaScript state? Dropdown menu?
   - What DOM patterns should I look for?

5. **URL patterns:**
   - Do operation links have a consistent URL pattern?
   - Examples of operation URLs you can see
   - Any hash routing or query parameters?

6. **Interaction requirements:**
   - Is this a static page or does it need interaction?
   - Do I need to click to reveal operations?
   - Is it a Single Page App that loads operations dynamically?

Be specific and concrete. Focus on what you actually see, not assumptions."""

        try:
            # Call vision API with structured output using Pydantic
            from claude_scraper.types import VisionPortalAnalysisResult

            result = self.llm.invoke_structured_with_vision(
                prompt=prompt,
                images=[screenshot_path],
                response_model=VisionPortalAnalysisResult,
                system="You are an expert at analyzing API documentation portals visually. Analyze the screenshot to understand the portal structure without assumptions."
            )

            logger.info(f"Vision analysis complete:")
            logger.info(f"  Appears to be API docs: {result.is_api_documentation}")
            logger.info(f"  Confidence: {result.confidence}")

            if not result.is_api_documentation or result.confidence < 0.5:
                logger.info("Not API documentation or low confidence, skipping")
                return None

            logger.info(f"  Operations visible: {len(result.operations_visible)}")
            logger.info(f"  Location: {result.operations_location}")
            logger.info(f"  Presentation: {result.operations_presentation}")

            # Log extraction guidance
            logger.info("Extraction guidance:")
            for line in result.extraction_guidance.split('\n'):
                if line.strip():
                    logger.info(f"    {line.strip()}")

            return PortalAnalysis(
                visual_description=result.visual_description,
                operations_presentation=result.operations_presentation,
                operations_location=result.operations_location,
                operation_indicators=result.operation_indicators,
                extraction_guidance=result.extraction_guidance,
                confidence=result.confidence,
                operations_visible=result.operations_visible,
                url_pattern=result.url_pattern,
                appears_to_be_api_docs=result.is_api_documentation,
                appears_to_be_interactive=result.requires_interaction,
                appears_to_be_single_page_app=result.is_spa
            )

        except Exception as e:
            logger.error(f"Vision analysis failed: {e}", exc_info=True)
            return None

    def interpret_extraction_guidance(
        self,
        analysis: PortalAnalysis
    ) -> Dict[str, Any]:
        """Interpret Claude's extraction guidance into actionable steps.

        Args:
            analysis: Portal analysis from vision

        Returns:
            Dictionary with:
              - method: "links", "javascript", "api_call", etc.
              - selectors: CSS selectors to try
              - actions: Actions to perform (click, scroll, etc.)
              - pattern: URL/text pattern to match
        """
        guidance = analysis.extraction_guidance.lower()

        # Interpret guidance into extraction strategy
        strategy = {
            "method": "unknown",
            "selectors": [],
            "actions": [],
            "pattern": None
        }

        # Detect method from guidance
        if "link" in guidance or "href" in guidance or "anchor" in guidance:
            strategy["method"] = "links"

            # Look for selector hints in guidance
            if "sidebar" in guidance:
                strategy["selectors"].extend([
                    ".sidebar a", "[role='navigation'] a", "nav a", "aside a"
                ])
            if "list" in guidance or "menu" in guidance:
                strategy["selectors"].extend([
                    "ul li a", ".menu a", ".list a", ".operations a"
                ])
            if "table" in guidance:
                strategy["selectors"].extend([
                    "table a", "tr a", "td a"
                ])

        elif "click" in guidance or "expand" in guidance:
            strategy["method"] = "interactive"

            if "button" in guidance:
                strategy["actions"].append("click_buttons")
            if "accordion" in guidance or "collapse" in guidance:
                strategy["actions"].append("expand_all")
            if "dropdown" in guidance:
                strategy["actions"].append("open_dropdowns")

        elif "javascript" in guidance or "spa" in guidance or "dynamic" in guidance:
            strategy["method"] = "javascript"
            strategy["actions"].append("extract_from_js_state")

        # Detect URL pattern from guidance
        if "hash" in guidance or "#" in guidance:
            if analysis.url_pattern:
                strategy["pattern"] = analysis.url_pattern
            else:
                strategy["pattern"] = "hash_routing"

        # Add generic fallback selectors
        if not strategy["selectors"]:
            strategy["selectors"] = [
                "a[href*='api']",
                "a[href*='endpoint']",
                "a[href*='operation']",
                ".operation a",
                ".endpoint a",
                ".api a"
            ]

        logger.info(f"Interpreted strategy:")
        logger.info(f"  Method: {strategy['method']}")
        logger.info(f"  Selectors: {strategy['selectors']}")
        logger.info(f"  Actions: {strategy['actions']}")
        logger.info(f"  Pattern: {strategy['pattern']}")

        return strategy
