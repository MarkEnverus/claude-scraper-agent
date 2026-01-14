"""Business Analyst (BA) agent types.

This module contains all Pydantic models and enums used throughout the
BA analysis pipeline (Phase 0-3). Migrated from types.py for better organization.
"""

from enum import Enum
from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Enums
# ============================================================================

class DataSourceType(str, Enum):
    """Type of data source being analyzed."""
    API = "API"
    FTP = "FTP"
    WEBSITE = "WEBSITE"
    EMAIL = "EMAIL"


class HTTPMethod(str, Enum):
    """HTTP request methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class AuthenticationMethod(str, Enum):
    """Authentication methods for data sources."""
    NONE = "NONE"
    API_KEY = "API_KEY"
    BEARER_TOKEN = "BEARER_TOKEN"
    OAUTH = "OAUTH"
    BASIC_AUTH = "BASIC_AUTH"
    COOKIE = "COOKIE"
    UNKNOWN = "UNKNOWN"


class ValidationStatus(str, Enum):
    """Status of endpoint validation testing."""
    TESTED_200_OK = "TESTED_200_OK"
    TESTED_401_UNAUTHORIZED = "TESTED_401_UNAUTHORIZED"
    TESTED_403_FORBIDDEN = "TESTED_403_FORBIDDEN"
    TESTED_404_NOT_FOUND = "TESTED_404_NOT_FOUND"
    BROKEN = "BROKEN"
    NOT_TESTED = "NOT_TESTED"


class ExtractionQuality(str, Enum):
    """Quality of data extraction from documentation."""
    COMPREHENSIVE = "COMPREHENSIVE"
    PARTIAL = "PARTIAL"
    LIMITED = "LIMITED"
    MISSING = "MISSING"


class ConfidenceLevel(str, Enum):
    """Confidence level in analysis results."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DocQuality(str, Enum):
    """Quality of documentation found."""
    EXCELLENT = "EXCELLENT"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    POOR = "POOR"


class PortalType(str, Enum):
    """Type of web portal."""
    STATIC = "STATIC"
    SPA = "SPA"
    API_DOCS = "API_DOCS"
    CUSTOM_FRAMEWORK = "CUSTOM_FRAMEWORK"


class ResponseFormat(str, Enum):
    """Format of API response data."""
    JSON = "JSON"
    XML = "XML"
    CSV = "CSV"
    HTML = "HTML"
    BINARY = "BINARY"


class ParameterLocation(str, Enum):
    """Location of API parameters."""
    PATH = "PATH"
    QUERY = "QUERY"
    HEADER = "HEADER"
    BODY = "BODY"
    COOKIE = "COOKIE"
    MATRIX = "MATRIX"


class ValidationOverallStatus(str, Enum):
    """Overall validation status."""
    PASS = "PASS"
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"
    FAIL = "FAIL"


class ScraperType(str, Enum):
    """Type of scraper to generate."""
    WEBSITE_PARSER = "WEBSITE_PARSER"
    HTTP_COLLECTOR = "HTTP_COLLECTOR"
    API_CLIENT = "API_CLIENT"
    FTP_CLIENT = "FTP_CLIENT"


class ComplexityLevel(str, Enum):
    """Complexity level of scraper implementation."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# ============================================================================
# Parameter and Endpoint Types
# ============================================================================

class Parameter(BaseModel):
    """API parameter specification with comprehensive metadata.

    Enhanced for MISO operations discovery to support detailed parameter analysis.
    """
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Data type: string, integer, number, boolean, array, object, date, datetime")
    required: bool = Field(..., description="Whether parameter is required")
    description: str = Field("", description="Parameter description")

    # NEW: Enhanced metadata for scraper generation (Phase 1.5 parameter analysis)
    location: Optional[str] = Field(None, description="Parameter location: query, path, header, body")
    format: Optional[str] = Field(None, description="Format pattern: YYYY-MM-DD, ISO-8601, unix_timestamp, etc.")
    example: Optional[str] = Field(None, description="Example value: '2024-01-15' or '2024-01-15T00:00:00Z'")
    default: Optional[Any] = Field(None, description="Default value if not provided")
    enum: Optional[List[str]] = Field(None, description="Allowed values for enum types")
    minimum: Optional[float] = Field(None, description="Minimum value for numbers")
    maximum: Optional[float] = Field(None, description="Maximum value for numbers")
    pattern: Optional[str] = Field(None, description="Regex pattern for validation")


class EndpointAnalysis(BaseModel):
    """Individual endpoint analysis from Phase 0."""
    endpoint_url: str
    path: str
    method: HTTPMethod
    parameters: list[Parameter] = Field(default_factory=list)
    response_format: ResponseFormat
    description: str
    auth_required: bool


class Endpoint(BaseModel):
    """Basic endpoint specification."""
    path: str
    method: HTTPMethod = Field(description="HTTP method: GET, POST, PUT, PATCH, DELETE")
    parameters: list[Parameter] = Field(default_factory=list)
    auth_required: bool
    response_format: ResponseFormat


class EndpointDetails(BaseModel):
    """Detailed endpoint specification with validation status."""
    endpoint_id: str
    name: str
    type: str
    base_url: str
    path: str
    method: HTTPMethod
    parameters: dict[str, Parameter]
    authentication: dict[str, str]
    response_format: ResponseFormat
    validation_status: ValidationStatus
    accessible: bool
    last_tested: str
    notes: str


# ============================================================================
# Phase 0: Detection Types
# ============================================================================

class Phase0Detection(BaseModel):
    """Results from Phase 0: Data source type detection."""
    detected_type: DataSourceType
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0",
        ge=0.0,
        le=1.0
    )
    indicators: list[str] = Field(default_factory=list)
    discovered_api_calls: list[str] = Field(
        default_factory=list,
        description="List of discovered API endpoints or calls"
    )
    discovered_endpoint_urls: list[str] = Field(
        default_factory=list,
        description="List of endpoint URLs to analyze individually"
    )
    discovered_data_links: list[str] = Field(
        default_factory=list,
        description="Direct download links to data files (.csv, .json, .xml, etc.) for non-API sources"
    )
    auth_method: str = Field(description="Detected authentication method")
    base_url: str = Field(description="Base URL of the API")
    url: str
    fallback_strategy: Optional[str] = None


class Phase0IterativeAnalysis(BaseModel):
    """AI response during iterative Phase 0 discovery."""
    needs_more_pages: bool = Field(
        description="Whether AI needs to visit additional pages for complete discovery"
    )
    urls_to_visit: list[str] = Field(
        default_factory=list,
        description="Specific URLs that AI wants to visit next"
    )
    discovered_endpoint_urls: list[str] = Field(
        default_factory=list,
        description="All endpoint URLs discovered so far"
    )
    detected_type: DataSourceType = Field(
        description="Type of data source detected"
    )
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0",
        ge=0.0,
        le=1.0
    )
    reasoning: str = Field(
        description="AI's reasoning for its decisions"
    )
    indicators: list[str] = Field(
        default_factory=list,
        description="Evidence and indicators found"
    )
    auth_method: str = Field(
        description="Detected authentication method"
    )
    base_url: str = Field(
        description="Base URL of the API"
    )
    discovered_api_calls: list[str] = Field(
        default_factory=list,
        description="Network API calls discovered"
    )


class FilteredURLs(BaseModel):
    """AI-filtered URL categorization to separate API endpoints from navigation links."""
    api_endpoints: list[str] = Field(
        default_factory=list,
        description="URLs that are actual API endpoints"
    )
    navigation_links: list[str] = Field(
        default_factory=list,
        description="URLs that are navigation/page links (not API endpoints)"
    )
    reasoning: str = Field(
        description="Brief explanation of how URLs were categorized"
    )


# ============================================================================
# Phase 1: Documentation Types
# ============================================================================

class EndpointDiscovery(BaseModel):
    """Metadata about endpoint discovery process."""
    total_endpoints_found: int
    collapsible_sections_expanded: int
    extraction_method: str
    screenshot_taken: bool
    systematic_enumeration_completed: bool


class AuthClaims(BaseModel):
    """Authentication information extracted from documentation."""
    auth_section_found: bool
    signup_links: list[str] = Field(default_factory=list)
    api_key_mentioned: bool
    subscription_mentioned: bool
    auth_header_examples: list[str] = Field(default_factory=list)
    conclusion: str


class EndpointSpec(BaseModel):
    """Endpoint specification from documentation."""
    endpoint_id: str
    path: str = Field(
        description="Full URL to the endpoint including protocol and domain "
                   "(e.g., https://api.example.com/v1/data). "
                   "Must NOT be a relative path."
    )
    method: HTTPMethod
    description: str
    parameters: list[Parameter] = Field(default_factory=list)
    response_format: ResponseFormat
    authentication_mentioned: bool

    @field_validator('path')
    @classmethod
    def validate_full_url(cls, v: str) -> str:
        """Validate that path is a full URL, not a relative path.

        This validator ensures the LLM follows instructions to provide full URLs.
        If a relative path is provided, it raises a clear validation error.

        Args:
            v: The path value to validate

        Returns:
            The validated path (unchanged if valid)

        Raises:
            ValueError: If path is not a full URL with protocol
        """
        if not v.startswith(('http://', 'https://')):
            raise ValueError(
                f"Endpoint path must be a full URL starting with http:// or https://, "
                f"got relative path: {v}. "
                f"This usually means the LLM extracted paths from documentation instead of "
                f"using the discovered URLs provided in the prompt."
            )
        return v


class DataInventory(BaseModel):
    """Inventory of available data files."""
    total_files: int
    file_formats: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    download_links: list[dict[str, str]] = Field(default_factory=list)


class AccessRequirements(BaseModel):
    """Requirements for accessing the data source."""
    authentication: str
    subscription_required: bool
    rate_limits: str


class Phase1Documentation(BaseModel):
    """Results from Phase 1: Documentation analysis."""
    source: str
    timestamp: str
    url: str
    source_type: str
    endpoints: list[EndpointSpec] = Field(default_factory=list)
    notes: str
    portal_type: PortalType = PortalType.API_DOCS
    auth_claims: Optional[AuthClaims] = None
    data_inventory: Optional[DataInventory] = None
    access_requirements: Optional[AccessRequirements] = None


# ============================================================================
# Phase 2: Testing Types
# ============================================================================

class TestResult(BaseModel):
    """Result of endpoint testing."""
    http_status: int
    response_snippet: str
    auth_keywords_found: list[str] = Field(default_factory=list)
    full_output_file: str


class TestConclusion(BaseModel):
    """Conclusion from endpoint testing."""
    auth_required: bool
    evidence: str
    likely_auth_method: AuthenticationMethod
    confidence: ConfidenceLevel


class DownloadTest(BaseModel):
    """Result of download link testing."""
    url: str
    http_status: int
    content_type: str = ""
    content_length: str = ""
    accessible: bool
    requires_auth: bool


class AuthenticationFindings(BaseModel):
    """Authentication findings from testing."""
    auth_required: bool
    evidence: str
    cookie_required: bool
    redirect_to_login: bool
    auth_headers_found: list[str] = Field(default_factory=list)


class FileMetadataVerification(BaseModel):
    """Verification of file metadata."""
    file_sizes_match_claims: str
    content_types_match: bool
    last_modified_dates_available: bool


class Phase2Tests(BaseModel):
    """Results from Phase 2: Live testing."""
    source: str
    timestamp: str
    source_type: str
    portal_type: PortalType = PortalType.API_DOCS
    files_saved: list[str] = Field(default_factory=list)
    test_results: dict[str, TestResult] = Field(default_factory=dict)
    download_tests: dict[str, list[DownloadTest]] = Field(default_factory=dict)
    conclusion: Optional[TestConclusion] = None
    authentication_findings: Optional[AuthenticationFindings] = None


# ============================================================================
# Phase 3: Validated Spec Types
# ============================================================================

class ValidationSummary(BaseModel):
    """Summary of validation process."""
    phases_completed: list[str]
    documentation_review: str
    live_api_testing: str
    discrepancies_found: int
    confidence_score: float = Field(
        description="Confidence score between 0.0 and 1.0",
        ge=0.0,
        le=1.0
    )
    confidence_level: ConfidenceLevel
    recommendation: str


class AuthenticationSpec(BaseModel):
    """Authentication specification for the data source."""
    required: bool
    method: AuthenticationMethod
    evidence: str
    notes: str


class Discrepancy(BaseModel):
    """Discrepancy found during validation."""
    type: str
    severity: str
    resolution: str


class Phase3Insights(BaseModel):
    """Lightweight LLM-generated insights for Phase 3.

    This model is used for the optimized Phase 3 approach where we ask
    the LLM only for qualitative insights, not to recalculate stats or
    regenerate all endpoint data.
    """
    summary: str = Field(
        description="2-3 sentence executive summary about the API"
    )
    key_findings: list[str] = Field(
        description="Bullet points of key findings from the analysis"
    )
    recommendations: list[str] = Field(
        description="Actionable recommendations for the user"
    )
    scraper_challenges: list[str] = Field(
        description="Main challenges for scraper implementation"
    )


class ExecutiveSummary(BaseModel):
    """Executive summary of analysis results."""
    total_endpoints_discovered: int
    accessible_endpoints: int
    success_rate: str
    primary_formats: list[str]
    authentication_required: bool
    estimated_scraper_complexity: ComplexityLevel


class DataCatalog(BaseModel):
    """Catalog of available data."""
    total_files_discovered: int
    total_endpoints: int


class ScraperRecommendation(BaseModel):
    """Recommendation for scraper implementation."""
    type: ScraperType
    complexity: ComplexityLevel
    estimated_effort: str


class CollationMetadata(BaseModel):
    """Metadata about the collation process."""
    collation_timestamp: str
    runs_compared: int


class CollationAnalysis(BaseModel):
    """Analysis from collation of multiple runs."""
    run_comparison: dict[str, str]
    improvements_from_run2: list[str]


class ValidatedSpec(BaseModel):
    """Final validated specification for scraper generation."""
    source: str
    source_type: str
    datasource: str = Field(
        description="Snake_case datasource identifier (e.g., 'example_service')"
    )
    dataset: str = Field(
        description="Snake_case dataset identifier (e.g., 'data', 'metrics')"
    )
    timestamp: str
    url: str
    executive_summary: ExecutiveSummary
    validation_summary: ValidationSummary
    scraper_recommendation: ScraperRecommendation
    endpoints: list[EndpointDetails]
    discovered_data_links: list[str] = Field(
        default_factory=list,
        description="Direct download links to data files for non-API sources"
    )
    discrepancies: list[Discrepancy]
    authentication: Optional[AuthenticationSpec] = None
    data_catalog: Optional[DataCatalog] = None
    collation_analysis: Optional[CollationAnalysis] = None


# ============================================================================
# Validation Report Types
# ============================================================================

class ValidationResult(BaseModel):
    """Result of validation checks."""
    confidence: float = Field(
        description="Confidence in the phase result (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    identified_gaps: list[str] = Field(
        default_factory=list,
        description="List of gaps or issues found"
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommendations for improvement"
    )
    validation_notes: str = Field(description="Detailed validation notes")


class PhaseValidation(BaseModel):
    """Validation results for a single phase."""
    status: ValidationOverallStatus
    issues: list[dict[str, str]] = Field(default_factory=list)
    notes: str


class CriticalGap(BaseModel):
    """Critical gap identified during validation."""
    gap_type: str
    description: str
    action_required: str
    discovered: Optional[int] = None
    documented: Optional[int] = None
    missing: Optional[int] = None


class ValidationReport(BaseModel):
    """Comprehensive validation report."""
    validation_timestamp: str
    input_file: str
    overall_status: ValidationOverallStatus
    overall_confidence: float = Field(
        description="Overall confidence between 0.0 and 1.0",
        ge=0.0,
        le=1.0
    )
    phase_validations: dict[str, PhaseValidation] = Field(default_factory=dict)
    critical_gaps: list[CriticalGap] = Field(default_factory=list)
    recommendations_for_second_pass: list[str] = Field(default_factory=list)
    validation_summary: str


# ============================================================================
# Collation Report Types
# ============================================================================

class CollationResult(BaseModel):
    """Result of collating multiple analysis runs."""
    collation_complete: bool
    final_spec_path: str
    final_confidence_score: float = Field(
        description="Final confidence score between 0.0 and 1.0",
        ge=0.0,
        le=1.0
    )
    total_endpoints: int
    endpoints_run1: int
    endpoints_run2: int
    improvements_count: int
    discrepancies_resolved: int
    consistency_rate: str
    ready_for_scraper_generation: bool


# ============================================================================
# Vision Portal Analysis Types
# ============================================================================

class VisionPortalAnalysisResult(BaseModel):
    """Generic vision-based portal analysis result."""
    is_api_documentation: bool = Field(
        description="Is this API documentation? true/false"
    )
    confidence: float = Field(
        description="Confidence 0.0-1.0 in the classification",
        ge=0.0,
        le=1.0
    )
    visual_description: str = Field(
        description="Describe what you see on this page in 2-3 sentences"
    )
    operations_presentation: str = Field(
        description="How are operations/endpoints presented?"
    )
    operations_location: str = Field(
        description="Where on the page are operations located?"
    )
    operation_indicators: list[str] = Field(
        default_factory=list,
        description="What visual indicators show something is an API operation?"
    )
    operations_visible: list[str] = Field(
        default_factory=list,
        description="List the actual operation names/endpoints visible"
    )
    estimated_total_operations: int = Field(
        description="Approximately how many total operations exist?"
    )
    extraction_guidance: str = Field(
        description="How to extract ALL operations from this page"
    )
    url_pattern: Optional[str] = Field(
        default=None,
        description="URL pattern for operations"
    )
    uses_hash_routing: bool = Field(
        default=False,
        description="Do operation URLs use hash routing?"
    )
    uses_query_params: bool = Field(
        default=False,
        description="Do operation URLs use query parameters?"
    )
    requires_interaction: bool = Field(
        default=False,
        description="Does this page need clicking/expanding?"
    )
    interaction_type: Optional[str] = Field(
        default=None,
        description="Type of interaction needed"
    )
    is_spa: bool = Field(
        default=False,
        description="Is this a Single Page Application?"
    )
    has_javascript_state: bool = Field(
        default=False,
        description="Are operations stored in JavaScript state?"
    )
    recommended_selectors: list[str] = Field(
        default_factory=list,
        description="CSS selectors for operation elements"
    )
