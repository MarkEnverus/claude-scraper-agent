"""Phase 0 prompts for BA Analyst - Initial detection and iterative discovery.

Migrated from agentic_scraper/prompts/ba_analyzer.py (phase0_prompt and phase0_iterative_prompt).
These prompts handle data source type detection and AI-driven iterative page navigation.
"""

from typing import Optional


def phase0_single_page_prompt(
    url: str,
    page_content: str,
    network_calls: list[str],
    navigation_links: list[str],
    primary_api_name: Optional[str] = None
) -> str:
    """Phase 0: Single-page data source type detection prompt.

    This is the original single-pass detection for analyzing a single page.
    Used when iterative discovery is not needed.

    Args:
        url: Target URL being analyzed
        page_content: Full page text content (JavaScript rendered, up to 15k chars)
        network_calls: List of discovered network call URLs
        navigation_links: List of navigation/menu links extracted from page
        primary_api_name: Optional primary API name to focus on (e.g., "pricing-api")

    Returns:
        Formatted prompt string for Claude
    """
    network_calls_text = "\n".join(f"        - {call}" for call in network_calls) if network_calls else "        (none discovered)"
    nav_links_text = "\n".join(f"        - {link}" for link in navigation_links) if navigation_links else "        (none discovered)"

    # Build focus instructions if primary_api_name is set
    focus_section = ""
    if primary_api_name:
        focus_section = f"""
**FOCUS CONTROL:**
This analysis is specifically for the "{primary_api_name}" API.
- ONLY extract endpoints related to "{primary_api_name}"
- IGNORE endpoints from other APIs on the same portal
- Look for mentions of "{primary_api_name}" in the page content and navigation links
"""

    return f"""You are analyzing a data source to discover ALL API endpoints.

**CRITICAL RULES:**
1. NO HALLUCINATION - Only document endpoints you ACTUALLY SEE in the content below
2. NO GUESSING - Do not invent endpoints based on "common patterns"
3. If you can't find endpoints after analyzing all provided data, return empty list
{focus_section}
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
     **Modern API portal signals (hash routing, APIM patterns):**
     - Hash routing: #api=..., #/apis/..., #!/...
     - APIM-style URLs: /developer/apis/, /operations, /products
     - Spec markers: /openapi, /swagger, /api-docs
     - REST markers: /v1/, /v2/, /graphql
   - FTP: Look for ftp:// or sftp:// URLs, FTP/SFTP connection info
   - WEBSITE: Look for download links to data files (.csv, .json, .xml, .xlsx, .zip)
   - EMAIL: Look for subscribe forms, mailing list info, IMAP/SMTP config

   **CRITICAL - Landing Page Detection:**
   - LANDING PAGE indicators: "Browse APIs", "Products", "API Catalog", "Developer Portal"
   - Lists multiple API products or services (e.g., "Pricing API", "Load API", "Market API")
   - Has links TO API documentation but is NOT the documentation itself
   - Action: Extract links to individual API docs, visit them (do not stop at landing page)
   - Type: API with confidence 0.7-0.9 (API management portal landing page)

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


def phase0_iterative_prompt(
    all_pages_data: list[dict],
    visited_urls: list[str],
    primary_api_name: Optional[str] = None
) -> str:
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

    # Format website-specific data (shadow DOM, custom elements, late API calls, download buttons)
    all_shadow_text = []
    all_custom_hints = []
    all_late_calls = []
    all_download_buttons = []

    for page in all_pages_data:
        shadow_text = page.get('shadow_dom_text', '')
        if shadow_text:
            all_shadow_text.append(shadow_text)

        hints = page.get('custom_element_hints', [])
        all_custom_hints.extend(hints)

        late_calls = page.get('late_api_calls', [])
        all_late_calls.extend(late_calls)

        buttons = page.get('download_buttons', [])
        all_download_buttons.extend(buttons)

    # Format for display
    shadow_text_combined = "\n\n".join(all_shadow_text) if all_shadow_text else ""
    custom_hints_text = "\n".join(f"  - <{h['tag']}> {list(h.get('attributes', {}).keys())[:3]}"
                                    for h in all_custom_hints[:10]) if all_custom_hints else "None"
    late_calls_text = "\n".join(f"  - {call}" for call in list(set(all_late_calls))[:10]) if all_late_calls else "None"
    download_buttons_text = f"{len(all_download_buttons)} found" if all_download_buttons else "None"

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

## Website-Specific Data Extracted

**Late API Calls** (captured after page load):
{late_calls_text}

**Custom Web Components** (may indicate interactive portal):
{custom_hints_text}

**Download Buttons Found**: {download_buttons_text}

{f'''**Shadow DOM Content** (first 500 chars):
{shadow_text_combined[:500] if shadow_text_combined else "None"}
''' if shadow_text_combined else ''}

**Analysis Hint**: If you see custom web components, late API calls, or download buttons, this may be an interactive data portal (WEBSITE type) rather than API documentation. Consider this when determining the data source type.

## WEBSITE-TYPE DATA PORTAL INSTRUCTIONS

**If detected_type is WEBSITE** (not API), apply these rules:

**Recognize hierarchical structures** (vision + reasoning):
- Breadcrumbs showing depth (Home > Category > 2026 > January)
- Folder trees with parent/child relationships
- Numeric/date patterns in links (years, months, IDs, versions)
- Repetitive link structures suggesting folder hierarchies
- File icons/extension badges visible in UI
- Shadow DOM listings or custom file browser components

**Identify current level** (use breadcrumbs/URL/layout):
- Portal level: Landing page with category navigation
- Category level: Shows subcategories or folder structures
- Folder level: Contains more folders or file listings
- File level: Shows actual downloadable files (.csv, .json, .xml, .xlsx)

**Goal**: Navigate deeper until you reach FILE LEVEL (links with file extensions)

**Stopping criteria for WEBSITE**:
- ✅ STOP if: discovered_data_links >= 50 (sufficient data)
- ✅ STOP if: At file listing level with 10+ download links
- ✅ STOP if: No file links found after 5+ pages AND no hierarchy visible
- ⏭️ CONTINUE if: discovered_data_links < 10 AND hierarchical navigation still visible
- ⏭️ CONTINUE if: Current page shows navigation but no file listings yet
- ⏭️ CONTINUE if: Breadcrumbs/URL suggest you're not at deepest level

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
   - **NO** if: You have visited pages for ALL operations shown in the content
   - **NO** if: No new links point to additional {primary_api_name if primary_api_name else ''} endpoint documentation

   **CRITICAL - Landing Page Navigation Rule:**
   - **NEVER stop at landing/portal pages** - If current page lists multiple APIs/products, MUST visit their docs
   - **NEVER stop if you see "API Documentation" or "Developer Portal" links** not yet visited
   - **ONLY stop** when you've visited actual endpoint documentation pages (not landing pages)

**4. Which specific URLs should you visit next?**
   - **FIRST PRIORITY**: Pages for {primary_api_name if primary_api_name else 'the primary API'} operations you haven't visited yet
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
