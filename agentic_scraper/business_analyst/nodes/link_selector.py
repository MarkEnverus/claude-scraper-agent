"""Link Selector Node for BA Analyst LangGraph.

This module implements the Link Selector node, which is responsible for:
1. **Pass 1**: Deterministic heuristic scoring of discovered links (fast, testable)
2. **Pass 2**: LLM-based reranking of top candidates (refinement only)
3. Filtering by domain, depth, and visit status
4. Stop condition detection when no high-value links remain

The two-pass approach balances cost control with quality:
- Heuristic scoring handles the bulk of links quickly
- LLM refinement focuses only on top candidates (top 20)
- Both scores are preserved for debugging and audit trails
"""

import logging
from typing import Dict, Optional, List

from agentic_scraper.business_analyst.state import (
    BAAnalystState,
    LinkInfo,
    LinkRerankResult,
)
from agentic_scraper.business_analyst.config import BAConfig
from agentic_scraper.business_analyst.prompts.link_reranking import link_reranking_prompt
from agentic_scraper.business_analyst.utils.link_scoring import (
    score_and_sort_links,
    filter_links_by_domain,
    filter_visited_links,
)

logger = logging.getLogger(__name__)


def link_selector_node(state: BAAnalystState) -> Dict:
    """Link Selector Node - Two-pass scoring and filtering of discovered links.

    This node implements a two-pass link selection strategy:

    **Pass 1: Heuristic Scoring** (deterministic, fast)
    - Apply rule-based scoring to all discovered links
    - Filter by domain, visit status, and minimum score
    - Remove links that fail basic criteria

    **Pass 2: LLM Reranking** (top 20 only)
    - Use LLM to refine scores for top candidates
    - Get nuanced reasoning about link relevance
    - Combine heuristic + LLM scores (average)

    **Stop Condition Detection**:
    - If no links pass filtering, set stop_reason
    - If current_depth >= max_depth, set stop_reason
    - Otherwise, queue is updated with scored links

    Args:
        state: BAAnalystState containing:
            - queue: Current link queue (may be empty or contain old links)
            - visited: Set of visited URLs
            - current_depth: Current navigation depth
            - seed_url: Original seed URL
            - allowed_domains: List of allowed domains
            - config: BAConfig with max_depth and thresholds

    Returns:
        Dict with updated:
        - queue: List of scored link dicts sorted by combined_score descending
        - stop_reason: Set if no high-value links remain or depth exceeded
        - next_action: "stop" if stop_reason is set, None otherwise

    Each link in the queue contains:
    - url: Absolute URL
    - text: Link text
    - heuristic_score: Rule-based score (0-1)
    - llm_score: LLM score (0-1) or None if not reranked
    - combined_score: Average of heuristic + llm_score
    - reason: Heuristic reasoning
    - llm_rationale: LLM reasoning or None

    Example:
        >>> state = {
        ...     "queue": [{"url": "...", "text": "..."}],
        ...     "visited": {"https://example.com"},
        ...     "current_depth": 1,
        ...     "max_depth": 3,
        ...     "seed_url": "https://example.com",
        ...     "allowed_domains": [],
        ...     "config": BAConfig()
        ... }
        >>> result = link_selector_node(state)
        >>> print(f"Selected {len(result['queue'])} links")
    """
    logger.info("=" * 80)
    logger.info("LINK SELECTOR NODE - Starting two-pass link selection")
    logger.info("=" * 80)

    # Extract state variables
    queue = state.get("queue", [])
    visited = state.get("visited", set())
    current_depth = state.get("current_depth", 0)
    seed_url = state.get("seed_url", "")
    allowed_domains = state.get("allowed_domains", [])
    config: Optional[BAConfig] = state.get("config")

    # Get config values
    if config:
        max_depth = config.max_depth
        min_score = config.high_value_threshold
    else:
        max_depth = state.get("max_depth", 3)
        min_score = 0.5

    logger.info(f"Input: {len(queue)} links in queue, {len(visited)} visited, depth {current_depth}/{max_depth}")

    # Check depth limit
    if current_depth >= max_depth:
        logger.warning(f"Max depth reached: {current_depth} >= {max_depth}")
        return {
            "queue": [],
            "stop_reason": f"Maximum depth reached ({max_depth})",
            "next_action": "stop"
        }

    # ========================================================================
    # PASS 1: HEURISTIC SCORING
    # ========================================================================
    logger.info("-" * 80)
    logger.info("PASS 1: Heuristic Scoring (deterministic)")
    logger.info("-" * 80)

    # Convert queue items to link dicts if needed
    links = []
    for item in queue:
        if isinstance(item, dict):
            # Already a dict
            links.append(item)
        else:
            # Convert to dict (shouldn't happen, but handle gracefully)
            logger.warning(f"Unexpected queue item type: {type(item)}")
            links.append({"url": str(item), "text": ""})

    logger.info(f"Processing {len(links)} links from queue")

    # Filter by domain
    links = filter_links_by_domain(links, allowed_domains, seed_url)
    logger.info(f"After domain filter: {len(links)} links")

    # Filter already visited
    links = filter_visited_links(links, visited)
    logger.info(f"After visited filter: {len(links)} links")

    # Check if we have any links left
    if not links:
        logger.warning("No links remain after filtering")
        return {
            "queue": [],
            "stop_reason": "No unvisited links remain in allowed domains",
            "next_action": "stop"
        }

    # Apply heuristic scoring and sorting
    scored_links = score_and_sort_links(
        links=links,
        seed_url=seed_url,
        visited=visited,
        min_score=min_score
    )

    logger.info(f"After heuristic scoring: {len(scored_links)} links above threshold {min_score}")

    # Check if we have any high-value links
    if not scored_links:
        logger.warning(f"No links scored above threshold {min_score}")
        return {
            "queue": [],
            "stop_reason": f"No links scored above threshold {min_score}",
            "next_action": "stop"
        }

    # Log top heuristic scores
    logger.info("Top 5 heuristic scores:")
    for i, link in enumerate(scored_links[:5], 1):
        url = link.get('url', '')[:60]
        score = link.get('heuristic_score', 0.0)
        reason = link.get('reason', '')
        logger.info(f"  {i}. {score:.2f} - {url}... ({reason})")

    # ========================================================================
    # PASS 2: LLM RERANKING (top 20 only)
    # ========================================================================
    logger.info("-" * 80)
    logger.info("PASS 2: LLM Reranking (top 20 candidates)")
    logger.info("-" * 80)

    # Take top 20 for LLM reranking (cost control)
    top_n = 20
    rerank_candidates = scored_links[:top_n]
    remaining_links = scored_links[top_n:]

    logger.info(f"Reranking {len(rerank_candidates)} links, keeping {len(remaining_links)} with heuristic scores only")

    # Build current findings summary for context
    endpoints = state.get("endpoints", [])
    findings_summary = ""
    if endpoints:
        findings_summary = f"Found {len(endpoints)} endpoints so far:\n"
        for ep in endpoints[:3]:  # First 3 as examples
            findings_summary += f"- {ep.name} ({ep.url})\n"

    # Create LLM for structured reranking (using LangChain)
    try:
        from agentic_scraper.business_analyst.llm_factory import create_chatbedrock_with_reasoning

        if config:
            llm = create_chatbedrock_with_reasoning(config)
        else:
            from langchain_aws import ChatBedrockConverse
            llm = ChatBedrockConverse(
                model="us.anthropic.claude-3-5-haiku-20241022-v1:0",
                temperature=1.0,
                region="us-east-1"
            )

        # Generate reranking prompt
        prompt = link_reranking_prompt(
            links=rerank_candidates,
            seed_url=seed_url,
            current_findings=findings_summary
        )

        logger.info("Invoking LLM for link reranking...")

        # Call LLM with structured output (LangChain method)
        structured_llm = llm.with_structured_output(LinkRerankResult)
        rerank_result = structured_llm.invoke(prompt)

        logger.info(f"LLM returned {len(rerank_result.links)} reranked links")

        # Merge LLM scores back into links
        reranked_links = _merge_llm_scores(rerank_candidates, rerank_result.links)

        logger.info("Top 5 combined scores after LLM reranking:")
        for i, link_info in enumerate(reranked_links[:5], 1):
            url = link_info.url[:60]
            logger.info(f"  {i}. {link_info.combined_score:.2f} (H:{link_info.heuristic_score:.2f}, "
                       f"L:{link_info.llm_score:.2f}) - {url}...")
            logger.info(f"     LLM: {link_info.llm_rationale}")

    except Exception as e:
        logger.error(f"LLM reranking failed: {e}", exc_info=True)
        logger.warning("Falling back to heuristic scores only")
        # Convert to LinkInfo without LLM scores
        reranked_links = _convert_to_link_info(rerank_candidates)

    # Convert remaining links to LinkInfo (no LLM scores)
    remaining_link_infos = _convert_to_link_info(remaining_links)

    # Combine reranked and remaining links
    all_links = reranked_links + remaining_link_infos

    # Sort by combined_score (defaulting to heuristic_score if combined_score is None)
    all_links.sort(
        key=lambda x: x.combined_score if x.combined_score is not None else x.heuristic_score,
        reverse=True
    )

    logger.info(f"Final link selection: {len(all_links)} links ready for queueing")

    # Convert LinkInfo back to dict format for queue
    queue_dicts = [_link_info_to_dict(link) for link in all_links]

    # ========================================================================
    # RETURN UPDATED STATE
    # ========================================================================
    logger.info("=" * 80)
    logger.info(f"LINK SELECTOR COMPLETE - {len(queue_dicts)} links in queue")
    logger.info("=" * 80)

    return {
        "queue": queue_dicts,
        "stop_reason": None,
        "next_action": None
    }


def _merge_llm_scores(
    original_links: List[dict],
    llm_links: List[LinkInfo]
) -> List[LinkInfo]:
    """Merge LLM scores into original links.

    Matches links by URL and combines heuristic + LLM scores.

    Args:
        original_links: Original link dicts with heuristic scores
        llm_links: LinkInfo objects with LLM scores from reranking

    Returns:
        List of LinkInfo objects with combined scores
    """
    # Build lookup by URL
    llm_by_url = {link.url: link for link in llm_links}

    merged = []
    for orig in original_links:
        url = orig.get('url', '')
        text = orig.get('text', '')
        heuristic_score = orig.get('heuristic_score', 0.0)
        reason = orig.get('reason', '')

        # Check if LLM scored this link
        if url in llm_by_url:
            llm_link = llm_by_url[url]
            llm_score = llm_link.llm_score or 0.0
            llm_rationale = llm_link.llm_rationale or ""

            # Combine scores (average)
            combined_score = (heuristic_score + llm_score) / 2.0

            link_info = LinkInfo(
                url=url,
                text=text,
                heuristic_score=heuristic_score,
                llm_score=llm_score,
                combined_score=combined_score,
                reason=reason,
                llm_rationale=llm_rationale
            )
        else:
            # No LLM score, use heuristic only
            link_info = LinkInfo(
                url=url,
                text=text,
                heuristic_score=heuristic_score,
                llm_score=None,
                combined_score=heuristic_score,  # Use heuristic as combined
                reason=reason,
                llm_rationale=None
            )

        merged.append(link_info)

    # Sort by combined score
    merged.sort(key=lambda x: x.combined_score or x.heuristic_score, reverse=True)

    return merged


def _convert_to_link_info(links: List[dict]) -> List[LinkInfo]:
    """Convert link dicts to LinkInfo objects (no LLM scores).

    Args:
        links: List of link dicts with heuristic scores

    Returns:
        List of LinkInfo objects
    """
    link_infos = []
    for link in links:
        url = link.get('url', '')
        text = link.get('text', '')
        heuristic_score = link.get('heuristic_score', 0.0)
        reason = link.get('reason', '')

        link_info = LinkInfo(
            url=url,
            text=text,
            heuristic_score=heuristic_score,
            llm_score=None,
            combined_score=heuristic_score,  # Use heuristic as combined
            reason=reason,
            llm_rationale=None
        )
        link_infos.append(link_info)

    return link_infos


def _link_info_to_dict(link_info: LinkInfo) -> dict:
    """Convert LinkInfo to dict for queue storage.

    Args:
        link_info: LinkInfo object

    Returns:
        Dictionary with all link metadata
    """
    return {
        "url": link_info.url,
        "text": link_info.text,
        "heuristic_score": link_info.heuristic_score,
        "llm_score": link_info.llm_score,
        "combined_score": link_info.combined_score,
        "reason": link_info.reason,
        "llm_rationale": link_info.llm_rationale
    }


def filter_links_for_tool(
    links: list[dict],
    seed_url: str,
    goal: str = "Find API documentation and data sources",
    max_results: int = 20,
    config: Optional[BAConfig] = None
) -> list[dict]:
    """Filter links for use in tools (simplified version of link_selector_node).

    This is a lightweight version of link_selector_node for use in tools.
    Does NOT require full BAAnalystState - works with raw link lists.

    Args:
        links: Raw link dicts from Botasaurus (with href, text, etc.)
        seed_url: Starting URL for context
        goal: Analysis goal for LLM context
        max_results: Max links to return
        config: Optional BAConfig

    Returns:
        Filtered list of top links (max_results)
    """
    logger.info(f"Filtering {len(links)} links with AI (max_results={max_results})")

    # Convert to LinkInfo format for scoring
    link_infos = []
    for link in links:
        link_infos.append(LinkInfo(
            url=link.get("href", ""),
            text=link.get("text", ""),
            source=link.get("source", "content"),
            heuristic_score=0.0
        ))

    # Pass 1: Heuristic scoring
    from agentic_scraper.business_analyst.utils.link_scoring import score_and_sort_links
    scored_links = score_and_sort_links(link_infos, seed_url)
    logger.info(f"Heuristic scoring complete, top score: {scored_links[0].heuristic_score:.2f if scored_links else 0}")

    # Take top N for LLM reranking
    top_n = min(20, len(scored_links))
    rerank_candidates = scored_links[:top_n]

    # Pass 2: LLM reranking (using LangChain)
    try:
        from agentic_scraper.business_analyst.llm_factory import create_chatbedrock_with_reasoning

        if config:
            llm = create_chatbedrock_with_reasoning(config)
        else:
            from langchain_aws import ChatBedrockConverse
            llm = ChatBedrockConverse(
                model="us.anthropic.claude-3-5-haiku-20241022-v1:0",
                temperature=1.0,
                region="us-east-1"
            )

        # Use with_structured_output
        structured_llm = llm.with_structured_output(LinkRerankResult)

        # Convert LinkInfo to dict format for prompt
        rerank_dicts = []
        for link in rerank_candidates:
            rerank_dicts.append({
                'url': link.url,
                'text': link.text,
                'heuristic_score': link.heuristic_score
            })

        prompt = link_reranking_prompt(
            links=rerank_dicts,
            seed_url=seed_url,
            current_findings=goal
        )

        logger.info("Invoking LLM for link reranking...")
        rerank_result = structured_llm.invoke(prompt)
        logger.info(f"LLM returned {len(rerank_result.links)} reranked links")

        # Merge scores
        reranked = _merge_llm_scores(rerank_dicts, rerank_result.links)

        # Sort by combined score
        reranked.sort(
            key=lambda x: x.combined_score if x.combined_score else x.heuristic_score,
            reverse=True
        )

        # Convert back to dict format
        result_links = [_link_info_to_dict(link) for link in reranked[:max_results]]
        logger.info(f"Filtered to {len(result_links)} high-value links")
        return result_links

    except Exception as e:
        logger.warning(f"LLM reranking failed, using heuristic only: {e}")
        # Fallback: use heuristic scores only
        result_links = []
        for link in scored_links[:max_results]:
            result_links.append({
                "href": link.url,
                "text": link.text,
                "heuristic_score": link.heuristic_score,
                "reason": f"Heuristic score: {link.heuristic_score:.2f}"
            })
        logger.info(f"Fallback: returning {len(result_links)} links based on heuristic only")
        return result_links


# Export public API
__all__ = [
    'link_selector_node',
    'filter_links_for_tool',  # New export
]
