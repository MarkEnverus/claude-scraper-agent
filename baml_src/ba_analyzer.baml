// BAML Functions for BA Analyzer - 4-Phase Data Source Analysis
// Based on ba-enhanced.md specification

// ============================================================================
// Phase 0: Data Source Type Detection
// ============================================================================

function AnalyzePhase0(
    url: string,
    html_content: string,
    network_calls: string[]
) -> Phase0Detection {
    client ClaudeBedrock
    prompt #"
        You are analyzing a data source to detect its type and discover API endpoints.

        URL: {{ url }}

        HTML Content:
        {{ html_content }}

        Network Calls Discovered:
        {% for call in network_calls %}
        - {{ call }}
        {% endfor %}

        Analyze the HTML and network traffic to determine:

        1. Data Source Type:
           - API: Look for REST endpoints, OpenAPI/Swagger docs, API documentation
           - FTP: Look for ftp:// or sftp:// URLs, FTP/SFTP connection info
           - WEBSITE: Look for download links to data files (.csv, .json, .xml, .xlsx, .zip)
           - EMAIL: Look for subscribe forms, mailing list info, IMAP/SMTP config

        2. Confidence Level (0.0 to 1.0):
           - 0.9-1.0: Very clear indicators (multiple strong signals)
           - 0.7-0.9: Clear indicators (at least 2 strong signals)
           - 0.5-0.7: Some indicators (1-2 signals)
           - 0.0-0.5: Unclear or mixed signals

        3. Evidence Indicators:
           List specific evidence found (e.g., "Found 15 .csv download links", "OpenAPI spec visible")

        4. Discovered API Calls:
           List all API endpoints found in network traffic (from network_calls parameter)
           Include any /api/, /v1/, /data/, .json endpoints

        5. Endpoints:
           For each discovered endpoint, extract:
           - path: Full URL path
           - method: HTTP method (GET, POST, etc.)
           - parameters: Empty list for Phase 0 (will be filled in Phase 1)
           - auth_required: false for Phase 0 (will be determined in Phase 2)
           - response_format: Guess based on URL (.json -> JSON, .xml -> XML, etc.)

        IMPORTANT:
        - If uncertain, default to WEBSITE (most flexible)
        - Don't guess - only document what you actually see
        - Network calls are the most reliable indicator for APIs

        {{ ctx.output_format }}
    "#
}

// ============================================================================
// Phase 1: Documentation/Metadata Extraction
// ============================================================================

function AnalyzePhase1(
    url: string,
    documentation_content: string,
    phase0_result: Phase0Detection
) -> Phase1Documentation {
    client ClaudeBedrock
    prompt #"
        You are analyzing documentation/metadata for a data source.

        URL: {{ url }}
        Detected Type: {{ phase0_result.detected_type }}

        Documentation Content:
        {{ documentation_content }}

        {% if phase0_result.detected_type == "API" %}

        For API data sources, extract:

        1. Endpoint Discovery:
           - Total endpoints found (must match actual count in endpoints array)
           - Collapsible sections expanded (if applicable)
           - Extraction method: "puppeteer" or "webfetch"
           - Screenshot taken: true/false
           - Systematic enumeration completed: true ONLY IF ALL of:
             * All collapsible sections were expanded AND
             * All visible endpoints were extracted AND
             * Screenshot was taken showing expanded state
             Otherwise set to false

        2. Authentication Claims:
           - Auth section found: true/false
           - Auth section text: Exact text from docs (first 1000 chars)
           - Signup links: All registration/signup URLs found
           - API key mentioned: true/false
           - Subscription mentioned: true/false
           - Auth header examples: Code snippets showing auth headers
           - Conclusion: Summary of auth requirements from docs

        3. Endpoints (CRITICAL - NO HALLUCINATION):
           For EACH endpoint visible in documentation:
           - endpoint_id: Unique identifier (e.g., "get-users")
           - path: Exact path from docs (e.g., "/v1/users")
           - method: HTTP method (GET, POST, PUT, DELETE, PATCH)
           - description: Description from docs
           - parameters: List of parameters with name, type, required, description, example
           - response_format: JSON, XML, CSV, HTML, BINARY
           - authentication_mentioned: true if docs mention auth for this endpoint

        4. Documentation Quality:
           - EXCELLENT: Complete, clear, examples present
           - HIGH: Clear with most details
           - MEDIUM: Some details missing
           - LOW: Minimal information
           - POOR: Very unclear or contradictory

        CRITICAL ANTI-HALLUCINATION RULES - ABSOLUTE PROHIBITION:
        ❌ ONLY document endpoints you can ACTUALLY SEE in the documentation
        ❌ DO NOT make up endpoints based on "common patterns"
        ❌ DO NOT guess that "/v1/data" exists without seeing it in docs
        ❌ If docs show 5 endpoints, document exactly 5 (not 10, not 3)
        ❌ If uncertain if an endpoint exists, DO NOT include it
        ✅ VERIFICATION: Before saving, ask: "Did I see this EXACT endpoint path in the docs?"

        If you cannot find endpoint documentation, say so explicitly. Better to have 0 endpoints with high confidence than 10 hallucinated endpoints.

        {% elif phase0_result.detected_type == "WEBSITE" %}

        For WEBSITE data sources, extract:

        1. Data Inventory:
           - Total files discovered
           - File formats: List of formats (csv, json, xml, xlsx, pdf, etc.)
           - Categories: Data categories/sections found
           - Download links: Array of links with url, text, fileType, fileSize, lastModified

        2. Access Requirements:
           - Authentication: "none", "login_required", "api_key", or "unknown"
           - Registration: required (true/false), signup_links array
           - Terms of use URL: Link to terms/legal page
           - Subscription required: true/false
           - Rate limits: Description or "not_mentioned"

        3. Update Frequency:
           Look for mentions of "updated daily", "hourly", "weekly", "monthly", "real-time"

        4. Portal Type:
           - STATIC: Traditional static HTML site
           - SPA: Single-page application (JavaScript-rendered)
           - API_DOCS: API documentation portal
           - CUSTOM_FRAMEWORK: Custom framework

        5. Extraction Quality:
           - COMPREHENSIVE: All data sources documented
           - PARTIAL: Some data sources documented
           - LIMITED: Minimal extraction
           - MISSING: Failed to extract meaningful data

        {% else %}

        For FTP/EMAIL data sources:
        - Extract connection details, authentication requirements, data formats
        - Document access instructions
        - Note any scheduling or delivery information

        {% endif %}

        Notes: Any issues, warnings, or observations during extraction

        {{ ctx.output_format }}
    "#
}

// ============================================================================
// Phase 2: Portal Testing
// ============================================================================

function AnalyzePhase2(
    url: string,
    test_results_content: string,
    phase0_result: Phase0Detection,
    phase1_result: Phase1Documentation
) -> Phase2Tests {
    client ClaudeBedrock
    prompt #"
        You are analyzing live test results for a data source.

        URL: {{ url }}
        Source Type: {{ phase0_result.detected_type }}

        Test Results Content:
        {{ test_results_content }}

        {% if phase0_result.detected_type == "API" or phase1_result.endpoints|length > 0 %}

        For API data sources, analyze test results:

        1. Test Results:
           For each test performed (no_auth, with_azure_apim_header, with_api_key_header, with_bearer):
           - http_status: Actual HTTP status code from curl
           - response_snippet: First 500 chars of response
           - auth_keywords_found: Keywords like "sign up", "api key", "authenticate"
           - full_output_file: Path to saved curl output file

        2. Conclusion:
           - auth_required: true/false based on test results
           - evidence: Concrete evidence from testing (e.g., "HTTP 404 + page contains 'sign up to acquire keys'")
           - likely_auth_method: NONE, API_KEY, BEARER_TOKEN, OAUTH, BASIC_AUTH, COOKIE, UNKNOWN
           - likely_header_name: "Ocp-Apim-Subscription-Key", "X-API-Key", "Authorization", or null
           - confidence: HIGH, MEDIUM, or LOW

        TRUST TEST RESULTS OVER DOCUMENTATION:
        - If docs say "no auth" but tests return 401/403/404 with auth mentions -> auth IS required
        - If tests return 200 OK without auth -> no auth required
        - HTTP 404 with auth keywords in response = auth required
        - HTTP 401/403 = auth required

        CRITICAL: FORBIDDEN CLAIMS BY HTTP STATUS
        ✅ HTTP 200/201: Can claim "API returns data", "No auth required"
        ✅ HTTP 401/403: Can claim "Auth required" | ❌ CANNOT claim "No auth needed"
        ✅ HTTP 404: Can claim "Endpoint not found" | ❌ CANNOT claim "API returns data"

        FORBIDDEN PHRASES (indicate hallucination):
        ❌ "Excellent! The API returned..." (without HTTP 200)
        ❌ "Perfect! Let me analyze the response..." (without reading file first)
        ❌ "The data shows..." (without showing actual data)
        ❌ "Testing completed successfully" (when status was 404)

        TRUST THE TEST RESULTS OVER ASSUMPTIONS.

        {% else %}

        For WEBSITE data sources, analyze download tests:

        1. Download Tests:
           - total_links_tested: Number of links tested
           - successful: Count of HTTP 200 responses
           - failed: Count of non-200 responses
           - results: Array of test results with:
             * url: Link tested
             * http_status: Status code
             * content_type: Content-Type header
             * content_length: Content-Length header
             * last_modified: Last-Modified header
             * accessible: true if HTTP 200
             * requires_auth: true if HTTP 401/403
             * redirect_to_login: true if redirected to login page

        2. Authentication Findings:
           - auth_required: true/false/partial
           - evidence: Concrete evidence from tests
           - cookie_required: true if cookie needed
           - redirect_to_login: true if login redirect occurred
           - auth_headers_found: WWW-Authenticate or other auth headers

        3. File Metadata Verification:
           - file_sizes_match_claims: "true", "false", or "not_specified"
           - content_types_match: true/false
           - last_modified_dates_available: true/false

        Portal Conclusion: Summary of portal behavior and data access method

        {% endif %}

        Files Saved: List of all test output files saved during testing

        {{ ctx.output_format }}
    "#
}

// ============================================================================
// Phase 3: Specification Generation & Cross-Check Validation
// ============================================================================

function AnalyzePhase3(
    url: string,
    phase0: Phase0Detection,
    phase1: Phase1Documentation,
    phase2: Phase2Tests
) -> ValidatedSpec {
    client ClaudeBedrock
    prompt #"
        You are generating a validated specification by cross-checking 3 phases of analysis.

        URL: {{ url }}

        Phase 0 Detection:
        - Detected Type: {{ phase0.detected_type }}
        - Confidence: {{ phase0.confidence }}

        Phase 1 Documentation:
        - Endpoints Found: {{ phase1.endpoints|length }}
        - Doc Quality: {{ phase1.doc_quality }}
        {% if phase1.auth_claims %}
        - Auth Claims: {{ phase1.auth_claims.conclusion }}
        {% endif %}

        Phase 2 Testing:
        {% if phase2.conclusion %}
        - Auth Required: {{ phase2.conclusion.auth_required }}
        - Evidence: {{ phase2.conclusion.evidence }}
        {% endif %}

        Generate a validated specification with:

        1. Executive Summary (generate based on ALL phase data):
           - total_endpoints_discovered: REQUIRED (int) - count all discovered endpoints
           - accessible_endpoints: REQUIRED (int) - count endpoints that returned 200/201
           - total_datasets: OPTIONAL - only for WEBSITE sources (int)
           - total_files: OPTIONAL - only for WEBSITE sources (int)
           - protected_endpoints: Count requiring authentication
           - broken_endpoints: Count returning 404/errors
           - success_rate: Percentage (e.g., "85%")
           - primary_formats: List of formats (JSON, CSV, XML, etc.)
           - authentication_required: true/false (TRUST PHASE 2)
           - estimated_scraper_complexity: LOW, MEDIUM, or HIGH

        2. Validation Summary:
           - phases_completed: ["Phase 0: Detection", "Phase 1: Documentation", "Phase 2: Testing", "Phase 3: Validation"]
           - documentation_review: "completed"
           - live_api_testing: "completed" or "not_applicable"
           - discrepancies_found: Count of discrepancies
           - confidence_score: Calculate score (0.0-1.0):
             * Start: 0.5
             * +0.2 if phase1.doc_quality in [EXCELLENT, HIGH]
             * +0.3 if phase2 tests completed successfully
             * +0.2 if phase1 and phase2 agree on auth
             * -0.1 per discrepancy
             * Clamp to [0.0, 1.0]
           - confidence_level: HIGH (>0.7), MEDIUM (0.5-0.7), LOW (<0.5)
           - recommendation: "Spec validated - ready for scraper generation" if confidence >= 0.7

        3. Authentication (TRUST PHASE 2 OVER PHASE 1):
           - required: {{ phase2.conclusion.auth_required if phase2.conclusion else false }}
           - method: {{ phase2.conclusion.likely_auth_method if phase2.conclusion else "NONE" }}
           - header_name: {{ phase2.conclusion.likely_header_name if phase2.conclusion else null }}
           - evidence: Evidence from Phase 2 testing
           - registration_url: From Phase 1 signup links (first one)
           - notes: "Trust live API testing over documentation claims"

        4. Endpoints:
           For EACH endpoint from Phase 1, create EndpointDetails with:
           - endpoint_id: From Phase 1
           - name: Descriptive name
           - type: "rest-api", "file-browser-api", "download", etc.
           - base_url: Base URL
           - path: Endpoint path
           - method: HTTP method
           - parameters: Map of parameters from Phase 1
           - authentication: Map with "required" and "method"
           - response_format: From Phase 1
           - data_structure: Optional structure description
           - sample_files: Optional sample files (for WEBSITE sources)
           - validation_status: Based on Phase 2 tests:
             * TESTED_200_OK: HTTP 200
             * TESTED_401_UNAUTHORIZED: HTTP 401
             * TESTED_403_FORBIDDEN: HTTP 403
             * TESTED_404_NOT_FOUND: HTTP 404
             * NOT_TESTED: Not tested
           - accessible: true if validation_status == TESTED_200_OK
           - last_tested: ISO timestamp
           - file_count: Optional file count
           - update_frequency: From Phase 1
           - notes: Any important notes

        5. Scraper Recommendation:
           - type: WEBSITE_PARSER, HTTP_COLLECTOR, API_CLIENT, or FTP_CLIENT
           - rationale: List of reasons for this recommendation
           - complexity: LOW, MEDIUM, or HIGH
           - estimated_effort: "2-4 hours", "1-2 days", etc.
           - key_challenges: List of challenges

        6. Discrepancies:
           Compare Phase 1 vs Phase 2 and identify mismatches:

           Auth Requirement Mismatch:
           - If Phase 1 says "no auth" but Phase 2 shows auth required
           - Type: "auth_requirement_mismatch"
           - Severity: "high"
           - Resolution: "Trust API testing - authentication IS required"

           Endpoint Validity:
           - If Phase 2 returns 404 with no auth mentions
           - Type: "endpoint_not_found"
           - Severity: "high"
           - Resolution: "Verify endpoint URL is correct"

           Documentation Quality:
           - If Phase 1 unclear but Phase 2 clear
           - Type: "documentation_quality"
           - Severity: "medium"
           - Resolution: "Documentation unclear but testing provides answer"

        7. Artifacts Generated:
           List all files generated during analysis:
           - datasource_analysis/phase0_detection.json
           - datasource_analysis/phase1_documentation.json
           - datasource_analysis/phase2_tests.json
           - datasource_analysis/validated_datasource_spec.json
           - Any test output files

        8. Next Steps:
           - "Feed validated_datasource_spec.json to scraper-generator"
           - "Register for API key at: [URL]" (if auth required)
           - "Test with real credentials to confirm auth method"
           - Any other relevant steps

        IMPORTANT:
        - Always prefer Phase 2 (testing) over Phase 1 (documentation)
        - Document ALL discrepancies explicitly
        - Calculate confidence score based on consistency
        - Be honest about limitations and gaps

        {{ ctx.output_format }}
    "#
}
