"""LLM prompt for endpoint classification and ranking (Stage 2 filtering).

This prompt asks the LLM to classify discovered endpoints into categories and rank
them by data relevance. Used in hybrid 3-stage filtering pipeline.
"""

from typing import List
import json

from agentic_scraper.business_analyst.state import EndpointFinding


def endpoint_classification_prompt(
    candidates: List[EndpointFinding],
    seed_url: str,
    auth_summary: str,
    pages_visited: List[str],
    candidate_api_calls: List[str],
    max_endpoints: int
) -> str:
    """Generate prompt for LLM to classify and rank endpoints.

    Args:
        candidates: List of endpoint candidates to classify
        seed_url: Original seed URL being analyzed
        auth_summary: Authentication summary from BA analysis
        pages_visited: List of visited page URLs (context)
        candidate_api_calls: List of discovered API calls from network traffic
        max_endpoints: Maximum endpoints to recommend for generation

    Returns:
        Prompt string for LLM with structured JSON response schema

    The LLM will return JSON with:
        - endpoints: List of classified endpoints with category, confidence, reason
        - top_endpoints_for_generation: List of top N endpoint names (max N)
        - auth_notes: Authentication requirements summary
    """
    # Serialize candidates to JSON for prompt
    candidates_json = []
    for ep in candidates:
        candidates_json.append({
            "name": ep.name,
            "url": ep.url,
            "method_guess": ep.method_guess,
            "format": ep.format,
            "data_type": ep.data_type,
            "notes": ep.notes,
            "evidence_urls": ep.evidence_urls
        })

    prompt = f"""You are analyzing discovered endpoints from a data source to identify which ones are **data endpoints** suitable for scraper generation.

# Critical Rules

1. **ONLY classify endpoints that actually exist in the candidate list** - do not hallucinate or invent endpoints
2. **Use evidence-based reasoning** - reference specific URLs, network calls, or page content
3. **Focus on data collection** - we want endpoints that return data payloads, not portal navigation/auth/system pages
4. **Be conservative** - when in doubt, mark as non-data (AUTH/NAV/SYSTEM)

# Context

**Seed URL**: {seed_url}

**Authentication Summary**: {auth_summary or "Unknown"}

**Pages Visited** ({len(pages_visited)} total):
{json.dumps(pages_visited[:10], indent=2)}  # Show first 10

**Network API Calls Discovered** ({len(candidate_api_calls)} total):
{json.dumps(candidate_api_calls[:20], indent=2)}  # Show first 20

# Endpoint Candidates to Classify

{json.dumps(candidates_json, indent=2)}

# Your Task

Classify each endpoint candidate into ONE of these categories:

- **DATA**: Endpoint returns data payloads relevant to scraping (pricing data, load data, files, datasets)
- **AUTH**: Authentication/authorization endpoints (/login, /signin, /token, /oauth)
- **NAV**: Portal navigation pages (/apis, /products, /resources, /home)
- **SYSTEM**: System/monitoring endpoints (/health, /trace, /config, /metrics)
- **UNKNOWN**: Cannot determine from available evidence

For each endpoint, provide:
- `category`: One of DATA, AUTH, NAV, SYSTEM, UNKNOWN
- `keep_for_generation`: Boolean - true ONLY if category=DATA and endpoint is relevant
- `confidence`: Float 0.0-1.0 representing classification confidence
- `reason`: Evidence-based explanation referencing specific URLs, notes, or patterns

Then recommend the **top {max_endpoints} data endpoints** for scraper generation (ranked by relevance).

# Response Format

Return **ONLY** valid JSON (no markdown, no explanations outside JSON):

{{
  "endpoints": [
    {{
      "name": "pricing-api",
      "category": "DATA",
      "keep_for_generation": true,
      "confidence": 0.95,
      "reason": "Real-time energy pricing endpoint. Evidence: URL contains '#api=pricing-api', notes mention MCP (Market Clearing Price) data, format is JSON."
    }},
    {{
      "name": "signin",
      "category": "AUTH",
      "keep_for_generation": false,
      "confidence": 0.99,
      "reason": "Authentication page. Evidence: URL path '/signin', notes say 'User sign in page'."
    }},
    {{
      "name": "apis",
      "category": "NAV",
      "keep_for_generation": false,
      "confidence": 0.90,
      "reason": "Portal navigation page. Evidence: URL path '/apis', notes say 'API documentation and exploration page', format is HTML not JSON/data."
    }}
  ],
  "top_endpoints_for_generation": ["pricing-api", "load-generation-api"],
  "auth_notes": "Bearer token authentication required. Token endpoint: POST /token. Registration available at /signup."
}}

# Important Notes

- **top_endpoints_for_generation** must contain ≤{max_endpoints} endpoint names
- **top_endpoints_for_generation** must ONLY include endpoints where keep_for_generation=true
- All endpoint names in **top_endpoints_for_generation** must exist in the candidates list
- **auth_notes** should extract authentication details from AUTH-categorized endpoints (token URLs, methods, registration info)
- If NO data endpoints found, return empty list for top_endpoints_for_generation

Begin classification now. Return ONLY the JSON response.
"""

    return prompt
