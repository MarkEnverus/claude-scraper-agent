"""OpenAPI/Swagger spec parsing utilities for API sources.

This module provides functions to find, fetch, and parse OpenAPI/Swagger
specifications to extract REST endpoint definitions.

Critical for API documentation portals where endpoint metadata is available
in machine-readable spec files (JSON/YAML).
"""

import logging
import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import httpx

logger = logging.getLogger(__name__)


@dataclass
class OpenAPIEndpoint:
    """Parsed endpoint from OpenAPI spec."""
    path: str  # /v1/pricing/lmp
    method: str  # GET, POST, PUT, DELETE, PATCH
    operation_id: str  # Unique operation ID
    summary: str  # Brief description
    description: str  # Detailed description
    parameters: List[Dict[str, Any]]  # Parameter specs
    request_body: Optional[Dict[str, Any]]  # Request body schema
    responses: Dict[str, Any]  # Response specs by status code
    security: List[Dict[str, Any]]  # Security requirements
    tags: List[str]  # Tags for grouping


@dataclass
class OpenAPISpec:
    """Parsed OpenAPI/Swagger specification."""
    openapi_version: str  # 3.0.0, 3.1.0, 2.0 (swagger)
    title: str  # API title
    version: str  # API version
    description: str  # API description
    servers: List[Dict[str, str]]  # Server URLs
    endpoints: List[OpenAPIEndpoint]  # All endpoints
    security_schemes: Dict[str, Any]  # Security scheme definitions
    raw_spec: Dict[str, Any]  # Raw spec for reference


def find_openapi_spec_urls(
    links: List[str],
    network_calls: List[str],
    page_text: str
) -> List[str]:
    """Find OpenAPI/Swagger spec URLs from multiple sources.

    Searches for spec URLs matching common patterns:
    - /openapi.json, /swagger.json
    - /api-docs, /v1/api-docs
    - /openapi, /swagger
    - .yaml files with openapi/swagger in name
    - References in page text

    Args:
        links: Navigation links from page
        network_calls: Network calls captured during page load
        page_text: Page text content

    Returns:
        List of candidate spec URLs (deduplicated)

    Example:
        >>> links = ["https://api.example.com/openapi.json", "https://api.example.com/docs"]
        >>> find_openapi_spec_urls(links, [], "")
        ['https://api.example.com/openapi.json']
    """
    # Spec URL patterns
    patterns = [
        r'/openapi\.json',
        r'/swagger\.json',
        r'/api-docs',
        r'/v\d+/openapi',
        r'/v\d+/swagger',
        r'\.yaml.*openapi',
        r'\.yml.*swagger',
        r'/docs/openapi',
        r'/api/spec',
    ]

    candidates = []

    # Check links and network calls
    for source in links + network_calls:
        if any(re.search(p, source, re.IGNORECASE) for p in patterns):
            candidates.append(source)

    # Check page text for spec references
    # Look for common spec URL patterns in text
    url_pattern = r'https?://[^\s<>"\']+(?:openapi|swagger|api-docs)[^\s<>"\']*'
    text_urls = re.findall(url_pattern, page_text, re.IGNORECASE)
    candidates.extend(text_urls)

    # Deduplicate while preserving order
    unique_urls = list(dict.fromkeys(candidates))

    logger.info(f"Found {len(unique_urls)} candidate OpenAPI spec URLs")

    return unique_urls


def fetch_and_parse_spec(spec_url: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
    """Fetch and parse OpenAPI/Swagger spec from URL.

    Supports both JSON and YAML formats. Detects format from:
    1. File extension (.json, .yaml, .yml)
    2. Content-Type header
    3. Try JSON first, fallback to YAML

    Args:
        spec_url: URL to OpenAPI/Swagger spec
        timeout: Request timeout in seconds

    Returns:
        Parsed spec as dictionary, or None if fetch/parse fails

    Example:
        >>> spec = fetch_and_parse_spec("https://api.example.com/openapi.json")
        >>> spec['openapi']
        '3.0.0'
    """
    try:
        logger.info(f"Fetching OpenAPI spec from: {spec_url}")

        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(spec_url)
            response.raise_for_status()

            content_type = response.headers.get('content-type', '').lower()

            # Try JSON first
            if '.json' in spec_url.lower() or 'json' in content_type:
                try:
                    spec = response.json()
                    logger.info(f"Successfully parsed JSON spec from {spec_url}")
                    return spec
                except Exception as e:
                    logger.warning(f"Failed to parse as JSON: {e}")

            # Try YAML
            if '.yaml' in spec_url.lower() or '.yml' in spec_url.lower() or 'yaml' in content_type:
                try:
                    import yaml
                    spec = yaml.safe_load(response.text)
                    logger.info(f"Successfully parsed YAML spec from {spec_url}")
                    return spec
                except ImportError:
                    logger.error("PyYAML not installed, cannot parse YAML specs")
                    return None
                except Exception as e:
                    logger.warning(f"Failed to parse as YAML: {e}")

            # Fallback: try both formats
            try:
                spec = response.json()
                logger.info(f"Successfully parsed spec as JSON (fallback) from {spec_url}")
                return spec
            except:
                try:
                    import yaml
                    spec = yaml.safe_load(response.text)
                    logger.info(f"Successfully parsed spec as YAML (fallback) from {spec_url}")
                    return spec
                except:
                    logger.error(f"Failed to parse spec from {spec_url} as JSON or YAML")
                    return None

    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching spec from {spec_url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching spec from {spec_url}: {e}", exc_info=True)
        return None


def parse_openapi_spec(raw_spec: Dict[str, Any]) -> Optional[OpenAPISpec]:
    """Parse OpenAPI/Swagger spec into structured format.

    Extracts:
    - API metadata (title, version, description)
    - Server URLs
    - All endpoints with methods, parameters, responses
    - Security schemes

    Supports:
    - OpenAPI 3.0.x, 3.1.x
    - Swagger 2.0 (basic support)

    Args:
        raw_spec: Raw spec dictionary (from fetch_and_parse_spec)

    Returns:
        Parsed OpenAPISpec, or None if parsing fails

    Example:
        >>> spec = parse_openapi_spec(raw_spec_dict)
        >>> len(spec.endpoints)
        15
        >>> spec.endpoints[0].path
        '/v1/pricing/lmp'
    """
    try:
        # Detect spec version
        openapi_version = raw_spec.get('openapi', raw_spec.get('swagger', 'unknown'))

        # Extract API metadata
        info = raw_spec.get('info', {})
        title = info.get('title', 'Unknown API')
        version = info.get('version', 'unknown')
        description = info.get('description', '')

        # Extract servers (OpenAPI 3.x) or basePath (Swagger 2.0)
        servers = raw_spec.get('servers', [])
        if not servers and 'basePath' in raw_spec:
            # Swagger 2.0: construct server from host + basePath
            host = raw_spec.get('host', '')
            base_path = raw_spec.get('basePath', '')
            schemes = raw_spec.get('schemes', ['https'])
            servers = [{'url': f"{schemes[0]}://{host}{base_path}"}]

        # Extract security schemes
        security_schemes = raw_spec.get('components', {}).get('securitySchemes', {})
        if not security_schemes:
            # Swagger 2.0
            security_schemes = raw_spec.get('securityDefinitions', {})

        # Extract endpoints from paths
        endpoints = []
        paths = raw_spec.get('paths', {})

        for path, path_item in paths.items():
            # Path item may have operations: get, post, put, delete, patch, etc.
            for method in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
                if method not in path_item:
                    continue

                operation = path_item[method]

                endpoint = OpenAPIEndpoint(
                    path=path,
                    method=method.upper(),
                    operation_id=operation.get('operationId', f"{method}_{path}"),
                    summary=operation.get('summary', ''),
                    description=operation.get('description', ''),
                    parameters=operation.get('parameters', []),
                    request_body=operation.get('requestBody'),
                    responses=operation.get('responses', {}),
                    security=operation.get('security', []),
                    tags=operation.get('tags', [])
                )

                endpoints.append(endpoint)

        logger.info(
            f"Parsed OpenAPI spec: {title} v{version}, "
            f"{len(endpoints)} endpoints, "
            f"{len(servers)} servers"
        )

        return OpenAPISpec(
            openapi_version=openapi_version,
            title=title,
            version=version,
            description=description,
            servers=servers,
            endpoints=endpoints,
            security_schemes=security_schemes,
            raw_spec=raw_spec
        )

    except Exception as e:
        logger.error(f"Failed to parse OpenAPI spec: {e}", exc_info=True)
        return None


def construct_full_endpoint_urls(spec: OpenAPISpec) -> List[str]:
    """Construct full endpoint URLs from OpenAPI spec.

    Combines server base URLs with endpoint paths to create
    complete endpoint URLs for testing/validation.

    Args:
        spec: Parsed OpenAPI spec

    Returns:
        List of full endpoint URLs

    Example:
        >>> urls = construct_full_endpoint_urls(spec)
        >>> urls[0]
        'https://api.example.com/v1/pricing/lmp'
    """
    urls = []

    # Get base URL (use first server if multiple)
    base_url = ""
    if spec.servers:
        base_url = spec.servers[0].get('url', '').rstrip('/')

    for endpoint in spec.endpoints:
        # Combine base URL with endpoint path
        if base_url:
            full_url = f"{base_url}{endpoint.path}"
        else:
            # No base URL, use path as-is (relative)
            full_url = endpoint.path

        urls.append(full_url)

    logger.debug(f"Constructed {len(urls)} full endpoint URLs from spec")

    return urls


# Export public API
__all__ = [
    'OpenAPIEndpoint',
    'OpenAPISpec',
    'find_openapi_spec_urls',
    'fetch_and_parse_spec',
    'parse_openapi_spec',
    'construct_full_endpoint_urls',
]
