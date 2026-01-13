"""Phase 1 prompts for BA Analyst - Documentation and metadata extraction.

Migrated from agentic_scraper/prompts/ba_analyzer.py (phase1_prompt and analyze_endpoint_prompt).
These prompts handle detailed documentation analysis and individual endpoint extraction.
"""

from typing import Any, Optional


def phase1_documentation_prompt(
    url: str,
    page_content: str,
    phase0_result: Any,
    discovered_urls: Optional[list[str]] = None
) -> str:
    """Phase 1: Documentation/metadata extraction prompt.

    Extracts detailed endpoint specifications from API documentation.

    Args:
        url: Target URL being analyzed
        page_content: Structured/preprocessed HTML content
        phase0_result: Results from Phase 0 detection
        discovered_urls: Full endpoint URLs discovered by Phase 0 botasaurus

    Returns:
        Formatted prompt string for Claude
    """
    detected_type = phase0_result.detected_type
    confidence = phase0_result.confidence
    base_url = phase0_result.base_url

    # Format discovered URLs section
    discovered_urls_section = ""
    if discovered_urls:
        urls_list = '\n'.join(f"  - {u}" for u in discovered_urls[:20])
        if len(discovered_urls) > 20:
            urls_list += f"\n  ... and {len(discovered_urls) - 20} more"
        discovered_urls_section = f"""

**IMPORTANT: Phase 0 discovered {len(discovered_urls)} endpoint URLs via browser analysis:**
{urls_list}

**YOUR TASK:**
For each endpoint you extract:
1. Use the FULL URLs from Phase 0's discovered list above
2. Enrich with metadata from the documentation (parameters, descriptions, auth requirements)
3. Store the FULL URL in the 'path' field (e.g., "https://api.example.com/v1/data")
4. Do NOT extract relative paths from the HTML

If you find endpoints in the documentation that aren't in Phase 0's list:
- Extract the full URL by combining the base_url with the path
- Still store as a full URL in 'path' field
"""

    return f"""You are analyzing API documentation to extract detailed endpoint specifications.

URL: {url}
Detected Source Type: {detected_type}
Detection Confidence: {confidence}
Base URL: {base_url}

Documentation Content:
{page_content}
{discovered_urls_section}

Extract detailed information about each endpoint:

1. Endpoint Discovery:
   - Total endpoints found
   - Extraction method used
   - Whether systematic enumeration was completed

2. Authentication Claims:
   - Whether auth section was found
   - What auth methods are mentioned
   - Whether API keys or subscriptions are mentioned
   - Example auth headers if provided

3. For Each Endpoint:
   - endpoint_id: Unique identifier
   - path: Full URL including protocol and domain (e.g., "https://api.example.com/v1/data")
          Do NOT use relative paths like "/v1/data"
   - method: HTTP method (GET, POST, etc.)
   - description: What data it returns
   - parameters: List of parameters (name, type, required, description, example)
   - response_format: JSON, XML, CSV, HTML, or BINARY
   - authentication_mentioned: Whether auth is mentioned for this endpoint

4. Documentation Quality:
   - Assess overall doc quality: EXCELLENT, HIGH, MEDIUM, LOW, or POOR
   - Based on completeness, clarity, and examples provided

5. Notes:
   - Any important observations
   - Limitations or missing information
   - Rate limits or usage restrictions

IMPORTANT:
- Extract ONLY information visible in the documentation
- Don't make assumptions about parameters or formats
- If documentation is sparse, note it in the quality assessment
- Focus on extracting structured, actionable information

Return your analysis as JSON matching the Phase1Documentation schema."""


def analyze_endpoint_prompt(
    endpoint_url: str,
    page_context: str,
    auth_method: str,
    base_url: str
) -> str:
    """Individual endpoint analysis prompt (for Phase 1).

    Used when analyzing endpoints one-by-one rather than in bulk.

    Args:
        endpoint_url: Specific endpoint URL to analyze
        page_context: Page context for reference
        auth_method: Detected authentication method
        base_url: Base URL of the API

    Returns:
        Formatted prompt string for Claude
    """
    return f"""You are analyzing a SINGLE API endpoint in detail.

Endpoint URL: {endpoint_url}
Base URL: {base_url}
Auth Method: {auth_method}

Page Context (for reference):
{page_context}

Analyze this specific endpoint and extract:

1. Endpoint URL: {endpoint_url} (exactly as provided)

2. Path: Extract the path part from the endpoint URL
   - Example: For "https://api.example.com/data/v1/resource-a"
   - Path is "/data/v1/resource-a"

3. HTTP Method: Determine the HTTP method for this endpoint
   - Look for: GET, POST, PUT, DELETE, PATCH
   - Default to GET if not explicitly mentioned

4. Parameters: Extract ALL parameters for this endpoint
   For each parameter, document:
   - name: Parameter name (e.g., "date", "node", "market")
   - type: Data type (string, int, float, bool, date)
   - required: Is it required? (true/false)
   - description: What does it do?
   - example: Example value if available

5. Response Format: What format does this endpoint return?
   - JSON, XML, CSV, HTML, or BINARY

6. Description: Brief description of what this endpoint does
   - 1-2 sentences maximum
   - Focus on WHAT DATA it returns

7. Auth Required: Does this endpoint require authentication?
   - Based on the auth_method parameter provided
   - true if auth_method is not "NONE"

CRITICAL RULES:
✅ ONLY extract information you can SEE about this specific endpoint
❌ DO NOT make up parameters - only document visible ones
❌ DO NOT guess response format - look for examples or indicators
✅ If uncertain about a field, use reasonable defaults:
   - Parameters: Empty list if none visible
   - Description: Generic based on endpoint name
   - Response format: JSON (most common for APIs)

Return your analysis as JSON matching the EndpointAnalysis schema."""
