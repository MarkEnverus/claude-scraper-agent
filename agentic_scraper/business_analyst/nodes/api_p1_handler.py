"""API P1 Handler - Discovery phase for API sources.

This node handles Phase 1 discovery for API-type sources (e.g., MISO data exchange)
where endpoint metadata is available in OpenAPI/Swagger specification files or APIM operations.

Key responsibilities:
- Detect APIM portal patterns and fetch operations JSON
- Find OpenAPI/Swagger spec URLs from links, network calls, page text
- Fetch and parse spec files (JSON/YAML)
- Extract endpoint definitions (paths, methods, parameters, schemas)
- Extract authentication requirements
- Build structured endpoint list
- Fallback to HTML documentation parsing if no spec found

Example flow for MISO portal (APIM):
1. API docs page: https://data-exchange.misoenergy.org/api-details#api=pricing-api
2. Extract API name from URL: "pricing-api"
3. Detect APIM portal pattern
4. Fetch operations: /developer/apis/pricing-api/operations
5. Parse APIM JSON → 12+ operations with parameters
6. Build endpoint list: [{path, method, parameters, auth}, ...]
"""

import logging
import re
import httpx
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from agentic_scraper.business_analyst.state import BAAnalystState, EndpointFinding, PageArtifact
from agentic_scraper.business_analyst.utils.openapi_parser import (
    find_openapi_spec_urls,
    fetch_and_parse_spec,
    parse_openapi_spec,
    construct_full_endpoint_urls
)
from agentic_scraper.business_analyst.utils.api_call_extractor import is_openapi_spec_url

logger = logging.getLogger(__name__)


# ============================================================================
# APIM Operations Discovery (NEW for MISO operations discovery)
# ============================================================================

def extract_api_name_from_url(url: str) -> Optional[str]:
    """Extract API name from URL fragment or path.

    Examples:
        https://.../api-details#api=pricing-api → "pricing-api"
        https://.../developer/apis/pricing-api → "pricing-api"

    Args:
        url: Full URL possibly containing API name

    Returns:
        API name if found, None otherwise
    """
    if not url:
        return None

    # Check URL fragment (#api=...)
    if '#api=' in url:
        fragment = url.split('#api=')[1]
        api_name = fragment.split('&')[0]
        logger.info(f"Extracted API name from URL fragment: {api_name}")
        return api_name

    # Check URL path (/developer/apis/pricing-api or /apis/pricing-api)
    match = re.search(r'/apis/([a-z0-9_-]+)', url, re.IGNORECASE)
    if match:
        api_name = match.group(1)
        logger.info(f"Extracted API name from URL path: {api_name}")
        return api_name

    return None


def is_apim_portal(artifact: PageArtifact) -> bool:
    """Detect if page is Azure APIM (API Management) portal.

    Indicators:
    - URL contains /developer/apis/ or /api-details
    - Network calls to /operations, /schemas, /hostnames endpoints
    - Page text mentions "API Management" or "Developer Portal"

    Args:
        artifact: Page artifact to analyze

    Returns:
        True if APIM portal detected, False otherwise
    """
    url_lower = artifact.url.lower()

    # Check URL patterns
    if '/developer/apis/' in url_lower or '/api-details' in url_lower:
        logger.info(f"APIM portal detected via URL pattern: {artifact.url}")
        return True

    # Check network calls for APIM operation patterns
    for call in artifact.network_calls:
        call_lower = call.lower()
        if any(pattern in call_lower for pattern in ['/operations', '/schemas', '/hostnames', '/api-definitions']):
            logger.info(f"APIM portal detected via network call: {call}")
            return True

    # Check page text for APIM indicators
    text = (artifact.markdown_excerpt or artifact.html_excerpt or "").lower()
    if 'api management' in text or 'developer portal' in text:
        logger.info("APIM portal detected via page text")
        return True

    return False


def discover_apim_operations_for_api(
    domain: str,
    api_name: str,
    timeout: int = 10
) -> List[Dict[str, Any]]:
    """Fetch and parse APIM operations JSON for a specific API.

    Args:
        domain: Domain (e.g., "data-exchange.misoenergy.org")
        api_name: API name (e.g., "pricing-api")
        timeout: Request timeout in seconds

    Returns:
        List of operation dictionaries with structure:
        {
            "id": "da-lmp",
            "name": "Day-ahead LMP",
            "method": "GET",
            "urlTemplate": "/pricing-api/da-lmp",
            "parameters": [...],
            "description": "...",
            "request": {...},
            "responses": {...}
        }
    """
    operations_url = f"https://{domain}/developer/apis/{api_name}/operations"

    logger.info(f"Fetching APIM operations from: {operations_url}")

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(operations_url)
            response.raise_for_status()

            operations_data = response.json()

            # APIM returns different formats - handle both
            if isinstance(operations_data, dict) and 'value' in operations_data:
                # Format 1: {"value": [...operations...]}
                operations = operations_data['value']
            elif isinstance(operations_data, list):
                # Format 2: [...operations...]
                operations = operations_data
            else:
                logger.warning(f"Unexpected APIM operations format: {type(operations_data)}")
                return []

            logger.info(f"✅ Found {len(operations)} operations for {api_name}")
            return operations

    except httpx.HTTPStatusError as e:
        logger.warning(f"Failed to fetch APIM operations (HTTP {e.response.status_code}): {operations_url}")
        return []
    except Exception as e:
        logger.error(f"Error fetching APIM operations from {operations_url}: {e}")
        return []


def extract_api_names_from_catalog(artifact: PageArtifact) -> List[str]:
    """Extract API names from APIM catalog page.

    Looks for API names in:
    - Links with /api-details#api=...
    - Links with /developer/apis/...
    - Page text with API name patterns

    Args:
        artifact: Page artifact to extract from

    Returns:
        List of API names found
    """
    api_names = set()

    # Check links
    for link in artifact.links:
        api_name = extract_api_name_from_url(link.url)
        if api_name:
            api_names.add(api_name)

    # Check network calls
    for call in artifact.network_calls:
        api_name = extract_api_name_from_url(call)
        if api_name:
            api_names.add(api_name)

    logger.info(f"Extracted {len(api_names)} API names from catalog: {sorted(api_names)}")

    return sorted(api_names)


def convert_apim_operations_to_endpoint_findings(
    operations: List[Dict],
    base_url: str
) -> List[EndpointFinding]:
    """Convert APIM operations JSON to EndpointFinding objects.

    Args:
        operations: List of APIM operation dictionaries
        base_url: API base URL (e.g., "https://data-exchange.misoenergy.org")

    Returns:
        List of EndpointFinding objects with basic parameter info
    """
    endpoints = []

    for op in operations:
        # Extract basic info
        op_id = op.get('id', op.get('name', 'unknown'))
        name = op.get('name') or op.get('displayName') or op_id
        method = op.get('method', 'GET').upper()
        url_template = op.get('urlTemplate') or op.get('path') or f"/{op_id}"
        description = op.get('description', '')

        # Construct full URL
        full_url = f"{base_url}{url_template}"

        # Extract basic parameters (name, type, required only)
        # Phase 1.5 will enrich these with formats/examples/defaults
        raw_parameters = op.get('parameters', [])
        if not raw_parameters and 'request' in op:
            # Alternative location for parameters
            request = op.get('request', {})
            raw_parameters = request.get('queryParameters', []) or request.get('parameters', [])

        basic_params = []
        for p in raw_parameters:
            basic_params.append({
                'name': p.get('name'),
                'type': p.get('type', 'string'),
                'required': p.get('required', False),
                'location': p.get('in', 'query'),
                'description': p.get('description', '')
            })

        # Determine format from response
        format_guess = 'json'  # Default
        responses = op.get('responses', {})
        if responses:
            first_response = list(responses.values())[0] if responses else {}
            if isinstance(first_response, dict):
                if 'representation' in first_response:
                    content_type = first_response['representation'].get('contentType', '')
                    if 'xml' in content_type:
                        format_guess = 'xml'
                    elif 'csv' in content_type:
                        format_guess = 'csv'

        endpoint = EndpointFinding(
            name=name,
            url=full_url,
            method_guess=method,
            auth_required="unknown",  # Will be determined in P2
            data_type="other",
            format=format_guess,
            freshness="unknown",
            pagination="unknown",
            notes=description,
            evidence_urls=[full_url],
            parameters=basic_params  # NEW FIELD with basic parameter info
        )

        endpoints.append(endpoint)

    logger.info(f"Converted {len(endpoints)} APIM operations to EndpointFinding objects")

    return endpoints


def extract_endpoints_from_html_docs(artifact: Any) -> List[EndpointFinding]:
    """Extract endpoints from HTML documentation (fallback when no spec found).

    Searches artifact text for endpoint patterns:
    - HTTP methods followed by paths (GET /v1/data, POST /api/users)
    - API endpoint cards/tables in documentation
    - URL patterns in network calls

    Args:
        artifact: Page artifact with text and network calls

    Returns:
        List of EndpointFinding objects extracted from HTML

    Note:
        This is a fallback when OpenAPI spec not available.
        Results will be less complete than spec-based extraction.
    """
    endpoints = []

    # Simple pattern matching for endpoints in text
    # Look for: METHOD /path/to/endpoint patterns
    import re

    text = artifact.markdown_excerpt or artifact.html_excerpt
    if not text:
        logger.warning("No text content available for HTML endpoint extraction")
        return endpoints

    # Pattern: GET|POST|PUT|DELETE|PATCH /api/...
    method_path_pattern = r'\b(GET|POST|PUT|DELETE|PATCH)\s+(/[a-zA-Z0-9/_-]+)'

    matches = re.findall(method_path_pattern, text, re.IGNORECASE)

    for method, path in matches:
        endpoint = EndpointFinding(
            name=f"{method} {path}",
            url=path,  # Relative path (will need base URL)
            method_guess=method.upper(),
            auth_required="unknown",
            data_type="other",
            format="unknown",
            freshness="unknown",
            pagination="unknown",
            notes="Extracted from HTML documentation (no OpenAPI spec found)",
            evidence_urls=[artifact.url]
        )
        endpoints.append(endpoint)

    # Also check network calls for API-like URLs
    for url in artifact.network_calls:
        if '/api/' in url or '/v1/' in url or '/v2/' in url:
            # Try to guess method from URL patterns
            method_guess = "GET"  # Default assumption
            if '/create' in url or '/add' in url:
                method_guess = "POST"
            elif '/update' in url or '/edit' in url:
                method_guess = "PUT"
            elif '/delete' in url or '/remove' in url:
                method_guess = "DELETE"

            endpoint = EndpointFinding(
                name=f"Network Call: {url}",
                url=url,
                method_guess=method_guess,
                auth_required="unknown",
                data_type="other",
                format="unknown",
                freshness="unknown",
                pagination="unknown",
                notes="Discovered in network calls (no OpenAPI spec found)",
                evidence_urls=[artifact.url]
            )
            endpoints.append(endpoint)

    # Deduplicate by URL
    seen_urls = set()
    unique_endpoints = []
    for ep in endpoints:
        if ep.url not in seen_urls:
            seen_urls.add(ep.url)
            unique_endpoints.append(ep)

    logger.info(f"Extracted {len(unique_endpoints)} endpoints from HTML documentation")

    return unique_endpoints


def convert_openapi_to_endpoint_findings(
    spec_data: Any,
    base_url: str = ""
) -> List[EndpointFinding]:
    """Convert parsed OpenAPI spec into EndpointFinding objects.

    Maps OpenAPI endpoint data to BA Analyst's EndpointFinding schema.

    Args:
        spec_data: Parsed OpenAPISpec object
        base_url: Base URL to prepend to relative paths

    Returns:
        List of EndpointFinding objects
    """
    endpoints = []

    # Get base URL from spec servers if not provided
    if not base_url and spec_data.servers:
        base_url = spec_data.servers[0].get('url', '').rstrip('/')

    for openapi_ep in spec_data.endpoints:
        # Construct full URL
        if base_url:
            full_url = f"{base_url}{openapi_ep.path}"
        else:
            full_url = openapi_ep.path

        # Determine format from responses
        format_guess = "json"  # Default assumption
        if openapi_ep.responses:
            first_response = list(openapi_ep.responses.values())[0]
            if isinstance(first_response, dict):
                content = first_response.get('content', {})
                if 'application/xml' in content:
                    format_guess = "xml"
                elif 'text/csv' in content:
                    format_guess = "csv"

        # Check if authentication required
        auth_required = "true" if openapi_ep.security else "false"

        endpoint = EndpointFinding(
            name=openapi_ep.summary or openapi_ep.operation_id or f"{openapi_ep.method} {openapi_ep.path}",
            url=full_url,
            method_guess=openapi_ep.method,
            auth_required=auth_required,
            data_type="other",  # Would need content analysis to determine
            format=format_guess,
            freshness="unknown",
            pagination="unknown",
            notes=openapi_ep.description or "Extracted from OpenAPI specification",
            evidence_urls=[full_url]
        )
        endpoints.append(endpoint)

    logger.info(f"Converted {len(endpoints)} OpenAPI endpoints to EndpointFinding objects")

    return endpoints


def api_p1_handler(state: BAAnalystState) -> Dict[str, Any]:
    """P1: Discover REST endpoints from API sources.

    Enhanced with APIM operations discovery for portals like MISO.
    Finds and parses APIM operations JSON or OpenAPI/Swagger specifications.
    Falls back to HTML documentation parsing if no spec found.

    Args:
        state: Current graph state with artifacts

    Returns:
        State updates with endpoints, auth_summary, and control flow
    """
    logger.info("=== API P1 Handler: Discovery Phase ===")

    # P1/P2 Bug #2 fix: Use last_analyzed_url instead of current_url
    last_analyzed_url = state.get("last_analyzed_url")
    artifacts = state.get("artifacts", {})

    if not last_analyzed_url or last_analyzed_url not in artifacts:
        logger.error(f"No artifact found for last_analyzed_url: {last_analyzed_url}")
        return {
            "p1_complete": False,
            "next_action": "continue",
            "gaps": ["API P1: No artifact available for analysis"]
        }

    artifact = artifacts[last_analyzed_url]

    # Step 0: Check if seed URL targets specific API (MISO operations discovery)
    seed_url = state.get('seed_url', '')
    target_api_name = extract_api_name_from_url(seed_url)
    if target_api_name:
        logger.info(f"Target API specified in seed URL: {target_api_name}")

    endpoints = []
    auth_summary = None

    # Step 1: Check for APIM portal pattern (MISO operations discovery)
    if is_apim_portal(artifact):
        logger.info("🔍 APIM portal detected - attempting APIM operations discovery")

        # Extract domain from artifact URL
        parsed_url = urlparse(artifact.url)
        domain = parsed_url.netloc

        # If user provided specific API in seed URL, fetch ONLY that API
        if target_api_name:
            logger.info(f"Fetching operations for target API: {target_api_name}")
            operations = discover_apim_operations_for_api(domain, target_api_name)

            if operations:
                base_url = f"{parsed_url.scheme}://{domain}"
                endpoints = convert_apim_operations_to_endpoint_findings(operations, base_url)
                auth_summary = "Authentication: Required (APIM portal, details TBD in P2)"

                logger.info(f"✅ APIM discovery successful: {len(endpoints)} operations for {target_api_name}")
        else:
            # No specific API - discover all APIs from catalog (limit to 5 to prevent explosion)
            logger.info("No specific API targeted - discovering all APIs from catalog")
            api_names = extract_api_names_from_catalog(artifact)

            if api_names:
                logger.info(f"Found {len(api_names)} APIs, fetching operations for first 5")
                all_operations = []

                for api_name in api_names[:5]:  # Limit to 5 APIs
                    operations = discover_apim_operations_for_api(domain, api_name)
                    all_operations.extend(operations)

                if all_operations:
                    base_url = f"{parsed_url.scheme}://{domain}"
                    endpoints = convert_apim_operations_to_endpoint_findings(all_operations, base_url)
                    auth_summary = "Authentication: Required (APIM portal, details TBD in P2)"

                    logger.info(f"✅ APIM discovery successful: {len(endpoints)} operations across {min(len(api_names), 5)} APIs")

        # If APIM discovery found endpoints, return them (skip OpenAPI/HTML fallback)
        if endpoints:
            config = state.get('config')
            max_ops = config.max_operations_per_api if config else 20

            # Cap operations to prevent explosion
            if len(endpoints) > max_ops:
                logger.warning(f"Capping {len(endpoints)} operations to {max_ops}")
                endpoints = endpoints[:max_ops]

            if len(endpoints) >= 5:
                logger.info(f"✅ API P1 (APIM) discovery successful: {len(endpoints)} endpoints found")
                return {
                    "endpoints": endpoints,
                    "auth_summary": auth_summary,
                    "p1_complete": True,
                    "next_action": "continue"  # Move to P1.5 (parameter analysis)
                }
            else:
                logger.warning(f"⚠️ API P1 (APIM) discovery incomplete: Only {len(endpoints)} endpoints found")
                # Fall through to OpenAPI/HTML fallback

    # Step 2: Standard OpenAPI/Swagger flow (if APIM didn't find anything)
    if not endpoints:
        navigation_links = [link.url for link in artifact.links]
        network_calls = artifact.network_calls
        page_text = artifact.markdown_excerpt or artifact.html_excerpt or ""

        spec_urls = find_openapi_spec_urls(navigation_links, network_calls, page_text)

        logger.info(f"Found {len(spec_urls)} candidate OpenAPI spec URLs")

        # Try to fetch and parse spec
        if spec_urls:
            for spec_url in spec_urls[:3]:  # Try first 3 candidates
                logger.info(f"Attempting to fetch OpenAPI spec from: {spec_url}")

                raw_spec = fetch_and_parse_spec(spec_url)
                if not raw_spec:
                    logger.warning(f"Failed to fetch/parse spec from {spec_url}")
                    continue

                # Parse into structured format
                parsed_spec = parse_openapi_spec(raw_spec)
                if not parsed_spec:
                    logger.warning(f"Failed to parse OpenAPI spec structure from {spec_url}")
                    continue

                # Convert to EndpointFinding objects
                endpoints = convert_openapi_to_endpoint_findings(parsed_spec)

                # Extract auth summary from security schemes
                if parsed_spec.security_schemes:
                    auth_methods = list(parsed_spec.security_schemes.keys())
                    auth_summary = f"Authentication required: {', '.join(auth_methods)}"
                else:
                    auth_summary = "Authentication: Not specified in spec"

                logger.info(
                    f"✅ Successfully parsed OpenAPI spec: {parsed_spec.title} v{parsed_spec.version}, "
                    f"{len(endpoints)} endpoints"
                )

                break  # Found valid spec, stop trying

    # Step 3: Fallback to HTML documentation parsing if no spec found
    if not endpoints:
        logger.warning("No APIM operations or OpenAPI spec found, falling back to HTML documentation extraction")
        endpoints = extract_endpoints_from_html_docs(artifact)

        if not endpoints:
            logger.error("No endpoints extracted from HTML documentation either")
            return {
                "endpoints": [],
                "gaps": ["API P1: No APIM operations, OpenAPI spec, or HTML endpoints found"],
                "p1_complete": False,
                "next_action": "continue"
            }

        auth_summary = "Authentication: Unknown (no spec found)"

    # Step 4: Return results
    if len(endpoints) >= 5:
        logger.info(f"✅ API P1 discovery successful: {len(endpoints)} endpoints found")
        return {
            "endpoints": endpoints,
            "auth_summary": auth_summary,
            "p1_complete": True,
            "next_action": "continue"  # Move to P1.5 (parameter analysis)
        }
    else:
        logger.warning(f"⚠️ API P1 discovery incomplete: Only {len(endpoints)} endpoints found (need 5+)")
        return {
            "endpoints": endpoints,
            "auth_summary": auth_summary,
            "gaps": [f"API P1: Only found {len(endpoints)} endpoints, need 5+"],
            "p1_complete": False,
            "next_action": "continue"
        }


# Export
__all__ = ["api_p1_handler"]
