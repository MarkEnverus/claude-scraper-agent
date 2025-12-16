# Changelog

All notable changes to the Scraper Development Agent plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.11.0] - 2025-12-16

### Fixed
- **CRITICAL**: BA Agent now actually persists specifications to JSON files
  - Added explicit Write tool call instructions at every phase save point
  - Added mandatory Read verification immediately after every Write
  - Added comprehensive verification checklist before presenting results
  - Strengthened anti-hallucination rules to forbid claiming saves without tool use
  - Root cause: Agent had pseudocode examples instead of executable tool calls

### Added
- **Comprehensive Scraper Generator Details** in BA Agent specifications:
  - Complete authentication details: registration steps, credential locations, expiration policies
  - Authentication implementation: exact header names, value formats, session management
  - Rate limiting: requests per second/minute/hour/day with retry strategies
  - Parameter schemas: types, validation rules, examples, defaults for all parameters
  - Error handling: detailed specifications for all HTTP status codes (400, 401, 403, 404, 429, 500+)
  - Retry strategies: backoff algorithms, timing, which codes to retry
  - File patterns: naming conventions, directory structures, update schedules
  - Web scraping specs: CSS selectors, wait times, pagination, dynamic content handling
  - Login flows: step-by-step with selectors, success/failure indicators
  - Data schemas: complete field types, descriptions, nullability, examples
  - Example responses: full actual responses for reference
- Mandatory verification checklist for BA Agent (12-point checklist before saving spec)
- File persistence verification section with ls and du commands
- Directory creation at Phase 0 (`mkdir -p datasource_analysis`)

### Changed
- BA Agent endpoint specifications now include 12 mandatory sections
- Enhanced anti-hallucination enforcement for file persistence
- Updated Phase 0, 1, 2, and 3 save instructions with explicit tool calls
- Improved scraper generator readiness with implementation-ready details

### Documentation
- Added comprehensive "What to Include in Each Endpoint Specification" section
- Added Phase 3 enforcement rules with forbidden/required behaviors
- Added explicit tool call patterns for all phase save operations
- Documented verification pattern: Write → Read → Verify → Proceed

## [1.10.0] - 2025-12-11

### Changed
- Major improvements to scraper-updater agent for monorepo support
- Enhanced version tracking capabilities

## [1.9.0] - 2025-12-08

### Added
- Refactored S3 to reusable module
- Added version CLI command
- Normalized CLIs across all components

## [1.6.0] - 2025-12-05

### Changed
- Major refactor to generator-based regeneration
- All 4 generator agents refactored with __main__.py + moderate validation

## [1.5.0] - 2025-12-04

### Added
- Date defaulting to website-parser-generator for consistency
- Optional auth/dates support
- Integration tests for generators

## [1.0.0] - 2025-11-20

### Added
- Initial release of Scraper Development Agent plugin
- Support for HTTP/REST APIs, website parsing, FTP/SFTP, and email attachments
- Type-safe code generation with mypy and ruff compliance
- Automatic quality checking
- Tabbed question interface for better UX
- Version tracking
- Scraper maintenance tools (/fix-scraper, /update-scraper)
- Self-contained Kafka notification support
- Optional config file pre-configuration
