// BAML Functions for BA Validator Agent
// Validates BA analysis results for completeness and assigns confidence scores

// ============================================================================
// Phase 0 Validation Function
// ============================================================================

function ValidatePhase0(
    phase0_result: Phase0Detection,
    original_url: string
) -> ValidationResult {
    client ClaudeBedrock
    prompt #"
        You are validating a Phase 0 data source detection result from a Business Analyst agent.

        ## Phase 0 Result to Validate

        - **Detected Type:** {{ phase0_result.detected_type }}
        - **Confidence:** {{ phase0_result.confidence }}
        - **Indicators:** {{ phase0_result.indicators }}
        - **Discovered API Calls:** {{ phase0_result.discovered_api_calls }}
        - **URL:** {{ original_url }}

        ## Validation Criteria

        Validate the following aspects:

        1. **URL Validity**: Is {{ original_url }} a valid, well-formed URL with protocol (http/https/ftp/sftp)?
        2. **Type Detection Plausibility**: Is the detected type ({{ phase0_result.detected_type }}) plausible given the URL format ({{ original_url }})?
        3. **Indicator Sufficiency**: Are there enough indicators ({{ phase0_result.indicators | length }}) to support the detection?
        4. **Endpoint Realism**: Are the discovered endpoints realistic and properly formatted?
        5. **Confidence Justification**: Is the confidence score ({{ phase0_result.confidence }}) justified by the evidence?

        ## Your Task

        Analyze the Phase 0 results and identify:
        - Any issues or inconsistencies
        - Gaps in the analysis
        - Areas that need more investigation in Run 2
        - Whether the confidence score is appropriate

        Provide specific, actionable recommendations for improving the analysis in a second run.

        {{ ctx.output_format }}
    "#
}

// ============================================================================
// Phase 1 Validation Function
// ============================================================================

function ValidatePhase1(
    phase1_result: Phase1Documentation,
    phase0_result: Phase0Detection
) -> ValidationResult {
    client ClaudeBedrock
    prompt #"
        You are validating Phase 1 documentation extraction results.

        ## Phase 1 Result to Validate

        - **Source Type:** {{ phase1_result.source_type }}
        - **Documentation Quality:** {{ phase1_result.doc_quality }}
        - **Endpoints Found:** {{ phase1_result.endpoints | length }}
        - **Extraction Quality:** {{ phase1_result.extraction_quality }}
        - **Notes:** {{ phase1_result.notes }}

        ## Phase 0 Context

        - **Detected Type:** {{ phase0_result.detected_type }}
        - **Expected Endpoints:** {{ phase0_result.discovered_api_calls | length }}

        ## Validation Criteria

        1. **Consistency with Phase 0**: Does Phase 1 source_type match Phase 0 detected_type?
        2. **Endpoint Completeness**: Are all endpoints from Phase 0 documented in Phase 1?
        3. **Extraction Quality**: Is extraction_quality acceptable? (COMPREHENSIVE is best, LIMITED/MISSING require improvement)
        4. **Puppeteer Usage**: If extraction_quality is PARTIAL/LIMITED, was Puppeteer used? Should it be used in Run 2?
        5. **Enumeration Completeness**: Are ALL discovered endpoints documented with full specifications?

        Compare endpoint counts:
        - Phase 0 discovered: {{ phase0_result.discovered_api_calls | length }} API calls
        - Phase 1 documented: {{ phase1_result.endpoints | length }} endpoints
        - If Phase 1 < Phase 0: Flag as "incomplete_enumeration" gap with HIGH severity
        - Recommendation: "Second pass must document all {{ phase0_result.discovered_api_calls | length }} discovered endpoints"

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

        {{ ctx.output_format }}
    "#
}

// ============================================================================
// Phase 2 Validation Function
// ============================================================================

function ValidatePhase2(
    phase2_result: Phase2Tests,
    phase1_result: Phase1Documentation
) -> ValidationResult {
    client ClaudeBedrock
    prompt #"
        You are validating Phase 2 live testing results.

        ## Phase 2 Result to Validate

        - **Source Type:** {{ phase2_result.source_type }}
        - **Endpoint Tested:** {{ phase2_result.endpoint_tested }}
        - **Files Saved:** {{ phase2_result.files_saved | length }} files
        - **Conclusion:** {{ phase2_result.conclusion }}

        ## Phase 1 Context

        - **Documentation Claims:** {{ phase1_result.auth_claims }}
        - **Endpoints Documented:** {{ phase1_result.endpoints | length }}

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

        {{ ctx.output_format }}
    "#
}

// ============================================================================
// Complete Specification Validation Function
// ============================================================================

function ValidateCompleteSpec(
    spec: ValidatedSpec
) -> ValidationReport {
    client ClaudeBedrock
    prompt #"
        You are validating a complete data source specification from the BA agent.

        ## Specification to Validate

        **Executive Summary:**
        - Total endpoints discovered: {{ spec.executive_summary.total_endpoints_discovered }}
        - Accessible endpoints: {{ spec.executive_summary.accessible_endpoints }}
        - Success rate: {{ spec.executive_summary.success_rate }}
        - Authentication required: {{ spec.executive_summary.authentication_required }}

        **Validation Summary:**
        - Confidence score: {{ spec.validation_summary.confidence_score }}
        - Confidence level: {{ spec.validation_summary.confidence_level }}
        - Discrepancies found: {{ spec.validation_summary.discrepancies_found }}

        **Endpoints:**
        - Total documented: {{ spec.endpoints | length }}

        ## Validation Tasks

        ### 1. Endpoint Enumeration Completeness

        **CRITICAL**: Verify that ALL discovered endpoints are fully documented.

        Compare:
        - Executive summary claims: {{ spec.executive_summary.total_endpoints_discovered }} endpoints
        - Actually documented: {{ spec.endpoints | length }} endpoints

        **If mismatch detected:**
        - Severity: CRITICAL
        - Gap type: incomplete_enumeration
        - Action: Second pass MUST enumerate ALL endpoints

        ### 2. Confidence Score Validation

        Check if confidence score ({{ spec.validation_summary.confidence_score }}) is justified:
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

        {{ ctx.output_format }}
    "#
}

// ============================================================================
// Validation Result Type (defined in types.baml)
// ============================================================================
