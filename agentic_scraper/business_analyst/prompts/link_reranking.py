"""Link reranking prompt for LLM-based refinement.

This module provides the prompt for Pass 2 of link selection, where
the LLM refines the heuristic scores by analyzing link context and
providing nuanced scoring based on API discovery goals.
"""

from typing import List


def link_reranking_prompt(
    links: List[dict],
    seed_url: str,
    current_findings: str = ""
) -> str:
    """Generate prompt for LLM-based link reranking.

    This prompt asks the LLM to rerank links that passed the heuristic
    filter, providing nuanced scoring and rationale based on:
    - API discovery goals
    - Link text and URL patterns
    - Current findings (what we already know)
    - Likelihood of finding new endpoints

    Args:
        links: List of link dicts with 'url', 'text', 'heuristic_score'
        seed_url: Original seed URL for context
        current_findings: Summary of what has been discovered so far

    Returns:
        Formatted prompt string for LLM

    Example:
        >>> links = [
        ...     {"url": "https://api.example.com/docs", "text": "API Docs", "heuristic_score": 0.9}
        ... ]
        >>> prompt = link_reranking_prompt(links, "https://api.example.com")
    """
    # Build links table
    links_table = []
    for i, link in enumerate(links, 1):
        url = link.get('url', '')
        text = link.get('text', '')
        heuristic = link.get('heuristic_score', 0.0)
        links_table.append(f"{i}. [{text}]({url})\n   Heuristic: {heuristic:.2f}")

    links_str = "\n".join(links_table)

    # Build current findings context
    findings_context = ""
    if current_findings:
        findings_context = f"""
## Current Findings

{current_findings}

Based on what we've already discovered, prioritize links that are likely to reveal NEW information.
"""

    prompt = f"""You are analyzing links from a website to discover API endpoints and data sources.

## Goal

Rerank these links to prioritize the most valuable ones for API discovery. Your task is to:
1. Assign each link a score from 0.0 to 1.0
2. Provide a brief rationale explaining your score
3. Consider both the heuristic score and your semantic understanding

## Context

**Seed URL**: {seed_url}
{findings_context}

## Links to Rerank

{links_str}

## Scoring Guidelines

**High scores (0.8-1.0)**: Links likely to contain:
- API documentation (Swagger, OpenAPI, WADL)
- Endpoint listings or references
- Data download pages (CSV, JSON, XML)
- Developer portals or API consoles
- Technical specifications

**Medium scores (0.5-0.7)**: Links that may contain:
- General documentation with possible API mentions
- Data sections or resource pages
- Technical blogs or guides
- FAQ or help pages about APIs

**Low scores (0.0-0.4)**: Links unlikely to help:
- Marketing/sales pages
- About/company information
- Legal/privacy pages
- User accounts/login pages
- Social media links

## Important Considerations

1. **Avoid redundancy**: If we've already found comprehensive API docs, deprioritize similar links
2. **Favor specificity**: "REST API Reference" > "Documentation"
3. **Look for data formats**: Links mentioning CSV, JSON, XML, XLSX are high value
4. **Consider navigation**: Links in main nav or sidebar are usually more important than footer links
5. **URL patterns matter**: /api/, /docs/, /reference/ in URLs are strong signals

## Output Format

For each link, return:
- url: The exact URL from the input
- text: The exact link text from the input
- llm_score: Your score (0.0-1.0)
- llm_rationale: Brief explanation (1-2 sentences)

Be concise but specific in your rationale. Focus on WHY the link is valuable or not.
"""

    return prompt


# Export public API
__all__ = [
    'link_reranking_prompt',
]
