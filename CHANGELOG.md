# Changelog

All notable changes to the Scraper Development Agent plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.14.0] - 2025-12-16

### Added
- **NEW AGENT**: Endpoint QA Validator (endpoint-qa-validator.md v1.0.0)
  - Live endpoint testing with curl (HEAD requests with authentication support)
  - Tests ALL discovered endpoints for existence (200/401/403 = keep, 404 = remove)
  - Automatic hallucination detection and removal
  - 1 second delay between tests to respect rate limits
  - Generates comprehensive QA report with curl test artifacts
  - User confirmation required if all endpoints fail validation
  - Runs after BA Collator, before presenting results to user
- **Source-First Constraint** in BA Agent endpoint enumeration
  - Explicit knowledge limitation to documentation page only
  - Evidence requirements for each endpoint (doc_quote, extraction_method, doc_section)
  - Self-audit questions before saving phase1_documentation.json
- **Comprehensive Prohibition List** with specific hallucination patterns to avoid
- **Hallucination Warning Signs** checklist for agent self-awareness

### Fixed
- **CRITICAL**: BA Agent (v2.3.0) enhanced context preservation
  - Strengthened instructions to stay in agent context when asking questions
  - Added VERIFICATION step before using AskUserQuestion
  - Explicit FORBIDDEN BEHAVIORS list to prevent context loss
- **CRITICAL**: BA Agent file persistence improvements
  - Removed user verification messages (agent verifies with Read tool)
  - Added clear success/retry/failure logic in file writing checklist
  - Agent now tells user final file location after verification
- **CRITICAL**: Endpoint hallucination prevention with QA validator
  - Independent verification layer catches hallucinated endpoints
  - Live curl testing provides definitive proof of endpoint existence
  - Pattern detection flags suspicious endpoint naming conventions
  - Rapid falsification testing: "guilty until proven innocent" approach

### Changed
- BA Agent workflow now includes Step 5: QA Validator invocation
  - Old workflow: Run 1 → Validator → Run 2 → Collator → Present Results
  - New workflow: Run 1 → Validator → Run 2 → Collator → **QA Validator** → Present Results
- BA Agent version: 2.2.0 → 2.3.0
- Plugin version: 1.13.0 → 1.14.0
- Final results now include QA validation metrics (verified count, removed count, flagged count)

## [1.13.0] - 2025-12-16

### Fixed
- **CRITICAL**: BA Agent (v2.2.0) now ACTUALLY writes files (not just claims to)
  - Replaced JavaScript pseudo-code with explicit "ACTUALLY USE THE TOOL" instructions
  - Added "YOU ARE EXECUTING IN USER'S WORKING DIRECTORY" awareness
  - Added anti-hallucination enforcement checklist before claiming files created
  - Agent must verify with Read tool and check results before claiming success
- **CRITICAL**: BA Agent hallucination prevention - NO making up endpoints
  - Added absolute prohibition on inventing/guessing/extrapolating endpoints
  - Must ONLY document endpoints explicitly shown in documentation
  - Added verification questions: "Did I see this exact endpoint in docs?"
  - If uncertain, DO NOT include endpoint

### Changed
- File Writing section: Removed pseudo-code, added explicit tool call requirements
- Endpoint Enumeration section: Added "ABSOLUTE PROHIBITION: NO HALLUCINATION" with verification

## [1.12.0] - 2025-12-16

### Fixed
- **CRITICAL**: BA Agent (v2.1.0) context loss when asking questions
  - Agent now stays in context when using AskUserQuestion
  - Questions are checkpoints, not exit points
  - Agent continues analysis immediately after receiving user's answer
- **CRITICAL**: BA Agent files not being created
  - Mandatory Read() verification after every Write()
  - Must create datasource_analysis/ directory first
  - Cannot proceed to next phase if file write fails
- **CRITICAL**: BA Agent incomplete endpoint enumeration
  - Must expand ALL collapsible sections before extraction
  - Must take screenshot proof of expanded state
  - Must extract ALL endpoints systematically (not samples or guesses)
  - Validation checklist required before proceeding to Phase 2
  - Prohibition on guessing endpoints without documentation evidence

### Added
- Agent Context & Question Handling section with explicit instructions
- File Writing & Verification section with mandatory verification process
- Systematic Endpoint Enumeration with expand-extract-validate workflow
- Comprehensive validation checklists for completeness verification

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
