"""Code generation prompts for HybridGenerator (migrated from BAML)

These prompts generate Python code for scrapers based on BA analysis specifications.
"""

from typing import Any
import json


# BaseCollector interface context for LLM code generation
INTERFACE_CONTEXT = """
## BaseCollector Interface Contract

You are implementing methods for a class that inherits from BaseCollector.

**Available Instance Variables:**
- self.dgroup: str - Data group identifier
- self.s3_uploader: S3Uploader - S3 upload manager
- self.hash_registry: HashRegistry - Deduplication registry
- self.environment: str - Environment (dev/staging/prod)
- self.kafka_connection_string: Optional[str] - Kafka connection
- self.timeout: int - Request timeout in seconds
- self.retry_attempts: int - Number of retry attempts
- self.base_url: str - API base URL
- self.endpoints: List[Dict] - Endpoint configurations
- self.auth_headers: Dict - Pre-configured auth headers
- self.api_key: Optional[str] - API key (if applicable)

**Logging:**
Use module-level logger (already imported at top of file):
```python
logger.info("message", extra={...})
logger.warning("message", extra={...})
logger.error("message", extra={...})
```

**DO NOT use:**
- self.logger (doesn't exist)
- self.config (doesn't exist)

**Method Signatures:**
```python
def collect_content(self, candidate: DownloadCandidate) -> bytes:
    # Use candidate.source_location for URL (already contains proper URL with params)
    # Use candidate.collection_params for headers/timeout
    # Raise ScrapingError for failures
    pass

def validate_content(self, content: bytes, candidate: DownloadCandidate) -> bool:
    # Return False for invalid content (don't raise exceptions)
    # Return True for valid content
    # DO NOT raise exceptions for validation failures
    pass
```

**Error Handling:**
- Import: `from sourcing.exceptions import ScrapingError`
- Use: `raise ScrapingError("message")` for collection failures
- Don't retry on: 401, 403, 404 (authentication/authorization failures)
- Retry with exponential backoff for: 5xx, timeouts, connection errors
"""


def generate_collect_content_prompt(
    ba_spec_json: str,
    endpoint: str,
    auth_method: str,
    data_format: str,
    timeout_seconds: int,
    retry_attempts: int
) -> str:
    """Generate collect_content() method code.

    Original: baml_src/scraper_generator.baml -> GenerateCollectContent()

    Args:
        ba_spec_json: Complete BA spec as JSON string
        endpoint: Endpoint identifier/URL
        auth_method: Authentication method (API_KEY, BEARER_TOKEN, etc.)
        data_format: Expected data format (JSON, CSV, XML, etc.)
        timeout_seconds: Request timeout in seconds
        retry_attempts: Number of retry attempts for failures

    Returns:
        Prompt string for Claude to generate collect_content() code
    """
    return f"""You are an expert Python developer generating production-ready scraper code.

{INTERFACE_CONTEXT}

Generate the METHOD BODY ONLY for a collect_content() method that fetches data from an API endpoint.

## BA Specification:
{ba_spec_json}

## Requirements:
- **Endpoint**: {endpoint}
- **Authentication**: {auth_method}
- **Data Format**: {data_format}
- **Timeout**: {timeout_seconds} seconds
- **Retries**: {retry_attempts} attempts

## Method Signature (DO NOT include this - only generate the body):
```python
def collect_content(self, candidate: DownloadCandidate) -> bytes:
```

## Implementation Requirements:

1. **Use Candidate URL:**
   ```python
   url = candidate.source_location  # Already contains proper URL with params
   ```

2. **Use Pre-configured Headers:**
   ```python
   headers = candidate.collection_params.get("headers", self.auth_headers)
   timeout = candidate.collection_params.get("timeout", self.timeout)
   ```

3. **Proper Logging (module-level logger):**
   ```python
   logger.info(f"Fetching data from {{url}}", extra={{"candidate": candidate.identifier}})
   ```

4. **Return bytes:**
   ```python
   return response.content  # bytes, not response.text
   ```

## Code Generation Guidelines:
1. Use `requests` library for HTTP calls
2. Handle authentication ({auth_method}) using self.auth_headers
3. Use timeout from candidate.collection_params or self.timeout
4. Implement retry logic with exponential backoff ({retry_attempts} attempts)
5. Use module-level `logger` (NOT self.logger)
6. Raise ScrapingError (not generic exceptions) for failures
7. Don't retry on 401, 403, 404 (auth failures)
8. DO NOT include the method signature, only the body
9. Indent code with 4 spaces (method body level)

## Example Structure:
```python
    # Method body starts here (4-space indent)
    url = candidate.source_location
    logger.info(f"Fetching data from {{url}}", extra={{"candidate": candidate.identifier}})

    # Use pre-configured headers
    headers = candidate.collection_params.get("headers", self.auth_headers)
    timeout = candidate.collection_params.get("timeout", self.timeout)

    # Retry loop
    for attempt in range(self.retry_attempts):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            logger.info("Successfully fetched data", extra={{"candidate": candidate.identifier}})
            return response.content
        except requests.HTTPError as e:
            # Don't retry auth failures
            if e.response.status_code in (401, 403, 404):
                logger.error(f"Authentication/Not Found error: {{e}}")
                raise ScrapingError(f"HTTP {{e.response.status_code}}: {{e}}")
            # Retry for other errors
            if attempt == self.retry_attempts - 1:
                raise ScrapingError(f"Failed after {{self.retry_attempts}} attempts: {{e}}")
            logger.warning(f"Attempt {{attempt+1}} failed: {{e}}")
            time.sleep(2 ** attempt)
```

Return ONLY the method body code (no signature, no markdown formatting)."""


def generate_validate_content_prompt(
    ba_spec_json: str,
    endpoint: str,
    data_format: str,
    validation_requirements: str
) -> str:
    """Generate validate_content() method code.

    Original: baml_src/scraper_generator.baml -> GenerateValidateContent()

    Args:
        ba_spec_json: Complete BA spec as JSON string
        endpoint: Endpoint identifier/URL
        data_format: Expected data format (JSON, CSV, XML, etc.)
        validation_requirements: JSON string with validation rules

    Returns:
        Prompt string for Claude to generate validate_content() code
    """
    return f"""You are an expert Python developer generating production-ready data validation code.

{INTERFACE_CONTEXT}

Generate the METHOD BODY ONLY for a validate_content() method that validates fetched data.

## BA Specification:
{ba_spec_json}

## Requirements:
- **Endpoint**: {endpoint}
- **Data Format**: {data_format}
- **Validation Rules**: {validation_requirements}

## Method Signature (DO NOT include this - only generate the body):
```python
def validate_content(self, content: bytes, candidate: DownloadCandidate) -> bool:
```

## Validation Requirements:

1. **Return bool, don't raise:**
   ```python
   if not content:
       logger.warning("Empty content", extra={{"candidate": candidate.identifier}})
       return False  # DON'T raise

   try:
       data = json.loads(content)
   except json.JSONDecodeError:
       logger.warning("Invalid JSON", extra={{"candidate": candidate.identifier}})
       return False  # DON'T raise

   # ... validation checks ...

   return True  # Success
   ```

2. **Use module-level logger:**
   ```python
   logger.info("validation message", extra={{"candidate": candidate.identifier}})
   ```

## Code Generation Guidelines:
1. Parse content based on format ({data_format})
2. Validate structure and required fields
3. Check data types and value ranges
4. Use module-level `logger` (NOT self.logger)
5. Return False for validation failures (DON'T raise exceptions)
6. Return True when validation passes
7. Only raise for unexpected/fatal errors
8. DO NOT include the method signature, only the body
9. Indent code with 4 spaces (method body level)

## Example Structure:
```python
    # Method body starts here (4-space indent)
    logger.info("Validating fetched content", extra={{"candidate": candidate.identifier}})

    # Check for empty content
    if not content:
        logger.warning("Empty content received", extra={{"candidate": candidate.identifier}})
        return False

    # Parse based on format
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON: {{e}}", extra={{"candidate": candidate.identifier}})
        return False

    # Validate structure
    if "required_field" not in data:
        logger.warning("Missing required_field", extra={{"candidate": candidate.identifier}})
        return False

    # All checks passed
    logger.info("Content validation passed", extra={{"candidate": candidate.identifier}})
    return True
```

Return ONLY the method body code (no signature, no markdown formatting)."""


def generate_complex_auth_prompt(
    auth_spec: str,
    auth_method: str,
    registration_url: str = ""
) -> str:
    """Generate __init__() authentication setup code for complex auth methods.

    Original: baml_src/scraper_generator.baml -> GenerateComplexAuth()

    Only called for: OAUTH, SAML, MFA, COOKIE authentication methods.

    Args:
        auth_spec: JSON string with authentication details
        auth_method: Authentication method (OAUTH, SAML, MFA, COOKIE)
        registration_url: Optional registration/OAuth URL

    Returns:
        Prompt string for Claude to generate __init__() auth code
    """
    return f"""You are an expert Python developer generating authentication setup code.

{INTERFACE_CONTEXT}

Generate CODE SNIPPET for __init__() method that sets up {auth_method} authentication.

## Authentication Specification:
{auth_spec}

## Requirements:
- **Auth Method**: {auth_method}
- **Registration URL**: {registration_url or "N/A"}

## Code Generation Guidelines:
1. Generate code that would go INSIDE __init__() method (after super().__init__())
2. Set up authentication session/tokens
3. Handle {auth_method} flow appropriately
4. Store credentials securely (use environment variables)
5. Use module-level `logger` (NOT self.logger)
6. Add error handling
7. DO NOT include method signature
8. Indent with 8 spaces (inside __init__ method)

## Example Structure for {auth_method}:
```python
        # Auth setup starts here (8-space indent, inside __init__)
        logger.info("Setting up {auth_method} authentication")

        # Load credentials from environment
        self.auth_token = os.getenv("AUTH_TOKEN")
        if not self.auth_token:
            logger.error("{auth_method} token not found in environment")
            raise ValueError("{auth_method} token not found in environment")

        # Initialize session with auth
        self.session = requests.Session()
        self.session.headers.update({{"Authorization": f"Bearer {{self.auth_token}}"}})

        logger.info("{auth_method} authentication configured successfully")
```

Return ONLY the code snippet (no signature, no markdown formatting)."""
