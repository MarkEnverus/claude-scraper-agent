"""Phase 3 prompts for BA Analyst - Validated specification generation and executive summary.

Migrated from agentic_scraper/prompts/ba_analyzer.py (phase3_prompt and executive_summary_prompt).
These prompts handle cross-phase validation and final specification generation.
"""

from typing import Any, Dict


def phase3_validation_prompt(
    url: str,
    phase0: Any,
    phase1: Any,
    phase2: Any
) -> str:
    """Phase 3: Validated specification generation prompt.

    Cross-checks all phases to produce a validated specification.

    Args:
        url: Target URL being analyzed
        phase0: Phase 0 detection results
        phase1: Phase 1 documentation results
        phase2: Phase 2 testing results

    Returns:
        Formatted prompt string for Claude
    """
    detected_type = phase0.detected_type
    confidence = phase0.confidence
    endpoint_count = len(phase1.endpoints) if hasattr(phase1, 'endpoints') else 0

    # Get auth findings from phase2
    auth_required = False
    auth_method = "NONE"
    if hasattr(phase2, 'conclusion') and phase2.conclusion:
        auth_required = phase2.conclusion.auth_required
        auth_method = phase2.conclusion.likely_auth_method

    return f"""You are creating a final validated specification by cross-checking all analysis phases.

URL: {url}
Detected Type: {detected_type}
Endpoints Found: {endpoint_count}
Auth Required: {auth_required}
Auth Method: {auth_method}

Phase 0 (Detection):
- Type: {detected_type}
- Confidence: {confidence}
- Base URL: {phase0.base_url}

Phase 1 (Documentation):
- Endpoints documented: {endpoint_count}
- Doc quality: {phase1.doc_quality if hasattr(phase1, 'doc_quality') else 'UNKNOWN'}

Phase 2 (Testing):
- Auth conclusion: {auth_required}
- Auth method: {auth_method}

Auth Validation Logic:
- If Phase 0 predicted auth ({phase0.auth_method}) AND Phase 2 found 401 responses:
  → This CONFIRMS the auth requirement (HIGH confidence)
  → 401 Unauthorized means "endpoint exists, auth required" (GOOD outcome)
  → confidence_score should be 0.85 or higher
- If Phase 0 predicted NO auth AND Phase 2 found 200 responses:
  → This CONFIRMS no auth needed (HIGH confidence)
- If Phase 0 prediction does NOT match Phase 2 results:
  → This is a discrepancy (MEDIUM/LOW confidence)

Cross-check all phases and create a validated specification:

1. Executive Summary:
   - total_endpoints_discovered: Total endpoints found
   - accessible_endpoints: Endpoints that returned 200 OK
   - protected_endpoints: Endpoints that returned 401/403
   - broken_endpoints: Endpoints that returned 404/500
   - success_rate: Percentage of working endpoints
   - primary_formats: List of response formats (JSON, XML, etc.)
   - authentication_required: Boolean
   - estimated_scraper_complexity: LOW, MEDIUM, or HIGH

2. Validation Summary:
   - phases_completed: List of completed phases
   - documentation_review: Summary of doc review
   - live_api_testing: Summary of testing
   - discrepancies_found: Count of discrepancies
   - confidence_score: Overall confidence (0.0-1.0)
     * HIGH (0.85+): Auth predicted and confirmed by 401s, OR no auth predicted and confirmed by 200s
     * MEDIUM (0.6-0.84): Some discrepancies but endpoints discovered
     * LOW (0.0-0.59): Major discrepancies or most endpoints failed
   - confidence_level: HIGH, MEDIUM, or LOW
   - recommendation: Final recommendation

3. Authentication Spec:
   - required: Boolean
   - method: Auth method enum
   - header_name: Extract using fallback chain (CRITICAL for scraper generation):
     1. Check Phase 2 conclusion.evidence for header name mentions (e.g., "Ocp-Apim-Subscription-Key", "Authorization", "X-API-Key")
     2. Fallback to Phase 1 auth_claims.auth_header_examples[0] if available
     3. Fallback to Phase 1 auth_claims.conclusion text for header name patterns
     4. Default based on auth_method: BEARER_TOKEN/BASIC_AUTH → "Authorization", API_KEY → "X-API-Key"
   - evidence: Evidence supporting auth conclusion (combine Phase 1 and Phase 2 findings)
   - registration_url: Where to register if found
   - notes: Additional auth notes

4. Endpoint Details:
   For each endpoint, create EndpointDetails with:
   - endpoint_id: MUST preserve EXACTLY from Phase 1 without any modification (copy character-for-character, do NOT simplify or rename)
   - name: Use the endpoint_id value or create human-readable version
   - type, base_url, path, method: From Phase 1
   - parameters (from Phase 1)
   - authentication details
   - response_format
   - validation_status (from Phase 2 test results)
   - accessible (true if 200 OK)
   - last_tested (timestamp)
   - notes

   CRITICAL: DO NOT modify endpoint_id values in ANY way. Copy them EXACTLY character-for-character from Phase 1. Do NOT simplify, shorten, rename, or reformat them.

5. Scraper Recommendation:
   - type: WEBSITE_PARSER, HTTP_COLLECTOR, API_CLIENT, or FTP_CLIENT
   - confidence: Confidence level
   - rationale: List of reasons for this recommendation
   - complexity: LOW, MEDIUM, or HIGH
   - estimated_effort: Time estimate
   - key_challenges: List of implementation challenges

6. Discrepancies:
   List any discrepancies between phases:
   - type: Type of discrepancy
   - documentation_said: What Phase 1 said
   - api_testing_showed: What Phase 2 showed
   - severity: HIGH, MEDIUM, or LOW
   - resolution: How to resolve it

7. Next Steps:
   - List recommended next steps for scraper implementation

8. Generate identifiers:
   - datasource: Snake_case datasource identifier (e.g., "example_service")
   - dataset: Snake_case dataset identifier (e.g., "data")

IMPORTANT:
- Cross-check all phases for consistency
- Flag any conflicts between documentation and testing
- Be conservative with confidence scores if discrepancies exist
- Provide actionable recommendations

Return your analysis as JSON matching the ValidatedSpec schema."""


def executive_summary_prompt(
    validation_stats: Dict,
    phase0: Any,
    phase1: Any,
    phase2: Any
) -> str:
    """Lightweight prompt for AI insights only (optimized Phase 3).

    This prompt is used instead of the full phase3_validation_prompt to avoid
    sending massive amounts of data and timing out. Programmatic validation
    has already been done, so we only need AI for qualitative insights.

    Args:
        validation_stats: Pre-calculated validation statistics
        phase0: Phase 0 detection results
        phase1: Phase 1 documentation results
        phase2: Phase 2 testing results

    Returns:
        Formatted prompt string for Claude to generate Phase3Insights
    """
    auth_required = phase2.conclusion.auth_required if hasattr(phase2, 'conclusion') else False
    auth_method = phase2.conclusion.likely_auth_method if hasattr(phase2, 'conclusion') else "UNKNOWN"

    return f"""You are analyzing an API data source and need to provide executive insights.

**Analysis Statistics (Pre-calculated):**
- URL: {phase0.base_url if hasattr(phase0, 'base_url') else phase1.url}
- Source Type: {phase0.detected_type}
- Total Endpoints: {validation_stats['total_endpoints']}
- Accessible (200 OK): {validation_stats['accessible_endpoints']}
- Auth-Protected (401/403): {validation_stats['protected_endpoints']}
- Broken (404/500+): {validation_stats['broken_endpoints']}
- Overall Success Rate: {validation_stats['success_rate']:.1%}
- Confidence Score: {validation_stats['confidence_score']:.2f}

**Authentication:**
- Required: {auth_required}
- Method: {auth_method}
- Auth Prediction Correct: {validation_stats['auth_prediction_correct']}

**Your Task:**
Generate concise, actionable insights for this API analysis. Do NOT recalculate the statistics above.

1. **summary**: Write 2-3 sentences describing this API and what it provides
2. **key_findings**: List 3-5 key findings as bullet points (e.g., "All endpoints require authentication", "API uses RESTful design", "Well-documented with {validation_stats['total_endpoints']} endpoints")
3. **recommendations**: List 3-5 actionable recommendations for the user (e.g., "Obtain API credentials from provider", "Start with simpler endpoints", "Test rate limits")
4. **scraper_challenges**: List 3-5 main challenges for scraper implementation (e.g., "Authentication required", "Parameter validation needed", "Rate limiting unknown")

Keep responses concise and specific to THIS API. Focus on insights that will help someone build a scraper.

Return your analysis as JSON matching the Phase3Insights schema."""
