"""Hybrid 3-stage endpoint filtering for BA Analyst.

This module implements the endpoint filtering pipeline that prevents scraper explosion:
- Stage 1: Deterministic pre-filter (pattern matching)
- Stage 2: LLM classification + ranking
- Stage 3: Deterministic caps + audit trail

The filtering system produces:
- Filtered endpoints list (≤max_endpoints_for_generation) for scraper generator
- Full audit trail with categories and reasons for discarded endpoints
- Authentication metadata extracted from auth endpoints
"""

import logging
import json
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, asdict
from urllib.parse import urlparse

from agentic_scraper.business_analyst.state import EndpointFinding, BAAnalystState
from agentic_scraper.business_analyst.config import BAConfig
from agentic_scraper.business_analyst.utils.api_call_extractor import (
    is_static_asset,
    is_auth_endpoint,
    is_policy_page,
    is_portal_navigation,
    is_system_endpoint,
)
from agentic_scraper.business_analyst.prompts.endpoint_filter import (
    endpoint_classification_prompt,
)
from agentic_scraper.llm.factory import LLMFactory

logger = logging.getLogger(__name__)


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class DiscardedEndpoint:
    """Represents an endpoint that was filtered out with audit trail.

    Attributes:
        endpoint: The original EndpointFinding that was discarded
        stage: Which filtering stage discarded it ("pre_filter" | "llm_filter" | "cap_limit")
        category: Classification category ("STATIC" | "AUTH" | "NAV" | "SYSTEM" | "LOW_CONFIDENCE" | "CAP_EXCEEDED")
        reason: Human-readable explanation for why it was discarded
        confidence: Optional LLM confidence score (0.0-1.0) if from Stage 2
    """
    endpoint: EndpointFinding
    stage: str
    category: str
    reason: str
    confidence: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "endpoint": {
                "name": self.endpoint.name,
                "url": self.endpoint.url,
                "method_guess": self.endpoint.method_guess,
                "format": self.endpoint.format,
                "data_type": self.endpoint.data_type,
                "notes": self.endpoint.notes,
            },
            "stage": self.stage,
            "category": self.category,
            "reason": self.reason,
            "confidence": self.confidence,
        }


@dataclass
class CategorizedEndpoint:
    """Represents an endpoint classified by the LLM in Stage 2.

    Attributes:
        endpoint: The original EndpointFinding
        category: LLM-assigned category ("DATA" | "AUTH" | "NAV" | "SYSTEM" | "UNKNOWN")
        keep_for_generation: LLM recommendation to keep for scraper generation
        confidence: LLM confidence score (0.0-1.0)
        reason: LLM explanation for classification
    """
    endpoint: EndpointFinding
    category: str
    keep_for_generation: bool
    confidence: float
    reason: str


@dataclass
class EndpointClassificationResult:
    """Result from Stage 2 LLM classification.

    Attributes:
        categorized_endpoints: List of all endpoints with LLM categories
        top_data_endpoints: List of endpoint names ranked by LLM for generation
        auth_notes: Authentication requirements extracted from AUTH endpoints
    """
    categorized_endpoints: List[CategorizedEndpoint]
    top_data_endpoints: List[str]
    auth_notes: str


@dataclass
class FilteringResult:
    """Complete result from hybrid 3-stage filtering pipeline.

    Attributes:
        kept_endpoints: Filtered list of endpoints for scraper generation (≤max)
        discarded_endpoints: Full audit trail of filtered endpoints
        auth_metadata: Authentication information extracted from AUTH endpoints
        filtering_summary: Statistics about filtering stages
    """
    kept_endpoints: List[EndpointFinding]
    discarded_endpoints: List[DiscardedEndpoint]
    auth_metadata: Dict[str, Any]
    filtering_summary: Dict[str, Any]


# ============================================================================
# Stage 1: Deterministic Pre-Filter
# ============================================================================

def deterministic_pre_filter(
    endpoints: List[EndpointFinding],
    config: BAConfig
) -> Tuple[List[EndpointFinding], List[DiscardedEndpoint]]:
    """Stage 1: Filter out obvious junk using pattern matching.

    Drops only obvious non-data endpoints:
    - Static assets (.js, .css, images, fonts)
    - Auth flows (/login, /signin, /token, /oauth)
    - Policy pages (/terms, /privacy, /sitemap)
    - Portal navigation (/apis, /products, /resources)
    - System endpoints (/health, /trace, /config)

    Args:
        endpoints: List of endpoint candidates to filter
        config: BA configuration (unused here but kept for consistency)

    Returns:
        Tuple of (kept_endpoints, discarded_endpoints)
    """
    kept = []
    discarded = []

    for ep in endpoints:
        url = ep.url

        # Check filters in order of specificity
        if is_static_asset(url):
            discarded.append(DiscardedEndpoint(
                endpoint=ep,
                stage="pre_filter",
                category="STATIC",
                reason=f"Static asset (matches STATIC_ASSET_PATTERNS): {url}"
            ))
        elif is_auth_endpoint(url):
            discarded.append(DiscardedEndpoint(
                endpoint=ep,
                stage="pre_filter",
                category="AUTH",
                reason=f"Authentication endpoint (matches AUTH_PATTERNS): {url}"
            ))
        elif is_policy_page(url):
            discarded.append(DiscardedEndpoint(
                endpoint=ep,
                stage="pre_filter",
                category="NAV",
                reason=f"Policy/documentation page (matches POLICY_PATTERNS): {url}"
            ))
        elif is_portal_navigation(url):
            discarded.append(DiscardedEndpoint(
                endpoint=ep,
                stage="pre_filter",
                category="NAV",
                reason=f"Portal navigation page (matches PORTAL_NAV_PATTERNS): {url}"
            ))
        elif is_system_endpoint(url):
            discarded.append(DiscardedEndpoint(
                endpoint=ep,
                stage="pre_filter",
                category="SYSTEM",
                reason=f"System/monitoring endpoint (matches SYSTEM_PATTERNS): {url}"
            ))
        else:
            # Keep for Stage 2 LLM classification
            kept.append(ep)

    logger.info(
        f"Stage 1 (Deterministic Pre-Filter): {len(endpoints)} total → "
        f"{len(kept)} kept, {len(discarded)} discarded"
    )

    return kept, discarded


# ============================================================================
# Stage 2: LLM Classification + Ranking
# ============================================================================

def llm_classify_endpoints(
    candidates: List[EndpointFinding],
    state: BAAnalystState,
    llm_factory: LLMFactory,
    config: BAConfig
) -> EndpointClassificationResult:
    """Stage 2: Use LLM to classify and rank remaining endpoint candidates.

    Asks LLM to:
    - Categorize each endpoint (DATA | AUTH | NAV | SYSTEM | UNKNOWN)
    - Assign confidence score (0.0-1.0)
    - Provide evidence-based reasoning
    - Rank top N data endpoints for generation
    - Extract authentication requirements

    Args:
        candidates: Endpoints that passed Stage 1 pre-filter
        state: Full BA analyst state (for context)
        llm_factory: Factory to create LLM instance
        config: BA configuration with max_endpoints_for_generation

    Returns:
        EndpointClassificationResult with categorized endpoints and rankings
    """
    if not candidates:
        logger.info("Stage 2 (LLM Classification): No candidates to classify (all filtered in Stage 1)")
        return EndpointClassificationResult(
            categorized_endpoints=[],
            top_data_endpoints=[],
            auth_notes="No endpoints discovered."
        )

    # Extract context from state
    seed_url = state.get('seed_url', '')
    auth_summary = state.get('auth_summary', '')
    pages_visited = [page.get('url', '') for page in state.get('pages_visited', [])]
    candidate_api_calls = state.get('candidate_api_calls', [])

    # Generate LLM prompt
    prompt = endpoint_classification_prompt(
        candidates=candidates,
        seed_url=seed_url,
        auth_summary=auth_summary,
        pages_visited=pages_visited,
        candidate_api_calls=candidate_api_calls,
        max_endpoints=config.max_endpoints_for_generation
    )

    # Call LLM for classification (use fast model for classification task)
    llm = llm_factory.create_fast_model()

    try:
        logger.info(f"Stage 2 (LLM Classification): Classifying {len(candidates)} endpoints...")
        response = llm.invoke(prompt)

        # Parse LLM response (should be pure JSON)
        response_text = response.content if hasattr(response, 'content') else str(response)

        # Strip markdown code blocks if present
        if response_text.strip().startswith("```"):
            lines = response_text.strip().split('\n')
            # Remove first line (```json or ```) and last line (```)
            response_text = '\n'.join(lines[1:-1])

        classification_data = json.loads(response_text)

        # Build CategorizedEndpoint list
        categorized = []
        endpoint_name_map = {ep.name: ep for ep in candidates}

        for ep_data in classification_data.get('endpoints', []):
            ep_name = ep_data.get('name')
            if ep_name not in endpoint_name_map:
                logger.warning(f"LLM returned unknown endpoint name: {ep_name} (skipping)")
                continue

            categorized.append(CategorizedEndpoint(
                endpoint=endpoint_name_map[ep_name],
                category=ep_data.get('category', 'UNKNOWN'),
                keep_for_generation=ep_data.get('keep_for_generation', False),
                confidence=ep_data.get('confidence', 0.0),
                reason=ep_data.get('reason', 'No reason provided')
            ))

        top_data_endpoints = classification_data.get('top_endpoints_for_generation', [])
        auth_notes = classification_data.get('auth_notes', '')

        logger.info(
            f"Stage 2 (LLM Classification): Categorized {len(categorized)} endpoints, "
            f"top {len(top_data_endpoints)} recommended for generation"
        )

        return EndpointClassificationResult(
            categorized_endpoints=categorized,
            top_data_endpoints=top_data_endpoints,
            auth_notes=auth_notes
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM classification response as JSON: {e}")
        logger.error(f"Response text: {response_text[:500]}...")
        # Fallback: mark all as UNKNOWN with low confidence
        return EndpointClassificationResult(
            categorized_endpoints=[
                CategorizedEndpoint(
                    endpoint=ep,
                    category="UNKNOWN",
                    keep_for_generation=False,
                    confidence=0.0,
                    reason="LLM classification failed (JSON parse error)"
                )
                for ep in candidates
            ],
            top_data_endpoints=[],
            auth_notes="Classification failed - could not parse LLM response."
        )
    except Exception as e:
        logger.error(f"Unexpected error during LLM classification: {e}")
        # Fallback: mark all as UNKNOWN with low confidence
        return EndpointClassificationResult(
            categorized_endpoints=[
                CategorizedEndpoint(
                    endpoint=ep,
                    category="UNKNOWN",
                    keep_for_generation=False,
                    confidence=0.0,
                    reason=f"LLM classification failed: {str(e)}"
                )
                for ep in candidates
            ],
            top_data_endpoints=[],
            auth_notes="Classification failed due to unexpected error."
        )


# ============================================================================
# Stage 3: Deterministic Caps + Audit Trail
# ============================================================================

def apply_caps_and_audit(
    classification_result: EndpointClassificationResult,
    config: BAConfig
) -> Tuple[List[EndpointFinding], List[DiscardedEndpoint], Dict[str, Any]]:
    """Stage 3: Apply hard constraints and build final audit trail.

    Enforces:
    - Minimum confidence threshold (endpoint_min_confidence)
    - Maximum endpoints for generation (max_endpoints_for_generation)
    - Preserves full audit trail for transparency

    Args:
        classification_result: Result from Stage 2 LLM classification
        config: BA configuration with caps and thresholds

    Returns:
        Tuple of (kept_endpoints, discarded_endpoints, auth_metadata)
    """
    kept = []
    discarded = []

    # Build name-to-endpoint mapping for top_data_endpoints lookup
    categorized_map = {
        cat_ep.endpoint.name: cat_ep
        for cat_ep in classification_result.categorized_endpoints
    }

    # Extract auth metadata from AUTH-categorized endpoints
    auth_metadata = {
        "auth_notes": classification_result.auth_notes,
        "auth_endpoints": []
    }

    for cat_ep in classification_result.categorized_endpoints:
        if cat_ep.category == "AUTH":
            auth_metadata["auth_endpoints"].append({
                "name": cat_ep.endpoint.name,
                "url": cat_ep.endpoint.url,
                "notes": cat_ep.endpoint.notes,
            })

    # Process categorized endpoints
    top_names_set = set(classification_result.top_data_endpoints[:config.max_endpoints_for_generation])

    for cat_ep in classification_result.categorized_endpoints:
        # Rule 1: Discard if category is not DATA
        if cat_ep.category != "DATA":
            discarded.append(DiscardedEndpoint(
                endpoint=cat_ep.endpoint,
                stage="llm_filter",
                category=cat_ep.category,
                reason=cat_ep.reason,
                confidence=cat_ep.confidence
            ))
            continue

        # Rule 2: Discard if confidence below threshold
        if cat_ep.confidence < config.endpoint_min_confidence:
            discarded.append(DiscardedEndpoint(
                endpoint=cat_ep.endpoint,
                stage="llm_filter",
                category="LOW_CONFIDENCE",
                reason=f"Confidence {cat_ep.confidence:.2f} below threshold {config.endpoint_min_confidence} | {cat_ep.reason}",
                confidence=cat_ep.confidence
            ))
            continue

        # Rule 3: Discard if not in top N (cap limit)
        if cat_ep.endpoint.name not in top_names_set:
            discarded.append(DiscardedEndpoint(
                endpoint=cat_ep.endpoint,
                stage="cap_limit",
                category="CAP_EXCEEDED",
                reason=f"Not in top {config.max_endpoints_for_generation} data endpoints | {cat_ep.reason}",
                confidence=cat_ep.confidence
            ))
            continue

        # Keep this endpoint
        kept.append(cat_ep.endpoint)

    logger.info(
        f"Stage 3 (Caps + Audit): {len(classification_result.categorized_endpoints)} classified → "
        f"{len(kept)} kept (≤{config.max_endpoints_for_generation}), {len(discarded)} discarded"
    )

    return kept, discarded, auth_metadata


# ============================================================================
# Main Orchestrator
# ============================================================================

def run_hybrid_filter(
    endpoints: List[EndpointFinding],
    state: BAAnalystState,
    config: BAConfig,
    llm_factory: LLMFactory
) -> FilteringResult:
    """Main entry point: Run complete 3-stage hybrid filtering pipeline.

    Pipeline:
    1. Stage 1 (Deterministic Pre-Filter): Pattern-based filtering
    2. Stage 2 (LLM Classification): AI-based categorization and ranking
    3. Stage 3 (Caps + Audit): Hard constraints and audit trail

    Args:
        endpoints: All discovered endpoints from BA analysis
        state: Full BA analyst state (for LLM context)
        config: BA configuration with filtering parameters
        llm_factory: Factory to create LLM instances

    Returns:
        FilteringResult with kept endpoints (≤max), discarded endpoints, and metadata
    """
    logger.info(f"Starting hybrid 3-stage filtering pipeline with {len(endpoints)} total endpoints")

    # Stage 1: Deterministic pre-filter
    stage1_kept, stage1_discarded = deterministic_pre_filter(endpoints, config)

    # Stage 2: LLM classification + ranking
    classification_result = llm_classify_endpoints(
        candidates=stage1_kept,
        state=state,
        llm_factory=llm_factory,
        config=config
    )

    # Stage 3: Apply caps and build audit trail
    stage3_kept, stage3_discarded, auth_metadata = apply_caps_and_audit(
        classification_result, config
    )

    # Combine discarded endpoints from all stages
    all_discarded = stage1_discarded + stage3_discarded

    # Build filtering summary
    filtering_summary = {
        "total_endpoints": len(endpoints),
        "kept_for_generation": len(stage3_kept),
        "discarded_total": len(all_discarded),
        "discarded_stage1_pre_filter": len(stage1_discarded),
        "discarded_stage2_llm_filter": len([d for d in stage3_discarded if d.stage == "llm_filter"]),
        "discarded_stage3_cap_limit": len([d for d in stage3_discarded if d.stage == "cap_limit"]),
        "max_endpoints_config": config.max_endpoints_for_generation,
        "min_confidence_config": config.endpoint_min_confidence,
    }

    logger.info(
        f"Filtering complete: {len(endpoints)} total → {len(stage3_kept)} kept, "
        f"{len(all_discarded)} discarded (Stage1: {len(stage1_discarded)}, "
        f"Stage2+3: {len(stage3_discarded)})"
    )

    return FilteringResult(
        kept_endpoints=stage3_kept,
        discarded_endpoints=all_discarded,
        auth_metadata=auth_metadata,
        filtering_summary=filtering_summary
    )
