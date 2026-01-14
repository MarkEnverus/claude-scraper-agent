"""Phase 2 prompts for BA Analyst - Live endpoint testing and validation.

Migrated from agentic_scraper/prompts/ba_analyzer.py (phase2_prompt).
These prompts handle analysis of live endpoint test results to validate authentication
requirements and endpoint behavior.
"""

from typing import Any


def phase2_testing_prompt(
    url: str,
    test_results_content: str,
    phase0_result: Any,
    phase1_result: Any
) -> str:
    """Phase 2: Live endpoint testing analysis prompt.

    Analyzes the results of live endpoint testing to validate API behavior.

    Args:
        url: Target URL being analyzed
        test_results_content: Compact summary of test results
        phase0_result: Results from Phase 0
        phase1_result: Results from Phase 1

    Returns:
        Formatted prompt string for Claude
    """
    detected_type = phase0_result.detected_type
    endpoint_count = len(phase1_result.endpoints) if hasattr(phase1_result, 'endpoints') else 0

    return f"""You are analyzing the results of live endpoint testing to validate API behavior.

URL: {url}
Detected Type: {detected_type}
Endpoints Tested: {endpoint_count}

Test Results Summary:
{test_results_content}

Analyze the test results and determine:

1. Test Results Map:
   - For each endpoint tested, document:
     - http_status: HTTP status code received
     - response_snippet: First 500 chars of response
     - auth_keywords_found: List of auth-related keywords in response
     - full_output_file: Path to full test output file

2. Test Conclusion:
   - auth_required: Is authentication required? (based on 401/403 responses)
   - evidence: What evidence supports this conclusion? CRITICAL: Include exact auth header name if detected (e.g., "Authorization", "X-API-Key", "Ocp-Apim-Subscription-Key")
     * Extract from response headers (WWW-Authenticate, error messages mentioning missing headers)
     * Check Phase 1 auth_header_examples for documented headers
     * Example: "401 response with 'Missing Ocp-Apim-Subscription-Key header' indicates Ocp-Apim-Subscription-Key header required"
   - likely_auth_method: Most likely auth method (NONE, API_KEY, BEARER_TOKEN, OAUTH, BASIC_AUTH, COOKIE, UNKNOWN)
   - confidence: Confidence level (HIGH, MEDIUM, LOW)

3. Files Saved:
   - List of test output files generated

DECISION MATRIX FOR STATUS CODES:
- 200 OK: Endpoint accessible, no auth required
- 401 Unauthorized: Auth definitely required
- 403 Forbidden: Auth required or endpoint restricted
- 404 Not Found: Endpoint doesn't exist (may be documentation error)
- 429 Too Many Requests: Rate limited (retry needed)
- 500/502/503: Server error (retry needed)

IMPORTANT:
- Base conclusions on ACTUAL test results, not assumptions
- If multiple endpoints have consistent behavior, note patterns
- Distinguish between "no auth" (200) and "unknown" (errors)
- Report any unexpected behaviors or discrepancies

Return your analysis as JSON matching the Phase2Tests schema."""
