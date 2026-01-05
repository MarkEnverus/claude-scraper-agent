"""Prompts for BA Validator agent - Validation of BA analysis results.

Migrated from baml_src/ba_validator.baml to Python.
Each function returns a formatted prompt string for Claude.
"""

from typing import Any


def validate_phase0_prompt(phase0_result: Any, original_url: str) -> str:
    """Phase 0 validation prompt.

    Original: baml_src/ba_validator.baml -> ValidatePhase0()

    Args:
        phase0_result: Phase 0 detection result to validate
        original_url: Original URL analyzed

    Returns:
        Formatted prompt string for Claude
    """
    indicators_count = len(phase0_result.indicators) if hasattr(phase0_result, 'indicators') else 0

    return f"""You are validating a Phase 0 data source detection result from a Business Analyst agent.

## Phase 0 Result to Validate

- **Detected Type:** {phase0_result.detected_type}
- **Confidence:** {phase0_result.confidence}
- **Indicators:** {phase0_result.indicators}
- **Discovered API Calls:** {phase0_result.discovered_api_calls if hasattr(phase0_result, 'discovered_api_calls') else []}
- **URL:** {original_url}

## Validation Criteria

Validate the following aspects:

1. **URL Validity**: Is {original_url} a valid, well-formed URL with protocol (http/https/ftp/sftp)?
2. **Type Detection Plausibility**: Is the detected type ({phase0_result.detected_type}) plausible given the URL format ({original_url})?
3. **Indicator Sufficiency**: Are there enough indicators ({indicators_count}) to support the detection?
4. **Endpoint Realism**: Are the discovered endpoints realistic and properly formatted?
5. **Confidence Justification**: Is the confidence score ({phase0_result.confidence}) justified by the evidence?

## Your Task

Analyze the Phase 0 results and identify:
- Any issues or inconsistencies
- Gaps in the analysis
- Areas that need more investigation in Run 2
- Whether the confidence score is appropriate

Provide specific, actionable recommendations for improving the analysis in a second run.

Return your analysis as JSON matching the ValidationResult schema."""


def validate_phase1_prompt(phase1_result: Any, phase0_result: Any) -> str:
    """Phase 1 validation prompt.

    Original: baml_src/ba_validator.baml -> ValidatePhase1()

    Args:
        phase1_result: Phase 1 documentation result to validate
        phase0_result: Phase 0 detection result for context

    Returns:
        Formatted prompt string for Claude
    """
    endpoints_count = len(phase1_result.endpoints) if hasattr(phase1_result, 'endpoints') else 0
    phase0_calls_count = len(phase0_result.discovered_api_calls) if hasattr(phase0_result, 'discovered_api_calls') else 0

    return f"""You are validating Phase 1 documentation extraction results.

## Phase 1 Result to Validate

- **Source Type:** {phase1_result.source_type if hasattr(phase1_result, 'source_type') else 'N/A'}
- **Documentation Quality:** {phase1_result.doc_quality}
- **Endpoints Found:** {endpoints_count}
- **Extraction Quality:** {phase1_result.extraction_quality if hasattr(phase1_result, 'extraction_quality') else 'N/A'}
- **Notes:** {phase1_result.notes}

## Phase 0 Context

- **Detected Type:** {phase0_result.detected_type}
- **Expected Endpoints:** {phase0_calls_count}

## Validation Criteria

1. **Consistency with Phase 0**: Does Phase 1 source_type match Phase 0 detected_type?
2. **Endpoint Completeness**: Are all endpoints from Phase 0 documented in Phase 1?
3. **Extraction Quality**: Is extraction_quality acceptable? (COMPREHENSIVE is best, LIMITED/MISSING require improvement)
4. **Puppeteer Usage**: If extraction_quality is PARTIAL/LIMITED, was Puppeteer used? Should it be used in Run 2?
5. **Enumeration Completeness**: Are ALL discovered endpoints documented with full specifications?

Compare endpoint counts:
- Phase 0 discovered: {phase0_calls_count} API calls
- Phase 1 documented: {endpoints_count} endpoints
- If Phase 1 < Phase 0: Flag as "incomplete_enumeration" gap with HIGH severity
- Recommendation: "Second pass must document all {phase0_calls_count} discovered endpoints"

## Critical Checks

**For APIs:**
- Check if auth_claims exist and are complete
- Verify all endpoints have: path, method, parameters, response_format

**For Website Portals:**
- Check if data_inventory exists and has file counts
- Verify access_requirements are documented

## Red Flags

- Only 2-3 endpoints documented when Phase 0 found 10+
- extraction_quality is PARTIAL/LIMITED without explanation
- No mention of Puppeteer usage for JavaScript-rendered sites
- Missing auth claims for APIs
- Incomplete endpoint specifications

Return your analysis as JSON matching the ValidationResult schema."""


def validate_phase2_prompt(phase2_result: Any, phase1_result: Any) -> str:
    """Phase 2 validation prompt.

    Original: baml_src/ba_validator.baml -> ValidatePhase2()

    Args:
        phase2_result: Phase 2 testing result to validate
        phase1_result: Phase 1 documentation result for context

    Returns:
        Formatted prompt string for Claude
    """
    files_saved_count = len(phase2_result.files_saved) if hasattr(phase2_result, 'files_saved') else 0
    endpoints_count = len(phase1_result.endpoints) if hasattr(phase1_result, 'endpoints') else 0

    return f"""You are validating Phase 2 live testing results.

## Phase 2 Result to Validate

- **Source Type:** {phase2_result.source_type if hasattr(phase2_result, 'source_type') else 'N/A'}
- **Endpoint Tested:** {phase2_result.endpoint_tested if hasattr(phase2_result, 'endpoint_tested') else 'N/A'}
- **Files Saved:** {files_saved_count} files
- **Conclusion:** {phase2_result.conclusion if hasattr(phase2_result, 'conclusion') else 'N/A'}

## Phase 1 Context

- **Authentication Claims:** {phase1_result.auth_claims if hasattr(phase1_result, 'auth_claims') else 'N/A'}
- **Endpoints Documented:** {endpoints_count}

## Validation Criteria

1. **Evidence-Based Testing**: Are test results based on actual HTTP requests with saved outputs?
2. **Authentication Validation**: Do test results confirm or contradict Phase 1 auth claims?
3. **File Artifacts**: Are all test outputs saved to disk for verification?
4. **Completeness**: Were enough endpoints tested to validate the analysis?

## Critical Checks

**For APIs:**
- Check if test_results contain actual HTTP status codes (200, 401, 403, 404)
- Verify auth_keywords_found is populated with real evidence
- Ensure full_output_file paths exist for each test

**For Website Portals:**
- Check if download_tests cover representative samples
- Verify accessibility status for each tested link
- Ensure authentication findings are evidence-based

## Red Flags

- No files_saved (indicates tests may not have actually run)
- HTTP 404 but conclusion says "no auth required"
- High confidence but no test artifacts
- Contradictions between Phase 1 and Phase 2 not explained

Return your analysis as JSON matching the ValidationResult schema."""


def validate_complete_spec_prompt(spec: Any) -> str:
    """Complete specification validation prompt.

    Original: baml_src/ba_validator.baml -> ValidateCompleteSpec()

    Args:
        spec: Complete validated specification to validate

    Returns:
        Formatted prompt string for Claude
    """
    total_endpoints = spec.executive_summary.total_endpoints_discovered
    accessible_endpoints = spec.executive_summary.accessible_endpoints
    success_rate = spec.executive_summary.success_rate
    auth_required = spec.executive_summary.authentication_required

    confidence_score = spec.validation_summary.confidence_score
    confidence_level = spec.validation_summary.confidence_level
    discrepancies_found = spec.validation_summary.discrepancies_found

    documented_endpoints = len(spec.endpoints) if hasattr(spec, 'endpoints') else 0

    return f"""You are validating a complete data source specification from the BA agent.

## Specification to Validate

**Executive Summary:**
- Total endpoints discovered: {total_endpoints}
- Accessible endpoints: {accessible_endpoints}
- Success rate: {success_rate}
- Authentication required: {auth_required}

**Validation Summary:**
- Confidence score: {confidence_score}
- Confidence level: {confidence_level}
- Discrepancies found: {discrepancies_found}

**Endpoints:**
- Total documented: {documented_endpoints}

## Validation Tasks

### 1. Endpoint Enumeration Completeness

**CRITICAL**: Verify that ALL discovered endpoints are fully documented.

Compare:
- Executive summary claims: {total_endpoints} endpoints
- Actually documented: {documented_endpoints} endpoints

**If mismatch detected:**
- Severity: CRITICAL
- Gap type: incomplete_enumeration
- Action: Second pass MUST enumerate ALL endpoints

### 2. Confidence Score Validation

Check if confidence score ({confidence_score}) is justified:
- High confidence (>0.8) but many endpoints missing → INCONSISTENT
- High confidence but extraction_quality is PARTIAL → INCONSISTENT
- Low confidence but comprehensive analysis → May be overly conservative

### 3. Puppeteer Usage Check

NOTE: This check is performed in ValidatePhase1 function, NOT here in ValidateCompleteSpec.
The complete spec doesn't include phase1_result, so Puppeteer validation happens earlier.

For website portals or JavaScript-rendered sites (checked in Phase 1 validation):
- Check artifacts_generated for evidence of Puppeteer usage
- If extraction_quality is PARTIAL/LIMITED → Puppeteer should have been used
- If not used → Recommend for Run 2

### 4. Cross-Phase Consistency

Verify consistency across phases:
- Do authentication findings match across Phase 1 and Phase 2?
- Are discrepancies properly documented and resolved?
- Is the confidence score consistent with the quality of evidence?

### 5. Scraper Recommendation Validity

Check if scraper_recommendation is appropriate:
- Type matches source_type?
- Complexity assessment is reasonable?
- Key challenges are specific and actionable?

## Output Requirements

Generate a comprehensive validation report with:

1. **Overall Status**: PASS, NEEDS_IMPROVEMENT, or FAIL
2. **Overall Confidence**: Your assessment of spec quality (0.0-1.0)
3. **Phase Validations**: Status and issues for each phase
4. **Critical Gaps**: List of critical issues that MUST be addressed
5. **Recommendations**: Specific actions for Run 2 (if needed)

## Confidence Threshold

- If overall_confidence < 0.8 → Recommend Run 2
- If overall_confidence >= 0.8 → Spec is acceptable, Run 2 optional

Return your analysis as JSON matching the ValidationReport schema."""
