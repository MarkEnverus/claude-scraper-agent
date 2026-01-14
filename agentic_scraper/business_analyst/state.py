"""State models for LangGraph BA Analyst.

This module defines the TypedDict state and Pydantic models used throughout
the LangGraph-based Business Analyst system.
"""

from __future__ import annotations  # PEP 563 - enables forward references in all annotations

from typing import TypedDict, Optional, List, Dict, Set, Tuple, TYPE_CHECKING, Any, Annotated
from pydantic import BaseModel, Field
import operator

# Import BAConfig for runtime (needed by LangGraph type resolution)
# Avoid circular import by importing at module level
if TYPE_CHECKING:
    from agentic_scraper.business_analyst.config import BAConfig
    from agentic_scraper.types.ba_analysis import DataSourceType
else:
    # At runtime, use Any to avoid circular import issues
    # The actual BAConfig will be provided when state is created
    BAConfig = Any
    from agentic_scraper.types.ba_analysis import DataSourceType


# ============================================================================
# LangGraph State (TypedDict)
# ============================================================================

class BAAnalystState(TypedDict):
    """State for LangGraph BA Analyst.

    This represents the complete state maintained across the LangGraph workflow.
    """
    # Input configuration
    seed_url: str
    primary_api_name: Optional[str]  # API name extracted from URL fragment (e.g., "pricing-api")
    max_depth: int
    allowed_domains: List[str]

    # Navigation state
    visited: Set[str]
    analyzed_urls: Set[str]  # URLs that completed analyst AI analysis (conservative filtering)
    queue: List[Dict]  # List of {"url": str, "score": float, "reason": str}
    current_depth: int
    current_url: Optional[str]
    last_analyzed_url: Optional[str]  # P1/P2 Bug #2 fix: Preserve URL for P1 handlers after analyst completes

    # Evidence collected
    artifacts: Dict[str, PageArtifact]  # url -> artifact mapping
    screenshots: Dict[str, str]  # url -> screenshot_path mapping
    candidate_api_calls: Annotated[List[str], operator.add]  # Network API calls discovered (not filtered)

    # Findings (endpoints use operator.add to accumulate across multiple analyst passes)
    endpoints: Annotated[List[EndpointFinding], operator.add]
    auth_summary: Optional[str]
    gaps: Annotated[List[str], operator.add]

    # Control flow
    next_action: Optional[str]  # "fetch_main", "follow_link", "stop", "analyze_page", "continue"
    stop_reason: Optional[str]
    consecutive_failures: int  # Track consecutive analyst failures to prevent death spirals

    # Agent state (Phase B: ReAct pattern)
    planner_agent: Optional[Any]  # ReAct agent instance for reuse

    # Config reference
    config: Optional[BAConfig]

    # ========================================================================
    # P1/P2 Graph Split Fields (Phase 1+ for WEBSITE/API specialized handling)
    # ========================================================================

    # Phase 0 detection results (used for routing)
    detected_source_type: Optional[DataSourceType]  # API, WEBSITE, FTP, EMAIL
    detection_confidence: float  # 0.0-1.0 confidence in detection

    # WEBSITE hierarchy tracking (for portal/folder navigation)
    website_hierarchy_level: Optional[str]  # "portal", "category", "folder", "file"
    discovered_data_links: Annotated[List[str], operator.add]  # Download URLs (accumulate)
    folder_paths_visited: Set[str]  # Prevent navigation loops

    # P1/P2 control flow (track completion status)
    needs_p1_handling: bool  # Whether source needs P1 specialized handler
    p1_complete: bool  # P1 discovery complete
    p2_complete: bool  # P2 validation complete


# ============================================================================
# Data Models (Pydantic)
# ============================================================================

class LinkInfo(BaseModel):
    """Information about a discovered link."""
    url: str = Field(..., description="Absolute URL of the link")
    text: str = Field(..., description="Link text or description")
    heuristic_score: float = Field(0.0, description="Deterministic heuristic score (0-1)")
    llm_score: Optional[float] = Field(None, description="LLM rerank score (0-1)")
    combined_score: Optional[float] = Field(None, description="Average of heuristic + LLM scores")
    reason: str = Field("", description="Why this link is interesting")
    llm_rationale: Optional[str] = Field(None, description="LLM explanation for score")


class AuthSignals(BaseModel):
    """Authentication signals detected from a page."""
    requires_login: bool = Field(False, description="Generic login requirement detected")
    has_401: bool = Field(False, description="HTTP 401 Unauthorized")
    has_403: bool = Field(False, description="HTTP 403 Forbidden")
    login_form_detected: bool = Field(False, description="HTML login form present")
    sso_detected: bool = Field(False, description="SSO/OAuth detected in URL")
    requires_auth_header: bool = Field(False, description="WWW-Authenticate header present")
    auth_redirect: bool = Field(False, description="Redirects to /login")
    robots_disallowed: bool = Field(False, description="Blocked by robots.txt")
    credentials_available: bool = Field(False, description="Credentials available in config")
    credential_type: Optional[str] = Field(None, description="Type: bearer, basic, cookie")
    is_portal: bool = Field(False, description="Login portal (auth gate before content)")
    is_api_docs: bool = Field(False, description="Public API docs (mentions auth but not gated)")


class PageArtifact(BaseModel):
    """Complete artifact from fetching a page.

    Contains all data extracted from a page including HTML, markdown,
    links, auth signals, and screenshots.
    """
    url: str = Field(..., description="Page URL")
    status_code: int = Field(..., description="HTTP status code")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    html_excerpt: str = Field("", description="Trimmed HTML content")
    markdown_excerpt: str = Field("", description="Converted markdown excerpt")
    screenshot_path: Optional[str] = Field(None, description="Path to screenshot PNG")
    links: List[LinkInfo] = Field(default_factory=list, description="Discovered links")
    auth_signals: AuthSignals = Field(default_factory=AuthSignals, description="Auth detection")
    network_events: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Captured network events (dicts with at least `url`)",
    )

    # LLM interaction tracking (for capture/replay)
    llm_interactions: List[Dict] = Field(default_factory=list, description="LLM calls made on this page")


class EndpointFinding(BaseModel):
    """A discovered API endpoint or data source."""
    name: str = Field(..., description="Endpoint name or title")
    url: str = Field(..., description="Endpoint URL or base URL")
    method_guess: str = Field("unknown", description="HTTP method: GET, POST, or unknown")
    auth_required: str = Field("unknown", description="Auth required: true, false, or unknown")
    data_type: str = Field("other", description="Data type: historical, daily, real-time, or other")
    format: str = Field("unknown", description="Format: json, xml, csv, xlsx, wadl, openapi, or unknown")
    freshness: str = Field("unknown", description="Freshness: live, static, or unknown")
    pagination: str = Field("unknown", description="Pagination: true, false, or unknown")
    notes: str = Field("", description="Additional notes or observations")
    evidence_urls: List[str] = Field(default_factory=list, description="URLs where evidence was found")

    # NEW: Parameter information for API endpoints (MISO operations discovery)
    parameters: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Parameter metadata: name, type, required, location, format, examples, defaults"
    )


class SiteReport(BaseModel):
    """Final report for a site analysis."""
    site: str = Field(..., description="Seed URL analyzed")
    endpoints: List[EndpointFinding] = Field(default_factory=list, description="Discovered endpoints")
    auth_summary: str = Field("", description="Overall auth posture summary")
    navigation_paths: List[Tuple[str, str]] = Field(default_factory=list, description="(url, reason) tuples")
    gaps: List[str] = Field(default_factory=list, description="Known gaps or limitations")
    next_actions: List[str] = Field(default_factory=list, description="Suggested next steps")
    stop_reason: Optional[str] = Field(None, description="Why analysis stopped")
    pages_visited: int = Field(0, description="Total pages visited")
    screenshots_captured: int = Field(0, description="Total screenshots taken")
    total_tokens: int = Field(0, description="Total tokens used")


# ============================================================================
# LLM Response Models
# ============================================================================

class PlannerDecision(BaseModel):
    """Decision from planner node."""
    action: str = Field(..., description="Action to take: fetch_main, follow_link, or stop")
    next_url: Optional[str] = Field(None, description="URL to visit (if follow_link)")
    reason: Optional[str] = Field(None, description="Reason for decision")


class AnalysisResult(BaseModel):
    """Result from analyst node."""
    endpoints: List[EndpointFinding] = Field(default_factory=list, description="Endpoints found on this page")
    recommended_links: List[LinkInfo] = Field(default_factory=list, description="Links to follow next")


class LinkRerankResult(BaseModel):
    """Result from LLM link reranking."""
    links: List[LinkInfo] = Field(default_factory=list, description="Reranked links with LLM scores")
