"""LangGraph workflow for BA Analyst.

This module defines the complete LangGraph workflow that orchestrates
the Business Analyst system's exploration and analysis.

SIMPLIFIED 3-NODE ARCHITECTURE (Phase B):
- planner_react: ReAct agent with tool binding (replaces planner + fetcher + auth_probe + link_selector)
- analyst: Deep analysis of pages
- summarizer: Final report generation

P1/P2 GRAPH SPLIT (WEBSITE/API specialized handling):
When enable_p1_p2_routing is enabled, the graph conditionally routes to specialized handlers:
- After analyst completes Phase 0 detection, route based on detected_source_type
- WEBSITE path: website_p1 (discovery) → website_p2 (validation) → planner_react
- API path: api_p1 (discovery) → api_p2 (validation) → planner_react
- Low confidence or FTP/EMAIL: Continue with existing planner_react flow

The planner_react agent uses tools directly:
- render_page_with_js: Fetches and renders JS-heavy pages
- http_get_headers: Checks status/auth
- extract_links: Gets navigation links

This implements "agentic first" architecture where LLM makes tool decisions.
"""

from typing import Literal
import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agentic_scraper.business_analyst.state import BAAnalystState
from agentic_scraper.business_analyst.nodes.planner_react import planner_react_node
from agentic_scraper.business_analyst.nodes.analyst import analyst_node
from agentic_scraper.business_analyst.nodes.summarizer import summarizer_node
from agentic_scraper.business_analyst.nodes.website_p1_handler import website_p1_handler
from agentic_scraper.business_analyst.nodes.website_p2_validator import website_p2_validator
from agentic_scraper.business_analyst.nodes.api_p1_handler import api_p1_handler
from agentic_scraper.business_analyst.nodes.param_p15_handler import param_p15_handler
from agentic_scraper.business_analyst.nodes.api_p2_validator import api_p2_validator
from agentic_scraper.types.ba_analysis import DataSourceType

logger = logging.getLogger(__name__)


# ============================================================================
# P1/P2 Placeholder Nodes (to be implemented in later phases)
# ============================================================================

# WEBSITE P1/P2 and API P1/P2 handlers are now implemented in separate modules


# ============================================================================
# Graph Creation
# ============================================================================

def create_ba_graph():
    """Create the BA Analyst LangGraph workflow.

    Simplified 3-node architecture following langchain-experimental pattern:
    - planner_react: ReAct agent with tools (replaces planner + fetcher + auth_probe + link_selector)
    - analyst: Deep analysis node
    - summarizer: Final report generation

    Flow:
    - planner_react decides to analyze → analyst → planner_react (loop)
    - planner_react decides to stop → summarizer → END

    Returns:
        Compiled LangGraph with 3 nodes configured.

    Example:
        >>> graph = create_ba_graph()
        >>> config = {"configurable": {"thread_id": "session-1"}}
        >>> result = graph.invoke(initial_state, config=config)
    """
    # Create state graph
    workflow = StateGraph(BAAnalystState)

    # Add base 3 nodes
    workflow.add_node("planner_react", planner_react_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("summarizer", summarizer_node)

    # Add P1/P2 nodes (WEBSITE and API handlers both implemented)
    workflow.add_node("website_p1", website_p1_handler)
    workflow.add_node("website_p2", website_p2_validator)
    workflow.add_node("api_p1", api_p1_handler)
    workflow.add_node("param_p15", param_p15_handler)  # Phase 1.5: Parameter analysis
    workflow.add_node("api_p2", api_p2_validator)

    # Set entry point
    workflow.set_entry_point("planner_react")

    # Add conditional edges from planner_react
    def route_from_planner(state: BAAnalystState) -> Literal["analyst", "summarizer", "planner_react"]:
        """Route based on planner_react decision.

        The planner_react agent uses tools to fetch/analyze pages, then decides:
        - "analyze_page": Has content ready for deep analysis → analyst
        - "stop": Done exploring → summarizer
        - "continue": Keep exploring → planner_react (loop)

        Args:
            state: Current graph state

        Returns:
            Next node name: "analyst", "summarizer", or "planner_react"
        """
        action = state.get("next_action", "stop")

        if action == "analyze_page":
            return "analyst"
        elif action == "stop":
            return "summarizer"
        else:
            # Continue planning/exploring
            return "planner_react"

    workflow.add_conditional_edges(
        "planner_react",
        route_from_planner,
        {
            "analyst": "analyst",
            "summarizer": "summarizer",
            "planner_react": "planner_react"  # Loop back for continued exploration
        }
    )

    # ========================================================================
    # P1/P2 Conditional Routing from analyst (Phase 1+ implementation)
    # ========================================================================

    def route_from_analyst(state: BAAnalystState) -> Literal["website_p1", "api_p1", "planner_react"]:
        """Route after Phase 0 detection to source-type-specific handlers.

        Routes to specialized P1/P2 handlers based on detected source type.
        Confidence is informational only - routing always occurs based on detected type.

        Args:
            state: Current graph state with detection results

        Returns:
            Next node: "website_p1", "api_p1", or "planner_react"

        Routing logic:
        - DataSourceType.WEBSITE → website_p1
        - DataSourceType.API → api_p1
        - DataSourceType.FTP/EMAIL → planner_react (not yet implemented)
        """
        # Check detection results
        detected_type = state.get("detected_source_type")
        confidence = state.get("detection_confidence", 0.0)

        # Route based on detected source type (confidence is informational only)
        if detected_type == DataSourceType.WEBSITE:
            logger.info(
                f"Routing to WEBSITE P1 handler (detected_type={detected_type}, confidence={confidence:.2f})"
            )
            return "website_p1"
        elif detected_type == DataSourceType.API:
            logger.info(
                f"Routing to API P1 handler (detected_type={detected_type}, confidence={confidence:.2f})"
            )
            return "api_p1"
        else:
            # FTP/EMAIL not implemented yet → fallback to existing flow
            logger.info(
                f"Detected type {detected_type} not supported for P1/P2 routing yet, "
                f"continuing with planner_react flow"
            )
            return "planner_react"

    # P1/P2 Bug #3 fix: Conditional routing from P2 validators
    def route_from_p2(state: BAAnalystState) -> Literal["summarizer", "planner_react"]:
        """Route after P2 validation to allow termination.

        If P2 validation complete and next_action is stop, go to summarizer.
        Otherwise continue with planner_react for more exploration.
        """
        p2_complete = state.get("p2_complete", False)
        next_action = state.get("next_action")

        if p2_complete and next_action == "stop":
            logger.info("[P2 Route] Validation complete with stop signal → summarizer")
            return "summarizer"
        else:
            logger.info("[P2 Route] Validation complete but continue signal → planner_react")
            return "planner_react"

    # Add conditional routing from analyst
    workflow.add_conditional_edges(
        "analyst",
        route_from_analyst,
        {
            "website_p1": "website_p1",
            "api_p1": "api_p1",
            "planner_react": "planner_react"
        }
    )

    # ========================================================================
    # P1/P2 Path Edges (WEBSITE and API specialized handlers)
    # ========================================================================

    # WEBSITE path: P1 (discovery) → P2 (validation) → [conditional: summarizer or planner_react]
    workflow.add_edge("website_p1", "website_p2")
    workflow.add_conditional_edges(
        "website_p2",
        route_from_p2,
        {
            "summarizer": "summarizer",
            "planner_react": "planner_react"
        }
    )

    # API path: P1 (discovery) → P1.5 (parameter analysis) → P2 (validation) → [conditional: summarizer or planner_react]
    workflow.add_edge("api_p1", "param_p15")
    workflow.add_edge("param_p15", "api_p2")
    workflow.add_conditional_edges(
        "api_p2",
        route_from_p2,
        {
            "summarizer": "summarizer",
            "planner_react": "planner_react"
        }
    )

    # Summarizer is terminal
    workflow.add_edge("summarizer", END)

    # Add memory checkpointing
    memory = MemorySaver()

    # Compile graph
    app = workflow.compile(checkpointer=memory)

    return app


# Export
__all__ = ["create_ba_graph"]
