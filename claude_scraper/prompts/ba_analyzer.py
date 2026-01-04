"""Prompts for BA Analyzer agent - 4-Phase Data Source Analysis.

Migrated from baml_src/ba_analyzer.baml to Python.
Each function returns a formatted prompt string for Claude.
"""

from typing import Any


def phase0_prompt(url: str, page_content: str, network_calls: list[str], navigation_links: list[str]) -> str:
    """Phase 0: Data source type detection prompt.

    Original: baml_src/ba_analyzer.baml -> AnalyzePhase0()

    Args:
        url: Target URL being analyzed
        page_content: Full page text content (JavaScript rendered, up to 15k chars)
        network_calls: List of discovered network call URLs
        navigation_links: List of navigation/menu links extracted from page

    Returns:
        Formatted prompt string for Claude
    """
    network_calls_text = "\n".join(f"        - {call}" for call in network_calls) if network_calls else "        (none discovered)"
    nav_links_text = "\n".join(f"        - {link}" for link in navigation_links) if navigation_links else "        (none discovered)"

    return f"""You are analyzing a data source to discover ALL API endpoints.

**CRITICAL RULES:**
1. NO HALLUCINATION - Only document endpoints you ACTUALLY SEE in the content below
2. NO GUESSING - Do not invent endpoints based on "common patterns"
3. If you can't find endpoints after analyzing all provided data, return empty list

URL: {url}

=== PAGE TEXT CONTENT ===
{page_content}

NOTE: This is NOT raw HTML! It's:
- Text extracted from document.body.textContent (JavaScript rendered)
- Truncated to 15,000 chars max (~3,750 tokens)
- Clean text only, no HTML tags

=== NAVIGATION/MENU LINKS ===
{nav_links_text}

=== NETWORK CALLS DISCOVERED ===
{network_calls_text}

**YOUR TASK: Discover ALL API Endpoints**

Follow this systematic approach:

1. **Data Source Type Detection:**
   - API: Look for REST endpoints, OpenAPI/Swagger docs, API documentation
   - FTP: Look for ftp:// or sftp:// URLs, FTP/SFTP connection info
   - WEBSITE: Look for download links to data files (.csv, .json, .xml, .xlsx, .zip)
   - EMAIL: Look for subscribe forms, mailing list info, IMAP/SMTP config

   **CRITICAL - Landing Page Detection (FIX #6):**
   - LANDING PAGE indicators: "Browse APIs", "Products", "API Catalog", "Developer Portal"
   - Lists multiple API products or services (e.g., "Pricing API", "Load API", "Market API")
   - Has links TO API documentation but is NOT the documentation itself
   - Action: Extract links to individual API docs, visit them (do not stop at landing page)
   - Type: WEBSITE with confidence 0.6-0.8 (transitional state until you reach actual docs)

2. **Endpoint Discovery Strategy (CRITICAL):**

   **Step 1 - Check Navigation Links FIRST:**
   - Navigation links often contain endpoint names (e.g., "Resource A", "Get Current Data")
   - These link texts reveal what endpoints exist
   - Look for patterns like operation names, resource names, data types
   - Extract the endpoint URLs from link hrefs if they point to API endpoints

   **Step 2 - Analyze Network Calls:**
   - Look for actual API calls made by the page
   - Filter for endpoints (URLs with /api/, /v1/, /data/, .json, etc.)
   - These are CONFIRMED working endpoints

   **Step 3 - Read Page Content:**
   - Look for endpoint documentation in the page text
   - Find URL patterns, path templates, example URLs
   - Extract base URL + path combinations

3. **Discovered Endpoint URLs:**
   - List ONLY the URLs you discovered (e.g., "https://api.example.com/data/v1/resource-a")
   - DO NOT include parameters, methods, or descriptions - JUST URLs
   - Maximum 50 URLs (increased from 20 to capture all endpoints)
   - If more than 50 found, prioritize by importance

4. **Confidence Level (0.0 to 1.0):**
   - 0.9-1.0: Very clear indicators (navigation + network + page content all agree)
   - 0.7-0.9: Clear indicators (at least 2 sources confirm)
   - 0.5-0.7: Some indicators (only 1 source)
   - 0.0-0.5: Unclear or mixed signals

5. **Evidence Indicators:**
   List specific evidence for EACH discovery source:
   - "Found X navigation links with endpoint names"
   - "Found Y network calls to API endpoints"
   - "Page content mentions Z endpoints"

6. **Authentication Method:**
   - Detect: "NONE", "API_KEY", "BEARER_TOKEN", "OAUTH", "BASIC_AUTH", "COOKIE", or "UNKNOWN"
   - Based on auth indicators in page content and network calls

7. **Base URL:**
   - Extract the base URL (e.g., "https://api.example.com")
   - This is the root domain/host without path

**ANTI-HALLUCINATION RULES:**
✅ ONLY document endpoints you ACTUALLY SEE in the provided data
✅ If navigation link says "Resource A", look for the corresponding endpoint URL
✅ Cross-reference: Does the navigation link match a network call or page content?
❌ DO NOT invent endpoints based on "common API patterns"
❌ DO NOT guess endpoint names or URLs
❌ If you can't find any endpoints, return empty list (don't make them up!)

**OUTPUT FORMAT:**
Return JSON with:
- detected_type: "API" | "FTP" | "WEBSITE" | "EMAIL"
- confidence: 0.0 to 1.0
- indicators: List of evidence strings
- discovered_endpoint_urls: List of endpoint URLs (max 50)
- discovered_api_calls: List of network call URLs
- auth_method: Authentication method enum
- base_url: Base URL string

Return your analysis as JSON matching the Phase0Detection schema."""


def phase0_iterative_prompt(all_pages_data: list[dict], visited_urls: list[str], primary_api_name: str | None = None) -> str:
    """Phase 0: Iterative discovery prompt for AI-driven page navigation.

    This prompt enables AI to analyze multiple pages and decide whether
    to visit more pages for complete endpoint discovery.

    Args:
        all_pages_data: List of page data dictionaries with url, markdown, screenshot, etc.
        visited_urls: List of URLs already visited (for reference)
        primary_api_name: Name of the primary API to focus on (e.g., "pricing-api")

    Returns:
        Formatted prompt string for Claude with vision + structured output
    """
    # Format pages data for AI analysis
    pages_summary = []
    for i, page in enumerate(all_pages_data, 1):
        url = page.get('url', 'unknown')
        markdown_len = len(page.get('markdown', ''))
        nav_links_count = len(page.get('navigation_links', []))
        network_calls_count = len(page.get('network_calls', []))

        pages_summary.append(f"""
**Page {i}: {url}**
- Markdown content: {markdown_len} characters
- Navigation links: {nav_links_count}
- Network calls: {network_calls_count}
""")

    pages_summary_text = "\n".join(pages_summary)

    # Format navigation links from all pages
    all_nav_links = []
    for page in all_pages_data:
        for link in page.get('navigation_links', []):
            link_text = f"{link.get('text', '')}: {link.get('href', '')}"
            if link_text not in all_nav_links:
                all_nav_links.append(link_text)

    nav_links_text = "\n".join(f"  - {link}" for link in all_nav_links[:50])  # Limit to 50

    # Format discovered endpoints so far
    all_endpoints = set()
    for page in all_pages_data:
        for call in page.get('network_calls', []):
            if '/api/' in call or call.endswith('.json'):
                all_endpoints.add(call)

    endpoints_text = "\n".join(f"  - {ep}" for ep in list(all_endpoints)[:20])  # Limit to 20

    # Add primary API focus instructions if specified
    focus_instruction = ""
    if primary_api_name:
        focus_instruction = f"""
**PRIMARY API FOCUS**: You were asked to analyze the "{primary_api_name}" API.

**CRITICAL RULE - FINISH CURRENT API FIRST**:
1. **Prioritize {primary_api_name}**: Extract ALL endpoints from this API before exploring others
2. **Stay on topic**: Only visit pages that contain documentation for {primary_api_name}
3. **Navigation links to other APIs**: IGNORE links to different API products until {primary_api_name} is complete
4. **Complete extraction**: Make sure you've found all endpoint operation pages for {primary_api_name}

If you see navigation links showing "{primary_api_name}" has 10 operations but you've only extracted 4 endpoints,
YOU MUST continue visiting pages until all {primary_api_name} operations are discovered.

Only after {primary_api_name} is fully documented should you explore other APIs (if relevant).
"""

    return f"""You are analyzing data sources like a human analyst navigating documentation.

**MISSION**: Discover ALL API endpoints/data sources by intelligently navigating pages.
{focus_instruction}

**VISION ANALYSIS INSTRUCTIONS**:
You are provided with SCREENSHOTS of the pages alongside text data. Use vision to see what a human analyst would see:

1. **Visual Operation Discovery**:
   - Look at the screenshots to identify ALL visible operations, endpoints, or data access methods
   - Navigation menus, sidebars, and operation lists are easier to see visually than in text
   - Count exactly how many operation items you can SEE in the visual structure
   - Example: If you visually see a list with 10 operation names, that means 10 endpoints exist

2. **Visual Structure Understanding**:
   - Identify clickable elements: buttons, divs, links, tabs, sections
   - Notice visual groupings: which operations belong to the same API/service?
   - Spot patterns: color coding, icons, numbering that indicate completeness

3. **Cross-Reference Vision + Text**:
   - Use screenshots to COUNT operations (e.g., "I see 10 operation divs")
   - Use markdown/text to extract names and details
   - Use navigation links to construct or identify URLs
   - If vision shows 10 operations but text only mentions 6, you need to find the other 4

**CRITICAL**: Vision helps you see the page structure like a human does. The AI analysis should discover what a human analyst would find by looking at the screenshots.

You have visited {len(visited_urls)} page(s) so far:
{chr(10).join(f'  {i+1}. {url}' for i, url in enumerate(visited_urls))}

## Pages Analyzed

{pages_summary_text}

## All Navigation Links Discovered

{nav_links_text if nav_links_text else "  (none found)"}

## **CRITICAL: Using Navigation Link URLs**

Navigation links include BOTH text labels AND actual href URLs. When populating discovered_endpoint_urls:

**DO**:
- Extract URLs directly from the href attributes in navigation_links
- Filter for data-related patterns: /api/, /data/, /reports/, /download/, file extensions (.csv, .json, .xml)
- Example: If navigation link shows "Real Time Data: https://api.example.com/v1/realtime", use the FULL URL

**DON'T**:
- Construct placeholder URLs based on link text
- Create generic paths like "/endpoint1", "/endpoint2"
- Invent URLs that aren't in the navigation_links href values

**Example - CORRECT**:
```
Navigation link: {{"text": "Day-Ahead LMP", "href": "https://data-exchange.misoenergy.org/api/v1/day-ahead/lmp"}}
discovered_endpoint_urls: ["https://data-exchange.misoenergy.org/api/v1/day-ahead/lmp"]  ✅
```

**Example - INCORRECT**:
```
Navigation link: {{"text": "Day-Ahead LMP", "href": "https://data-exchange.misoenergy.org/api/v1/day-ahead/lmp"}}
discovered_endpoint_urls: ["https://data-exchange.misoenergy.org/day-ahead-lmp"]  ❌ (constructed placeholder)
```

## Network API Calls Discovered

{endpoints_text if endpoints_text else "  (none found)"}

## **CRITICAL: EXPLICIT COUNTING PROCESS**

Before deciding if you need more pages, follow this exact process:

**Step 1 - List Operations Visually:**
Look at the FIRST screenshot (the main API overview page).
Visually scan the sidebar/menu and list out EACH operation you see:
- Operation 1: [name]
- Operation 2: [name]
- Operation 3: [name]
- ... continue for ALL visible operations

**Step 2 - Count Your List:**
Count how many operations you listed above.
**Total operations visible in screenshot**: [X]

**Step 3 - Count Discovered Endpoints:**
Count how many endpoint URLs you have discovered so far.
**Total discovered**: [Y]

**Step 4 - Compare:**
- If X > Y: needs_more_pages = **True** (keep discovering!)
- If X == Y: needs_more_pages = **False** (you're done!)

**Step 5 - Verification:**
If you counted an odd number, **recount to verify**.
Many APIs have pairs of operations (current/historical, real-time/forecasted, etc.)
Check the BOTTOM of the sidebar - is there one more operation you missed?

**Example for reference:**
```
Visually listing operations from screenshot:
1. Get Current Data
2. Get Historical Data
3. Get Forecast
4. Get Metrics A
5. Get Metrics B
6. Get Resources
7. Get Status
8. Get Summary
9. Get Alerts
10. (CHECK: Is there a 10th at the bottom?)

Total visible: 10
Total discovered: 9
Result: 9 < 10 → needs_more_pages = True
```

## Your Task

Analyze the data from all pages and make a decision:

**1. Count ALL operations/endpoints shown in the page content**
   - Look at the markdown content - how many distinct operations/endpoints are listed?
   - Example: If you see "Get Resource A", "Get Current Data", "Get Historical Data", etc., COUNT each one
   - Count operations in lists, menus, navigation sidebars, and page sections
   - **CRITICAL**: Compare the TOTAL COUNT of operations shown vs. the NUMBER you have discovered

**2. Have you discovered ALL endpoints/data sources?**
   - Look at navigation links - do they suggest more endpoint documentation pages?
   - Look at page content - are there "See also" or "Related endpoints" references?
   - Look at breadcrumbs - are you in a section with multiple subsections?
   - **If the page shows 10 operations but you've only visited 4, YOU ARE NOT DONE**

**3. Do you need to visit more pages?**
   - **YES** if: Total operations shown in content > number of endpoints you've discovered
   - **YES** if: You see documentation links for {primary_api_name if primary_api_name else 'endpoints'} you haven't analyzed yet
   - **YES** if: Navigation suggests multiple endpoint pages exist for the primary API (e.g., "Endpoint 1 of 10")
   - **YES** if: You've found 4 endpoints but navigation shows 10 operations - keep going!
   - **NO** if: You have visited pages for ALL operations shown in the content
   - **NO** if: No new links point to additional {primary_api_name if primary_api_name else ''} endpoint documentation

   **CRITICAL - Landing Page Navigation Rule (FIX #7):**
   - **NEVER stop at landing/portal pages** - If current page lists multiple APIs/products, MUST visit their docs
   - **NEVER stop if you see "API Documentation" or "Developer Portal" links** not yet visited
   - **ONLY stop** when you've visited actual endpoint documentation pages (not landing pages)
   - Landing page confidence: 0.6-0.8. Actual API docs: 0.9-1.0. Keep going until confidence is high.

**4. Which specific URLs should you visit next?**
   - **FIRST PRIORITY**: Pages for {primary_api_name if primary_api_name else 'the primary API'} operations you haven't visited yet
   - **CRITICAL**: If you see operations in the content that you haven't visited, ADD THEM to your list
   - **SECOND PRIORITY**: Related operation/endpoint documentation pages
   - **IGNORE**: Links to different API products or unrelated services
   - Avoid duplicate or already-visited URLs
   - Limit to 5 most important URLs (we can iterate)

## Decision Rules

- **Be thorough**: If navigation shows {primary_api_name if primary_api_name else 'the API'} has 10 operations, visit pages until you find all 10
- **Stay focused**: Don't wander to other API products until {primary_api_name if primary_api_name else 'primary API'} is complete
- **Be efficient**: Don't request pages that won't have {primary_api_name if primary_api_name else 'endpoint'} info (e.g., "About Us", "Contact", other APIs)
- **Be conservative**: Max 20 total pages per analysis (you've visited {len(visited_urls)})
- **Be specific**: Return exact URLs to visit, not patterns or descriptions

## Anti-Hallucination Rules

✅ ONLY document endpoints you ACTUALLY SEE in the provided data
✅ If navigation link says "Get Data Endpoint", look for its documentation page
✅ Cross-reference: Do multiple sources confirm this endpoint exists?
❌ DO NOT invent endpoints based on "common API patterns"
❌ DO NOT guess URLs - only return URLs you see in navigation/links
❌ If you can't find clear endpoint documentation, return empty list

## Response Format

Return JSON with:
- **needs_more_pages**: true/false
- **urls_to_visit**: List of specific URLs (5 max, can be empty if needs_more_pages=false)
- **discovered_endpoint_urls**: ALL endpoint URLs found so far
- **reasoning**: Your thinking (2-3 sentences explaining your decision)
- **detected_type**: "API", "FTP", "WEBSITE", or "EMAIL"
- **confidence**: 0.0 to 1.0
- **indicators**: List of evidence strings
- **auth_method**: "NONE", "API_KEY", "BEARER_TOKEN", "OAUTH", "BASIC_AUTH", "COOKIE", or "UNKNOWN"
- **base_url**: Base URL (e.g., "https://api.example.com")
- **discovered_api_calls**: Network API calls

Think step by step and make intelligent decisions like a human analyst would."""


def analyze_endpoint_prompt(
    endpoint_url: str,
    page_context: str,
    auth_method: str,
    base_url: str
) -> str:
    """Individual endpoint analysis prompt (for Phase 1).

    Original: baml_src/ba_analyzer.baml -> AnalyzeEndpoint()

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


def phase1_prompt(url: str, page_content: str, phase0_result: Any) -> str:
    """Phase 1: Documentation/metadata extraction prompt.

    Original: baml_src/ba_analyzer.baml -> AnalyzePhase1()

    Args:
        url: Target URL being analyzed
        page_content: Structured/preprocessed HTML content
        phase0_result: Results from Phase 0 detection

    Returns:
        Formatted prompt string for Claude
    """
    detected_type = phase0_result.detected_type
    confidence = phase0_result.confidence
    base_url = phase0_result.base_url

    return f"""You are analyzing API documentation to extract detailed endpoint specifications.

URL: {url}
Detected Source Type: {detected_type}
Detection Confidence: {confidence}
Base URL: {base_url}

Documentation Content:
{page_content}

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
   - path: URL path (e.g., "/v1/data")
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


def phase2_prompt(
    url: str,
    test_results_content: str,
    phase0_result: Any,
    phase1_result: Any
) -> str:
    """Phase 2: Live endpoint testing analysis prompt.

    Original: baml_src/ba_analyzer.baml -> AnalyzePhase2()

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


def phase3_prompt(
    url: str,
    phase0: Any,
    phase1: Any,
    phase2: Any
) -> str:
    """Phase 3: Validated specification generation prompt.

    Original: baml_src/ba_analyzer.baml -> AnalyzePhase3()

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


def phase0_qa_validation_prompt(primary_api_name: str, discovered_count: int) -> str:
    """Phase 0 QA validation prompt.

    Used by Phase0QAValidator to independently count operations visible
    in the main API screenshot and compare against discovered count.

    Args:
        primary_api_name: Name of the primary API being validated
        discovered_count: Number of endpoint URLs discovered in Phase 0

    Returns:
        Formatted prompt string for Claude with vision
    """
    return f"""You are a meticulous QA validator reviewing Phase 0 discovery results.

**Your Task: Count ALL Operations Visible in This Screenshot**

You are looking at a screenshot of the main API documentation page for: {primary_api_name}

**Step 1 - Visual Enumeration:**
Look at the screenshot carefully and list out EVERY operation you see in the sidebar/menu:
- Operation 1: [name]
- Operation 2: [name]
- Operation 3: [name]
- ... continue for ALL visible operations

**Step 2 - Count:**
Count how many operations you listed above.
This is your `operations_visible_in_screenshot` count.

**Step 3 - Compare:**
Phase 0 discovered {discovered_count} endpoint URLs.
Compare this against your count from the screenshot.

**Step 4 - Identify Missing Operations:**
If your count is higher than {discovered_count}, list the names of operations
that are visible in the screenshot but were NOT discovered.

**Step 5 - Assessment:**
- `is_complete`: True if counts match, False if there's a discrepancy
- `confidence`: How confident are you in your count? (0.0-1.0)
  - 1.0 = Very clear, easy to count
  - 0.8-0.9 = Mostly clear, slight ambiguity
  - 0.5-0.7 = Some difficulty counting
- `validation_notes`: Explain your findings in 1-2 sentences

**CRITICAL RULES:**
✅ Count EVERY operation visible in the screenshot
✅ Check the BOTTOM of the sidebar - operations are often hidden below the fold
✅ If you count an odd number, recount to verify
✅ Be explicit about which operations are missing (if any)
❌ Don't guess - only count what you can SEE

Return your validation report as JSON matching the Phase0ValidationReport schema."""
