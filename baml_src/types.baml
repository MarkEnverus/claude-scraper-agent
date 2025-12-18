// BAML Type Definitions for Scraper Agent Architecture
// Generated from ba-enhanced.md, ba-validator.md, ba-collator.md specifications

// ============================================================================
// Enums
// ============================================================================

enum DataSourceType {
  API
  FTP
  WEBSITE
  EMAIL
}

enum HTTPMethod {
  GET
  POST
  PUT
  DELETE
  PATCH
  HEAD
  OPTIONS
}

enum AuthenticationMethod {
  NONE
  API_KEY
  BEARER_TOKEN
  OAUTH
  BASIC_AUTH
  COOKIE
  UNKNOWN
}

enum ValidationStatus {
  TESTED_200_OK
  TESTED_401_UNAUTHORIZED
  TESTED_403_FORBIDDEN
  TESTED_404_NOT_FOUND
  NOT_TESTED
}

enum ExtractionQuality {
  COMPREHENSIVE
  PARTIAL
  LIMITED
  MISSING
}

enum ConfidenceLevel {
  HIGH
  MEDIUM
  LOW
}

enum DocQuality {
  EXCELLENT
  HIGH
  MEDIUM
  LOW
  POOR
}

enum PortalType {
  STATIC
  SPA
  API_DOCS
  CUSTOM_FRAMEWORK
}

enum ResponseFormat {
  JSON
  XML
  CSV
  HTML
  BINARY
}

enum ParameterLocation {
  PATH
  QUERY
  HEADER
  BODY
  COOKIE
  MATRIX
}

enum ValidationOverallStatus {
  PASS
  NEEDS_IMPROVEMENT
  FAIL
}

enum ScraperType {
  WEBSITE_PARSER
  HTTP_COLLECTOR
  API_CLIENT
  FTP_CLIENT
}

enum ComplexityLevel {
  LOW
  MEDIUM
  HIGH
}

// ============================================================================
// Parameter and Endpoint Types
// ============================================================================

class Parameter {
  name string
  type string
  required bool
  description string
  example string?
}

class Endpoint {
  path string
  method HTTPMethod @description("HTTP method: GET, POST, PUT, PATCH, DELETE")
  parameters Parameter[]
  auth_required bool
  response_format ResponseFormat
}

class EndpointDetails {
  endpoint_id string
  name string
  type string
  base_url string
  path string
  method HTTPMethod
  parameters map<string, Parameter>
  authentication map<string, string>
  response_format ResponseFormat
  data_structure map<string, string>?
  sample_files map<string, string>[]?
  validation_status ValidationStatus
  accessible bool
  last_tested string
  file_count int?
  update_frequency string?
  notes string
  // Cross-run validation fields
  validation_consistency string?
  tested_in_run1 bool?
  tested_in_run2 bool?
}

// ============================================================================
// Phase 0: Detection Types
// ============================================================================

class Phase0Detection {
  detected_type DataSourceType
  confidence float @description("Confidence score between 0.0 and 1.0 (validated: must be >= 0.0 and <= 1.0)")
  indicators string[]
  discovered_api_calls string[] @description("List of discovered API endpoints or calls")
  endpoints Endpoint[]
  url string
  fallback_strategy string?
}

// ============================================================================
// Phase 1: Documentation Types
// ============================================================================

class EndpointDiscovery {
  total_endpoints_found int
  collapsible_sections_expanded int
  extraction_method string
  screenshot_taken bool
  systematic_enumeration_completed bool
}

class AuthClaims {
  auth_section_found bool
  auth_section_text string?
  signup_links string[]
  api_key_mentioned bool
  subscription_mentioned bool
  auth_header_examples string[]
  conclusion string
}

class EndpointSpec {
  endpoint_id string
  path string
  method HTTPMethod
  description string
  parameters Parameter[]
  response_format ResponseFormat
  authentication_mentioned bool
}

class DataInventory {
  total_files int
  file_formats string[]
  categories string[]
  download_links map<string, string>[]
}

class AccessRequirements {
  authentication string
  registration map<string, string>?
  terms_of_use_url string?
  subscription_required bool
  rate_limits string
}

class Phase1Documentation {
  source string
  timestamp string
  url string
  endpoint_discovery EndpointDiscovery?
  auth_claims AuthClaims?
  endpoints EndpointSpec[]
  doc_quality DocQuality
  notes string
  // For website portals
  source_type string?
  data_inventory DataInventory?
  access_requirements AccessRequirements?
  update_frequency string?
  portal_type PortalType?
  extraction_quality ExtractionQuality?
}

// ============================================================================
// Phase 2: Testing Types
// ============================================================================

class TestResult {
  http_status int
  response_snippet string
  auth_keywords_found string[]
  full_output_file string
}

class TestConclusion {
  auth_required bool
  evidence string
  likely_auth_method AuthenticationMethod
  likely_header_name string?
  confidence ConfidenceLevel
}

class DownloadTest {
  url string
  http_status int
  content_type string?
  content_length string?
  last_modified string?
  accessible bool
  requires_auth bool
  redirect_to_login bool?
}

class AuthenticationFindings {
  auth_required bool
  evidence string
  cookie_required bool
  redirect_to_login bool
  auth_headers_found string[]
}

class FileMetadataVerification {
  file_sizes_match_claims string
  content_types_match bool
  last_modified_dates_available bool
}

class Phase2Tests {
  source string
  timestamp string
  endpoint_tested string?
  test_results map<string, TestResult>?
  conclusion TestConclusion?
  files_saved string[]
  // For website portals
  source_type string?
  download_tests map<string, DownloadTest[]>?
  authentication_findings AuthenticationFindings?
  file_metadata_verification FileMetadataVerification?
  portal_type PortalType?
  portal_conclusion string? @description("Summary of portal behavior and data access method (only for website portals)")
}

// ============================================================================
// Phase 3: Validated Spec Types
// ============================================================================

class ValidationSummary {
  phases_completed string[]
  documentation_review string
  live_api_testing string
  discrepancies_found int
  confidence_score float @description("Confidence score between 0.0 and 1.0 (validated: must be >= 0.0 and <= 1.0)")
  confidence_level ConfidenceLevel
  recommendation string
  // Additional fields
  collation_complete bool?
  runs_analyzed int?
  final_confidence_score float? @description("Final confidence between 0.0 and 1.0 (validated: must be >= 0.0 and <= 1.0)")
  run1_confidence float? @description("Run 1 confidence between 0.0 and 1.0 (validated: must be >= 0.0 and <= 1.0)")
  run2_confidence float? @description("Run 2 confidence between 0.0 and 1.0 (validated: must be >= 0.0 and <= 1.0)")
  confidence_consistency string?
  validator_status string?
  discrepancies_resolved int?
}

class AuthenticationSpec {
  required bool
  method AuthenticationMethod
  header_name string?
  evidence string
  registration_url string?
  notes string
  // Additional fields
  authentication_consistency bool?
  authentication_notes string?
  authentication_details string?
}

class Discrepancy {
  type string
  documentation_said string?
  api_testing_showed string?
  severity string
  resolution string
  // For website portals
  area string?
  phase1_claim string?
  phase2_finding string?
}

class ExecutiveSummary {
  total_endpoints_discovered int
  total_datasets int?
  total_files int?
  accessible_endpoints int
  protected_endpoints int?
  broken_endpoints int?
  success_rate string
  primary_formats string[]
  authentication_required bool
  estimated_scraper_complexity ComplexityLevel
  // Collation fields
  improvements_from_run1 map<string, string>?
}

class DataCatalog {
  total_files_discovered int
  total_endpoints int
  file_formats map<string, int>
  data_categories string[]
  downloadable_files map<string, string>[]
}

class ScraperRecommendation {
  type ScraperType
  confidence ConfidenceLevel?
  rationale string[]
  complexity ComplexityLevel
  estimated_effort string
  key_challenges string[]
}

class CollationMetadata {
  collation_timestamp string
  run1_timestamp string
  run2_timestamp string
  validation_report string
  runs_compared int
  collation_agent string
}

class CollationAnalysis {
  run_comparison map<string, string>
  improvements_from_run2 string[]
  discrepancies_resolved map<string, string>[]
  consistency_checks map<string, string>
}

class ValidatedSpec {
  source string
  source_type string
  timestamp string
  url string
  executive_summary ExecutiveSummary
  validation_summary ValidationSummary
  authentication AuthenticationSpec?
  access_requirements AccessRequirements?
  endpoints EndpointDetails[]
  data_catalog DataCatalog?
  scraper_recommendation ScraperRecommendation
  discrepancies Discrepancy[]
  artifacts_generated string[]
  next_steps string[]
  // Collation-specific fields
  collation_metadata CollationMetadata?
  collation_analysis CollationAnalysis?
}

// ============================================================================
// Validation Report Types (from ba-validator.md)
// ============================================================================

class ValidationResult {
  confidence float @description("Confidence in the phase result (0.0-1.0)")
  identified_gaps string[] @description("List of gaps or issues found")
  recommendations string[] @description("Recommendations for improvement")
  validation_notes string @description("Detailed validation notes")
}

class PhaseValidation {
  status ValidationOverallStatus
  issues map<string, string>[]
  notes string
}

class CriticalGap {
  gap_type string
  description string
  action_required string
  // Additional fields
  discovered int?
  documented int?
  missing int?
}

class ValidationReport {
  validation_timestamp string
  input_file string
  overall_status ValidationOverallStatus
  overall_confidence float @description("Overall confidence between 0.0 and 1.0 (validated: must be >= 0.0 and <= 1.0)")
  phase_validations map<string, PhaseValidation>
  critical_gaps CriticalGap[]
  recommendations_for_second_pass string[]
  validation_summary string
}

// ============================================================================
// Collation Report Types (from ba-collator.md)
// ============================================================================

class CollationResult {
  collation_complete bool
  final_spec_path string
  final_confidence_score float @description("Final confidence score between 0.0 and 1.0 (validated: must be >= 0.0 and <= 1.0)")
  total_endpoints int
  endpoints_run1 int
  endpoints_run2 int
  improvements_count int
  discrepancies_resolved int
  consistency_rate string
  ready_for_scraper_generation bool
}
