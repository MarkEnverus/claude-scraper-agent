"""Analyst Node for BA Analyst LangGraph system.

This is the most complex node in the system, performing two-pass endpoint analysis:
- Pass 1 (Phase 0): Initial detection using vision + text analysis
- Pass 2 (Phase 1): Per-endpoint detailed analysis

The node implements strict cost controls through token budgeting, chunking,
and endpoint limits.
"""

import logging
from typing import Any, Dict, List, Optional

from agentic_scraper.business_analyst.state import (
    BAAnalystState,
    PageArtifact,
    EndpointFinding,
    AnalysisResult,
    LinkInfo
)
from agentic_scraper.business_analyst.prompts.phase0 import phase0_single_page_prompt
from agentic_scraper.business_analyst.prompts.phase1 import phase1_documentation_prompt
from agentic_scraper.business_analyst.utils.chunking import (
    chunk_markdown,
    select_top_chunks,
    merge_chunks,
    extract_api_keywords
)
from agentic_scraper.business_analyst.utils.network_events import urls_from_network_events
from agentic_scraper.llm.factory import LLMFactory
from agentic_scraper.types.ba_analysis import (
    Phase0Detection,
    Phase1Documentation,
    EndpointSpec,
    DataSourceType
)

logger = logging.getLogger(__name__)


def analyst_node(state: BAAnalystState) -> Dict[str, Any]:
    """Analyst Node: Two-pass endpoint analysis (Phase 0 → Phase 1).

    This is the most complex node in the BA Analyst system. It performs:
    1. Pass 1 (Phase 0): Initial detection using vision/text to discover endpoints
    2. Pass 2 (Phase 1): Per-endpoint detailed analysis with metadata extraction

    Cost Controls:
    - Markdown chunked to max 2000 tokens per chunk
    - Only top 3 chunks analyzed (by relevance score)
    - Max 10 endpoints analyzed in detail
    - Vision used only when screenshot available

    Failure Stop-Guard:
    - Tracks consecutive failures to prevent recursion limit death spirals
    - Stops after 3 consecutive failures with actionable error message

    Args:
        state: BAAnalystState containing current_url and artifact

    Returns:
        Dict with:
        - endpoints: List[EndpointFinding] - All discovered endpoints
        - queue: Updated queue with recommended links

    Example:
        >>> from agentic_scraper.business_analyst.state import BAAnalystState
        >>> state = BAAnalystState(
        ...     current_url="https://api.example.com/docs",
        ...     artifacts={"https://api.example.com/docs": artifact},
        ...     config=config
        ... )
        >>> result = analyst_node(state)
        >>> print(len(result["endpoints"]))
        5
    """
    logger.info(f"[Analyst Node] Starting analysis for: {state['current_url']}")

    # Failure Stop-Guard: Check consecutive failures threshold
    consecutive_failures = state.get("consecutive_failures", 0)
    MAX_CONSECUTIVE_FAILURES = 3

    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        logger.error(
            f"[Analyst Node] STOP: Reached {consecutive_failures} consecutive failures "
            f"(threshold={MAX_CONSECUTIVE_FAILURES}). Stopping to prevent recursion limit."
        )
        return {
            "next_action": "stop",
            "stop_reason": (
                f"Analyst failed {consecutive_failures} consecutive times. "
                f"This indicates a systemic issue (LLM errors, schema mismatch, or broken extraction). "
                f"Check logs for ValidationException or extraction errors."
            ),
            "endpoints": [],
            "queue": state.get("queue", []),
            "consecutive_failures": consecutive_failures  # Preserve count
        }

    # Retrieve config and LLM
    config = state.get("config")
    if not config:
        raise ValueError("Config not found in state")

    # Get current artifact
    current_url = state.get("current_url")
    if not current_url:
        raise ValueError("current_url not set in state")

    artifacts = state.get("artifacts", {})
    artifact = artifacts.get(current_url)
    if not artifact:
        raise ValueError(f"No artifact found for URL: {current_url}")

    # Initialize LLM factory with role-based models
    factory = LLMFactory(config=config, region=config.aws_region)
    reasoning_model = factory.create_reasoning_model()  # Haiku with extended thinking
    vision_model = factory.create_vision_model()        # Sonnet (vision-capable)

    # Extract screenshot path (if available)
    screenshots = state.get("screenshots", {})
    screenshot_path = screenshots.get(current_url)

    # ========================================================================
    # PASS 1: Phase 0 Detection (Initial Discovery)
    # ========================================================================
    logger.info("[Analyst Node] Pass 1: Phase 0 Detection (Initial Discovery)")

    # Apply cost controls: chunk markdown
    markdown_content = artifact.markdown_excerpt or ""
    if not markdown_content:
        logger.warning(f"No markdown content for {current_url}, using empty string")

    # Chunk markdown with cost controls
    keywords = extract_api_keywords()
    markdown_chunks = chunk_markdown(
        markdown_content,
        max_tokens=config.max_tokens_per_chunk,
        prioritize_headings=True,
        prioritize_links=True,
        prioritize_keywords=keywords
    )

    # Select top chunks (cost control)
    top_chunks = select_top_chunks(
        markdown_chunks,
        max_chunks=config.max_chunks_per_page
    )

    # Merge top chunks back into text
    chunked_markdown = merge_chunks(top_chunks)

    logger.info(
        f"[Analyst Node] Chunked markdown: "
        f"{len(markdown_chunks)} total chunks, "
        f"{len(top_chunks)} selected, "
        f"{len(chunked_markdown)} chars"
    )

    # Build Phase 0 prompt
    network_call_urls = urls_from_network_events(artifact.network_events)
    navigation_links = [link.url for link in artifact.links] if artifact.links else []

    phase0_prompt = phase0_single_page_prompt(
        url=current_url,
        page_content=chunked_markdown,
        network_call_urls=network_call_urls,
        navigation_links=navigation_links,
        primary_api_name=state.get('primary_api_name')  # Pass focus control from state
    )

    # Invoke LLM with/without vision
    try:
        if screenshot_path:
            logger.info(f"[Analyst Node] Using vision analysis with screenshot: {screenshot_path}")
            # Combine prompt with markdown context (similar to vision_utils pattern)
            full_prompt = f"{phase0_prompt}\n\n**Markdown Content:**\n{chunked_markdown[:5000]}"
            phase0_result = factory.invoke_structured_with_vision(
                model=vision_model,
                prompt=full_prompt,
                images=[screenshot_path],
                schema=Phase0Detection,
                system="You are analyzing API documentation to discover endpoints."
            )
        else:
            logger.info("[Analyst Node] Using text-only analysis (no screenshot)")
            phase0_result = factory.invoke_structured(
                model=reasoning_model,
                prompt=phase0_prompt,
                schema=Phase0Detection,
                system="You are analyzing API documentation to discover endpoints."
            )

        logger.info(
            f"[Analyst Node] Phase 0 complete: "
            f"Type={phase0_result.detected_type}, "
            f"Confidence={phase0_result.confidence:.2f}, "
            f"Endpoints={len(phase0_result.discovered_endpoint_urls)}"
        )

        # ====================================================================
        # Deterministic Backstop: Coerce WEBSITE→API if signals mismatch
        # ====================================================================
        if phase0_result.detected_type == DataSourceType.WEBSITE:
            # Check for file-browser/download signals
            network_call_urls = urls_from_network_events(artifact.network_events) if artifact else []
            navigation_links = artifact.links if artifact else []

            has_file_browser_signals = any(
                "file-browser" in call.lower() or
                any(ext in call.lower() for ext in [".csv", ".xlsx", ".zip", ".json", ".xml"])
                for call in network_call_urls
            )

            has_download_links = any(
                any(ext in link.url.lower() for ext in [".csv", ".xlsx", ".zip", ".json", ".xml"])
                for link in navigation_links
            )

            # Check for API portal signals
            has_api_signals = any(
                signal in current_url.lower() or any(signal in link.url.lower() for link in navigation_links)
                for signal in ["/developer/apis", "/operations", "/openapi", "/swagger", "/api-docs", "/v1/", "/v2/", "/graphql", "#api=", "#/apis/"]
            )

            # Coerce if no file-browser signals but has API signals
            if not (has_file_browser_signals or has_download_links) and has_api_signals:
                logger.warning(
                    f"[Analyst Node] Coercing WEBSITE→API: "
                    f"No file-browser/download signals found, but API portal signals present"
                )
                phase0_result.detected_type = DataSourceType.API
                phase0_result.confidence = min(0.9, phase0_result.confidence + 0.15)
                phase0_result.indicators.append("Coerced to API: APIM/REST signals present; no WEBSITE download evidence")

    except Exception as e:
        logger.error(f"[Analyst Node] Phase 0 analysis failed: {e}", exc_info=True)
        # Increment failure counter (death spiral prevention)
        consecutive_failures = state.get("consecutive_failures", 0) + 1
        logger.warning(
            f"[Analyst Node] Consecutive failures: {consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}"
        )
        # Return empty results on failure
        return {
            "endpoints": [],
            "queue": state.get("queue", []),
            "consecutive_failures": consecutive_failures
        }

    # ========================================================================
    # Cost Control: Limit endpoints to analyze
    # ========================================================================
    endpoints_to_analyze = phase0_result.discovered_endpoint_urls

    if len(endpoints_to_analyze) > config.max_endpoints_to_analyze:
        logger.warning(
            f"[Analyst Node] Too many endpoints discovered ({len(endpoints_to_analyze)}), "
            f"limiting to {config.max_endpoints_to_analyze}"
        )
        endpoints_to_analyze = endpoints_to_analyze[:config.max_endpoints_to_analyze]

    # ========================================================================
    # PASS 2: Phase 1 Analysis (Per-Endpoint Details)
    # ========================================================================
    logger.info(
        f"[Analyst Node] Pass 2: Phase 1 Analysis "
        f"({len(endpoints_to_analyze)} endpoints)"
    )

    # Build Phase 1 prompt
    phase1_prompt = phase1_documentation_prompt(
        url=current_url,
        page_content=chunked_markdown[:config.max_tokens_per_llm_call * 4],  # ~4 chars/token
        phase0_result=phase0_result,
        discovered_urls=endpoints_to_analyze
    )

    # Invoke LLM for detailed analysis
    try:
        if screenshot_path:
            logger.info("[Analyst Node] Using vision analysis for Phase 1")
            # Combine prompt with markdown context
            full_prompt = f"{phase1_prompt}\n\n**Markdown Content:**\n{chunked_markdown[:5000]}"
            phase1_result = factory.invoke_structured_with_vision(
                model=vision_model,
                prompt=full_prompt,
                images=[screenshot_path],
                schema=Phase1Documentation,
                system="You are analyzing API documentation to extract endpoint details."
            )
        else:
            logger.info("[Analyst Node] Using text-only analysis for Phase 1")
            phase1_result = factory.invoke_structured(
                model=reasoning_model,
                prompt=phase1_prompt,
                schema=Phase1Documentation,
                system="You are analyzing API documentation to extract endpoint details."
            )

        logger.info(
            f"[Analyst Node] Phase 1 complete: "
            f"Extracted {len(phase1_result.endpoints)} endpoint specs"
        )

    except Exception as e:
        logger.error(f"[Analyst Node] Phase 1 analysis failed: {e}", exc_info=True)
        # Fallback: create basic EndpointFinding from Phase 0 results
        phase1_result = None

    # ========================================================================
    # Build EndpointFinding List
    # ========================================================================
    endpoint_findings: List[EndpointFinding] = []

    if phase1_result and phase1_result.endpoints:
        # Use detailed Phase 1 results
        for spec in phase1_result.endpoints:
            finding = _convert_endpoint_spec_to_finding(spec, current_url, phase0_result)
            endpoint_findings.append(finding)
    else:
        # Fallback: use Phase 0 results only
        logger.warning("[Analyst Node] Using Phase 0 results only (Phase 1 failed or empty)")
        for endpoint_url in endpoints_to_analyze:
            finding = EndpointFinding(
                name=_extract_endpoint_name(endpoint_url),
                url=endpoint_url,
                method_guess="unknown",
                auth_required=phase0_result.auth_method if phase0_result.auth_method != "NONE" else "unknown",
                data_type="other",
                format="unknown",
                freshness="unknown",
                pagination="unknown",
                notes=f"Discovered in Phase 0 from {current_url}",
                evidence_urls=[current_url]
            )
            endpoint_findings.append(finding)

    logger.info(f"[Analyst Node] Built {len(endpoint_findings)} endpoint findings")

    # ========================================================================
    # Extract Recommended Links
    # ========================================================================
    recommended_links = _extract_recommended_links(artifact, config)

    logger.info(
        f"[Analyst Node] Extracted {len(recommended_links)} recommended links "
        f"for Link Selector"
    )

    # ========================================================================
    # Return Results
    # ========================================================================
    # After analysis completes, mark URL as analyzed and remove from queue
    current_url = state.get("current_url")
    queue = state.get("queue", [])
    analyzed_urls = state.get("analyzed_urls", set()).copy()  # Copy set to modify

    if current_url:
        # Mark URL as analyzed (sent to AI and completed)
        analyzed_urls.add(current_url)
        logger.info(f"Marked URL as analyzed: {current_url}")

        # Remove current_url from queue (it's been analyzed)
        queue = [link for link in queue if link.get("url") != current_url]
        logger.info(f"Removed analyzed URL from queue: {current_url}")
        logger.debug(f"Queue size: {len(state.get('queue', []))} → {len(queue)}")

    # Success! Reset failure counter
    logger.info("[Analyst Node] Analysis completed successfully - resetting failure counter")

    # P1/P2 BUG FIX: Persist detection results to state for routing
    detected_type = phase0_result.detected_type if phase0_result else None
    confidence = phase0_result.confidence if phase0_result else 0.0
    needs_p1 = detected_type in {DataSourceType.API, DataSourceType.WEBSITE, DataSourceType.FTP} if detected_type else False

    return {
        "endpoints": endpoint_findings,
        "queue": _update_queue_with_links(queue, recommended_links),
        "current_url": None,  # Reset so planner picks next URL
        "last_analyzed_url": current_url,  # P1/P2 Bug #2 fix: Preserve for P1 handlers
        "analyzed_urls": analyzed_urls,  # Update analyzed URLs tracking
        "consecutive_failures": 0,  # Reset on success (death spiral prevention)
        # P1/P2 routing inputs (Bug #1 fix)
        "detected_source_type": detected_type,
        "detection_confidence": confidence,
        "needs_p1_handling": needs_p1,
    }


# _get_llm_from_config() removed - replaced by LLMFactory
# LLMFactory now handles all model creation with role-based selection:
# - create_fast_model() for planner
# - create_reasoning_model() for analysis (Haiku with extended thinking)
# - create_vision_model() for screenshots (Sonnet, vision-capable)


def _convert_endpoint_spec_to_finding(
    spec: EndpointSpec,
    source_url: str,
    phase0_result: Phase0Detection
) -> EndpointFinding:
    """Convert EndpointSpec (Phase 1) to EndpointFinding.

    Args:
        spec: EndpointSpec from Phase 1 analysis
        source_url: Source URL where endpoint was found
        phase0_result: Phase 0 detection results for auth context

    Returns:
        EndpointFinding instance
    """
    # Extract endpoint name from path or use endpoint_id
    name = spec.endpoint_id or _extract_endpoint_name(spec.path)

    # Determine auth requirement
    auth_required = "true" if spec.authentication_mentioned else "unknown"
    if phase0_result.auth_method and phase0_result.auth_method != "NONE":
        auth_required = "true"

    # Map response format
    format_map = {
        "JSON": "json",
        "XML": "xml",
        "CSV": "csv",
        "HTML": "html",
        "BINARY": "binary"
    }
    format_str = format_map.get(spec.response_format.value, "unknown")

    return EndpointFinding(
        name=name,
        url=spec.path,
        method_guess=spec.method.value.lower(),
        auth_required=auth_required,
        data_type="other",  # Could be enhanced with more analysis
        format=format_str,
        freshness="unknown",
        pagination="unknown",
        notes=spec.description,
        evidence_urls=[source_url]
    )


def _extract_endpoint_name(url: str) -> str:
    """Extract a readable name from an endpoint URL.

    Args:
        url: Endpoint URL

    Returns:
        Human-readable endpoint name

    Example:
        >>> _extract_endpoint_name("https://api.example.com/v1/data/pricing")
        'pricing'
    """
    # Remove protocol and domain
    parts = url.split('/')
    # Get last non-empty part
    for part in reversed(parts):
        if part and part not in ['v1', 'v2', 'v3', 'api', 'data']:
            return part.replace('-', ' ').replace('_', ' ').title()

    # Fallback
    return "Endpoint"


def _extract_recommended_links(
    artifact: PageArtifact,
    config: Any
) -> List[LinkInfo]:
    """Extract recommended links from artifact for navigation.

    Filters links by heuristic score and returns high-value links.

    Args:
        artifact: PageArtifact containing discovered links
        config: BAConfig with high_value_threshold

    Returns:
        List of high-value LinkInfo objects
    """
    if not artifact.links:
        return []

    # Filter by heuristic score
    recommended = [
        link for link in artifact.links
        if link.heuristic_score >= config.high_value_threshold
    ]

    # Sort by score (highest first)
    recommended.sort(key=lambda x: x.heuristic_score, reverse=True)

    # Limit to top 10 to avoid queue explosion
    return recommended[:10]


def _update_queue_with_links(
    current_queue: List[Dict],
    recommended_links: List[LinkInfo]
) -> List[Dict]:
    """Update navigation queue with recommended links.

    Adds new links to queue, avoiding duplicates.

    Args:
        current_queue: Current queue of URLs to visit
        recommended_links: New links to add

    Returns:
        Updated queue
    """
    # Build set of existing URLs for deduplication
    existing_urls = {item["url"] for item in current_queue}

    # Add new links
    updated_queue = list(current_queue)

    for link in recommended_links:
        if link.url not in existing_urls:
            updated_queue.append({
                "url": link.url,
                "score": link.heuristic_score,
                "reason": link.reason or "Recommended by analyst"
            })
            existing_urls.add(link.url)

    logger.info(
        f"[Analyst Node] Updated queue: "
        f"{len(current_queue)} → {len(updated_queue)} "
        f"(+{len(updated_queue) - len(current_queue)} new links)"
    )

    return updated_queue
