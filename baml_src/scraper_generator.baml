// BAML Functions for Scraper Code Generation
// Generates Python code for complex scraper logic that cannot be templated

// ============================================================================
// Code Generation Types
// ============================================================================

class GeneratedCode {
    code string @description("Generated Python code")
    imports string[] @description("Required imports (if any additional needed)")
    notes string @description("Implementation notes or warnings")
}

class ValidationRules {
    required_fields string[] @description("Fields that must be present")
    format_checks string[] @description("Format validation checks")
    range_checks string[] @description("Value range validations")
    custom_logic string @description("Custom validation logic description")
}

// ============================================================================
// Generate collect_content() Method Body
// ============================================================================

function GenerateCollectContent(
    ba_spec_json: string,
    endpoint: string,
    auth_method: string,
    data_format: string,
    timeout_seconds: int,
    retry_attempts: int
) -> GeneratedCode {
    client ClaudeBedrock
    prompt #"
        You are generating the Python implementation for a collect_content() method
        in a data collector class that inherits from BaseCollector.

        BA Analyzer Spec (JSON):
        {{ ba_spec_json }}

        Endpoint: {{ endpoint }}
        Authentication: {{ auth_method }}
        Data Format: {{ data_format }}
        Timeout: {{ timeout_seconds }} seconds
        Retry Attempts: {{ retry_attempts }}

        Generate the METHOD BODY ONLY (not the method signature) for:

        ```python
        def collect_content(self, candidate: DownloadCandidate) -> CollectedContent:
            # YOUR GENERATED CODE HERE
        ```

        Requirements:

        1. HTTP Request Logic:
           - Use requests library with proper error handling
           - Include retry logic with exponential backoff
           - Handle timeouts correctly
           - Log each attempt

        2. Authentication:
           {% if auth_method == "API_KEY" or auth_method == "BEARER_TOKEN" or auth_method == "BASIC_AUTH" %}
           - Use self.auth_headers (already set up in __init__)
           - Pass headers to requests.get()
           {% elif auth_method == "OAUTH" %}
           - Implement OAuth token exchange if needed
           - Refresh token handling
           {% elif auth_method == "NONE" %}
           - No authentication headers needed
           {% else %}
           - Custom authentication logic as described in BA spec
           {% endif %}

        3. Response Processing:
           {% if data_format == "json" %}
           - Parse JSON with error handling
           - Validate JSON structure
           - Extract relevant data
           {% elif data_format == "csv" %}
           - Read CSV content
           - Validate CSV structure
           {% elif data_format == "xml" %}
           - Parse XML with error handling
           - Validate XML structure
           {% else %}
           - Handle binary/text content appropriately
           {% endif %}

        4. Error Handling:
           - Try-except blocks for HTTP errors
           - Try-except blocks for parsing errors
           - Log errors with context
           - Return CollectedContent with success=False on errors

        5. Return Value:
           Return CollectedContent(
               candidate=candidate,
               success=True/False,
               content=bytes,  # Raw content
               content_hash=computed_hash,
               error_message=None or error string,
               metadata={...}  # Any additional metadata
           )

        6. Code Style:
           - Use existing logger instance (logger.info, logger.error)
           - Follow PEP 8 style
           - Add inline comments for complex logic
           - Use type hints
           - Handle edge cases

        IMPORTANT:
        - Generate ONLY the method body (the code inside the function)
        - Do NOT include the method signature "def collect_content(...):"
        - Do NOT include docstring (template already has it)
        - Assume self.base_url, self.auth_headers, self.timeout, self.retry_attempts exist
        - Assume imports: requests, logging, hashlib, json
        - Use 4-space indentation
        - End with return statement

        Example structure:
        ```python
        url = candidate.url
        headers = self.auth_headers.copy()

        for attempt in range(self.retry_attempts):
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()

                # Parse content
                content = response.content
                content_hash = hashlib.sha256(content).hexdigest()

                logger.info(f"Successfully collected content from {url}")

                return CollectedContent(
                    candidate=candidate,
                    success=True,
                    content=content,
                    content_hash=content_hash,
                )

            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == self.retry_attempts - 1:
                    return CollectedContent(
                        candidate=candidate,
                        success=False,
                        error_message=str(e),
                    )
                time.sleep(2 ** attempt)  # Exponential backoff
        ```

        {{ ctx.output_format }}
    "#
}

// ============================================================================
// Generate validate_content() Method Body
// ============================================================================

function GenerateValidateContent(
    ba_spec_json: string,
    endpoint: string,
    data_format: string,
    validation_requirements: string
) -> GeneratedCode {
    client ClaudeBedrock
    prompt #"
        You are generating the Python implementation for a validate_content() method
        in a data collector class that inherits from BaseCollector.

        BA Analyzer Spec (JSON):
        {{ ba_spec_json }}

        Endpoint: {{ endpoint }}
        Data Format: {{ data_format }}
        Validation Requirements: {{ validation_requirements }}

        Generate the METHOD BODY ONLY for:

        ```python
        def validate_content(self, content: CollectedContent) -> ValidationResult:
            # YOUR GENERATED CODE HERE
        ```

        Requirements:

        1. Basic Validations (Always Include):
           - Check content is not empty
           - Check content is not None
           - Verify content size is reasonable (not 0 bytes, not > 100MB)

        2. Format-Specific Validations:
           {% if data_format == "json" %}
           JSON Validation:
           - Verify valid JSON syntax (json.loads)
           - Check required top-level keys exist
           - Validate data types of key fields
           - Check for expected structure (arrays, objects)
           - Verify data array is not empty
           {% elif data_format == "csv" %}
           CSV Validation:
           - Verify CSV can be parsed
           - Check header row exists
           - Validate column names match expected
           - Check minimum number of rows
           - Verify data types in key columns
           {% elif data_format == "xml" %}
           XML Validation:
           - Verify valid XML syntax
           - Check root element is correct
           - Validate required elements exist
           - Check namespaces if applicable
           {% else %}
           Generic Validation:
           - Check content type matches expected
           - Verify minimum size requirements
           - Check for error indicators in content
           {% endif %}

        3. Business Logic Validations (Based on BA Spec):
           - Timestamp/date fields are valid ISO8601
           - Numeric fields are in expected ranges
           - Required fields are present
           - Data consistency checks

        4. Return Value:
           - Return ValidationResult with:
             * is_valid: True/False
             * errors: List of error messages (empty if valid)
             * warnings: List of warnings (non-critical issues)
             * metadata: Dict with validation stats

        5. Error Handling:
           - Try-except for parsing errors
           - Collect ALL validation errors (don't fail on first)
           - Log validation issues
           - Clear error messages

        6. Code Style:
           - Use existing logger
           - Follow PEP 8
           - Type hints
           - Inline comments

        IMPORTANT:
        - Generate ONLY the method body
        - Do NOT include method signature or docstring
        - Assume content.content is bytes
        - Assume content.success is bool
        - Use 4-space indentation
        - Return ValidationResult at the end

        Example structure:
        ```python
        errors = []
        warnings = []

        # Check if collection succeeded
        if not content.success:
            errors.append("Content collection failed")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
            )

        # Check content exists
        if not content.content:
            errors.append("Content is empty")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
            )

        # Parse and validate format
        try:
            data = json.loads(content.content)

            # Check required fields
            if "data" not in data:
                errors.append("Missing 'data' field in JSON")

            # Validate data array
            if "data" in data:
                if not isinstance(data["data"], list):
                    errors.append("'data' field must be an array")
                elif len(data["data"]) == 0:
                    warnings.append("'data' array is empty")

        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON: {e}")

        # Return result
        is_valid = len(errors) == 0

        logger.info(
            f"Validation {'passed' if is_valid else 'failed'}",
            extra={
                "errors": len(errors),
                "warnings": len(warnings),
            },
        )

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            metadata={"content_size": len(content.content)},
        )
        ```

        {{ ctx.output_format }}
    "#
}

// ============================================================================
// Generate Complex Authentication Logic
// ============================================================================

function GenerateComplexAuth(
    auth_spec: string,
    auth_method: string,
    registration_url: string
) -> GeneratedCode {
    client ClaudeBedrock
    prompt #"
        You are generating Python code for complex authentication setup.

        Authentication Spec:
        {{ auth_spec }}

        Auth Method: {{ auth_method }}
        Registration URL: {{ registration_url }}

        This code will be inserted into the _init_auth() method of a collector class.

        Generate authentication setup code for:

        {% if auth_method == "OAUTH" %}
        OAuth Authentication:
        - Token endpoint configuration
        - Client ID/secret handling
        - Token exchange flow
        - Token refresh logic
        - Store token in self.auth_headers
        {% elif auth_method == "SAML" %}
        SAML Authentication:
        - SAML endpoint configuration
        - Certificate handling
        - Assertion generation
        - Token extraction
        {% elif auth_method == "COOKIE" %}
        Cookie-Based Authentication:
        - Login request setup
        - Session cookie extraction
        - Cookie storage for requests
        {% elif auth_method == "MFA" %}
        Multi-Factor Authentication:
        - Initial login request
        - MFA challenge handling
        - Token verification
        - Final authentication
        {% else %}
        Custom Authentication:
        - Parse auth_spec for requirements
        - Implement described authentication flow
        - Handle credentials securely
        {% endif %}

        Requirements:

        1. Credential Handling:
           - Read from environment variables (never hardcode)
           - Validate credentials exist
           - Raise clear error if missing

        2. Token Management (if applicable):
           - Request token from auth endpoint
           - Parse token from response
           - Store token in self.auth_headers
           - Handle token expiration
           - Implement token refresh

        3. Error Handling:
           - Try-except for auth requests
           - Clear error messages
           - Log authentication attempts
           - Raise ValueError on auth failure

        4. Security:
           - Never log credentials
           - Use HTTPS for auth requests
           - Validate SSL certificates
           - Use secure token storage

        5. Code Style:
           - Use existing logger
           - Follow PEP 8
           - Type hints
           - Inline comments

        IMPORTANT:
        - Generate code that will be inserted into _init_auth() method
        - Assume self.api_key exists (from __init__ parameter)
        - Set self.auth_headers = {...} at the end
        - Use 4-space indentation
        - Import any additional libraries needed (add to imports list)

        Example for OAuth:
        ```python
        # OAuth token endpoint
        token_url = "https://auth.example.com/oauth/token"

        # Request access token
        try:
            response = requests.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.api_key.split(":")[0],
                    "client_secret": self.api_key.split(":")[1],
                },
                timeout=30,
            )
            response.raise_for_status()

            token_data = response.json()
            access_token = token_data["access_token"]

            # Store in auth headers
            self.auth_headers = {
                "Authorization": f"Bearer {access_token}",
            }

            logger.info("OAuth authentication successful")

        except requests.RequestException as e:
            raise ValueError(f"OAuth authentication failed: {e}")
        except (KeyError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to parse OAuth token: {e}")
        ```

        {{ ctx.output_format }}
    "#
}

// ============================================================================
// Generate Custom __init__ Logic
// ============================================================================

function GenerateInitCode(
    ba_spec_json: string,
    custom_requirements: string
) -> GeneratedCode {
    client ClaudeBedrock
    prompt #"
        You are generating custom initialization code for a collector class.

        BA Analyzer Spec (JSON):
        {{ ba_spec_json }}

        Custom Requirements:
        {{ custom_requirements }}

        Generate additional initialization code that will be inserted at the END
        of the __init__ method, after standard initialization.

        Use cases:
        - Setting up custom clients (Selenium, Playwright, FTP, SMTP)
        - Initializing complex data structures
        - Pre-loading configuration
        - Setting up connection pools

        Requirements:

        1. Custom Client Setup:
           - Initialize any special clients (Selenium, Playwright)
           - Configure client options
           - Store client as self attribute
           - Handle initialization errors

        2. Configuration Loading:
           - Load any additional config files
           - Parse custom settings
           - Validate configuration
           - Set default values

        3. Resource Initialization:
           - Set up connection pools
           - Initialize caches
           - Prepare data structures

        4. Error Handling:
           - Try-except for setup errors
           - Clear error messages
           - Log initialization steps

        5. Code Style:
           - Use existing logger
           - Follow PEP 8
           - Type hints
           - Inline comments

        IMPORTANT:
        - Generate code that will be added to __init__ method
        - Assume standard __init__ parameters already exist
        - Use self.attribute_name for new attributes
        - Use 4-space indentation
        - Import any additional libraries (add to imports list)

        Example for Selenium setup:
        ```python
        # Initialize Selenium WebDriver for JavaScript rendering
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("Selenium WebDriver initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Selenium: {e}")
            self.driver = None
        ```

        {{ ctx.output_format }}
    "#
}
