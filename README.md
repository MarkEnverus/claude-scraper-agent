# Claude Scraper Agent v2.0.0

**Type-safe scraper generation with Python CLI, LangGraph, and BAML**

Generate, fix, and update production-ready Python scrapers for HTTP APIs, FTP, Email, and Websites using AI-powered analysis and hybrid template generation.

**Latest Updates (v2.0.0):**
- ✅ **Migrated to Python CLI** - Clean architecture with Click, LangGraph, Pydantic
- ✅ **Hybrid Generation** - Jinja2 templates + AI for complex logic
- ✅ **471 Tests Passing** - 85%+ coverage with comprehensive test suite
- ✅ **CLI Utilities** - Retry logic, error handling, progress bars
- ✅ **Enhanced Documentation** - Complete guides and examples

**⚠️ Migration Note:** If you're using the old plugin-based system (v1.x), see [MIGRATION_SCRAPER_AGENTS.md](MIGRATION_SCRAPER_AGENTS.md) for upgrade instructions.

## Overview

**Claude Scraper Agent** is a comprehensive CLI tool for generating, maintaining, and updating production-ready data scrapers. It combines:

- **🎯 Smart Analysis**: AI-powered data source analysis with 4-phase validation
- **🔧 Hybrid Generation**: Jinja2 templates + AI for complex logic
- **🏗️ Clean Architecture**: Pydantic types, LangGraph orchestration, modular design
- **✅ Quality First**: 519 tests, 85%+ coverage, mypy + ruff validation
- **🔄 Maintenance Tools**: Fix and update existing scrapers automatically
- **📊 Rich CLI**: Interactive workflows with progress indication

### Key Components

- **CLI (`claude_scraper/cli/`)**: Click-based commands (analyze, generate, fix, update)
- **Types (`claude_scraper/types/`)**: Pydantic type system with validation
- **Generators (`claude_scraper/generators/`)**: Hybrid template + AI code generation
- **Templates (`claude_scraper/templates/`)**: Jinja2 templates for scrapers
- **Orchestration (`claude_scraper/orchestration/`)**: LangGraph pipelines
- **Fixers (`claude_scraper/fixers/`)**: Diagnosis and repair tools
- **Infrastructure**: Base classes for collection framework

## Project Structure

```
claude_scraper_agent/
├── claude_scraper/          # Main package
│   ├── cli/                 # Click-based CLI
│   │   ├── main.py         # Commands: analyze, generate, fix, update
│   │   ├── config.py       # Configuration management
│   │   └── utils.py        # Error handling, retry logic
│   ├── types/              # Pydantic type system
│   │   ├── base.py         # Base models
│   │   ├── enums.py        # Enums with display names
│   │   ├── scraper_spec.py # Method-specific configs
│   │   └── validators.py   # Business logic validators
│   ├── generators/         # Code generation
│   │   ├── hybrid_generator.py
│   │   ├── template_renderer.py
│   │   └── variable_transformer.py
│   ├── templates/          # Jinja2 templates
│   │   ├── scraper_main.py.j2
│   │   ├── scraper_tests.py.j2
│   │   └── scraper_readme.md.j2
│   ├── orchestration/      # LangGraph pipelines
│   │   ├── pipeline.py
│   │   └── nodes.py
│   ├── fixers/             # Maintenance tools
│   │   ├── fixer.py        # Diagnosis and repair
│   │   └── updater.py      # Version migration
│   └── llm/                # LLM providers (Bedrock/Anthropic)
├── infrastructure/         # Base collection framework
│   ├── collection_framework.py
│   ├── hash_registry.py
│   ├── logging_json.py
│   └── kafka_utils.py
├── tests/                  # 519 tests (85%+ coverage)
├── baml_src/              # BAML type definitions
└── docs/                   # Documentation
```

## Installation

### Prerequisites

- Python 3.10+
- `uv` package manager (recommended) or `pip`
- AWS credentials (for Bedrock) or Anthropic API key

### Install with uv (Recommended)

```bash
# Clone repository
git clone https://github.com/your-org/claude-scraper-agent.git
cd claude_scraper_agent

# Create virtual environment and install
uv sync

# Verify installation
uv run claude-scraper --help
```

### Install with pip

```bash
# Clone repository
git clone https://github.com/your-org/claude-scraper-agent.git
cd claude_scraper_agent

# Install in development mode
pip install -e ".[dev]"

# Verify installation
claude-scraper --help
```

### Environment Setup

```bash
# For Bedrock (default provider)
export AWS_ACCESS_KEY_ID=<your-key>
export AWS_SECRET_ACCESS_KEY=<your-secret>
export AWS_DEFAULT_REGION=us-west-2

# For Anthropic provider
export ANTHROPIC_API_KEY=<your-api-key>

# Optional: Custom output directory
export SCRAPER_OUTPUT_DIR=custom/output/path
```

### Verify Installation

```bash
# Check version
claude-scraper --version

# Show available commands
claude-scraper --help

# Test analyze command
claude-scraper analyze --help
```

## Usage

### Quick Reference

```bash
# Analyze a data source
claude-scraper analyze --url https://api.example.com/docs

# Generate scraper from analysis
claude-scraper generate --ba-spec validated_datasource_spec.json

# Fix an existing scraper
claude-scraper fix

# Update scrapers to new infrastructure
claude-scraper update --mode scan
```

### 1. Analyze a Data Source

Analyze API documentation or data sources to generate validated specifications:

```bash
# Basic usage
claude-scraper analyze --url https://api.misoenergy.org/docs

# Use Anthropic provider
claude-scraper analyze --url https://api.example.com --provider anthropic

# Custom output directory
claude-scraper analyze --url https://api.example.com --output-dir custom/path

# Enable debug logging
claude-scraper analyze --url https://api.example.com --debug
```

**Output:** `datasource_analysis/validated_datasource_spec.json`

### 2. Generate a Scraper

Generate production-ready scrapers from BA specifications or URLs:

```bash
# From BA spec (after analyze)
claude-scraper generate --ba-spec validated_datasource_spec.json

# From URL (runs analysis first, then generates)
claude-scraper generate --url https://api.example.com/docs

# Custom output directory
claude-scraper generate --ba-spec spec.json --output-dir custom/scrapers

# With debug logging
claude-scraper generate --ba-spec spec.json --debug
```

**Output:** Complete scraper with tests, fixtures, and documentation

### 3. Fix an Existing Scraper

Diagnose and repair issues in existing scrapers:

```bash
# Interactive mode - select from list
claude-scraper fix

# Fix specific scraper
claude-scraper fix --scraper sourcing/scraping/scraper_miso_http.py

# Custom scraper root
claude-scraper fix --scraper-root custom/path

# Skip validation
claude-scraper fix --no-validate

# Debug mode
claude-scraper fix --debug
```

**Interactive Workflow:**
1. Scans for scrapers in `sourcing/scraping/`
2. Prompts for scraper selection
3. Asks for problem description
4. Collects fix operations (OLD -> NEW format)
5. Applies fixes and updates timestamps
6. Runs QA validation

### 4. Update Scrapers to New Infrastructure

Migrate scrapers to the current infrastructure version (v1.6.0):

```bash
# Scan mode - report only
claude-scraper update --mode scan

# Auto mode - interactive updates
claude-scraper update --mode auto

# Non-interactive - update all
claude-scraper update --mode auto --non-interactive

# Custom scraper root
claude-scraper update --mode auto --scraper-root custom/path

# Skip validation
claude-scraper update --mode auto --no-validate

# Debug mode
claude-scraper update --mode scan --debug
```

**Update Process:**
1. Scans all scrapers for version info
2. Identifies outdated scrapers (< v1.6.0)
3. Detects generator agent for each scraper (4 methods)
4. Regenerates with current infrastructure
5. Runs QA validation

### Example: Complete Workflow

```bash
# Step 1: Analyze API documentation
$ claude-scraper analyze --url https://api.misoenergy.org/docs

Scraper Analysis Pipeline

Phase 0: Detection → 95% confidence (HTTP_REST_API)
Phase 1: Documentation → 10 endpoints found
Phase 2: Testing → 8/10 endpoints accessible
Phase 3: Validation → Cross-check complete

✓ Analysis complete!
Output: datasource_analysis/validated_datasource_spec.json

# Step 2: Generate scraper
$ claude-scraper generate --ba-spec datasource_analysis/validated_datasource_spec.json

Scraper Generation

Transform BA spec → Template variables
Render Jinja2 template → scraper_miso_energy_pricing_http.py
Generate AI code → Complex auth + validation
Validate Python syntax → PASSED
Generate tests → test_scraper_miso_energy_pricing.py

✓ Generation complete!

Generated files:
  - generated_scrapers/scraper_miso_energy_pricing_http.py
  - generated_scrapers/test_scraper_miso_energy_pricing.py
  - generated_scrapers/README.md
  - generated_scrapers/fixtures/sample_data.json
```

## Enhanced Business Analyst Agent

This plugin includes an enhanced business analyst agent that can extract API documentation from JavaScript-rendered documentation sites.

### Quick Start

```bash
# 1. Configure MCP Puppeteer (one-time setup)
echo '{
  "mcpServers": {
    "puppeteer": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-puppeteer"]
    }
  }
}' > ~/.claude/mcp.json

# 2. Restart Claude Code

# 3. Use the agent
/analyze-api https://data-exchange.misoenergy.org/api-details#api=pricing-api
```

### Features

- ✅ **Handles JavaScript-rendered sites** - Uses browser automation when needed
- ✅ **Falls back gracefully** - Tries WebFetch first for speed
- ✅ **Comprehensive analysis** - Extracts endpoints, auth, parameters, response formats
- ✅ **JIRA-ready output** - Provides complete developer specifications

### How It Works

1. **WebFetch first**: Fast extraction for static documentation
2. **Browser automation**: For single-page apps and JS-heavy sites
3. **Intelligent detection**: Automatically chooses the right approach
4. **Fallback option**: Guides users to copy/paste if browser tools unavailable

### Prerequisites

**For browser automation support** (optional but recommended):
- Node.js installed
- MCP Puppeteer server configured (see Quick Start above)

**Without browser automation**:
- Agent still works with WebFetch
- Will ask you to copy/paste content from JS-heavy sites
- Setup instructions provided when needed

### Example Usage

**Scenario 1: Modern API documentation portal**
```
/scraper-dev:analyze https://data-exchange.misoenergy.org/api-details#api=pricing-api

→ Python CLI analyzer launches
→ Botasaurus handles JavaScript rendering
→ Phase 0: Detects API type (95% confidence)
→ Phase 1: Extracts 10 endpoints with parameters
→ Phase 2: Tests endpoints (finds auth required)
→ Phase 3: Validates and cross-checks
→ Returns validated_datasource_spec.json
```

**Scenario 2: REST API with OpenAPI docs**
```
/scraper-dev:analyze https://api.example.com/docs

→ Python CLI analyzer launches
→ Botasaurus extracts full documentation
→ Phase 0: Discovers endpoints from OpenAPI spec
→ Phase 1: Documents all parameters and auth
→ Phase 2: Live tests confirm accessibility
→ Returns complete specification in 15-20 seconds
```

**Scenario 3: Type-safe results**
```
Every analysis produces:
→ datasource_analysis/validated_datasource_spec.json
→ Type-safe Pydantic models (BAML-generated)
→ Cross-validated against live testing
→ Discrepancies identified and resolved
→ Confidence scoring (0.0-1.0)
→ Scraper recommendation with complexity estimate
```

### Integration with Scraper Generator

Use the enhanced BA agent to analyze documentation, then create scrapers:

```
# Step 1: Analyze the API
/analyze-api https://data-exchange.misoenergy.org/api-details#api=pricing-api

# Step 2: BA agent provides detailed specification

# Step 3: Create scraper with that specification
/create-scraper
[Paste the specification from BA agent]
```

### MCP Puppeteer vs WebFetch

| Feature | WebFetch | MCP Puppeteer |
|---------|----------|---------------|
| Speed | ⚡ Fast (~1-2 sec) | 🐌 Slower (~5-10 sec) |
| JavaScript | ❌ No execution | ✅ Full JS execution |
| Static sites | ✅ Perfect | ⚠️ Overkill |
| SPA/React sites | ❌ Returns empty | ✅ Full content |
| Setup | ✅ Built-in | ⚠️ Requires Node.js |

The agent automatically chooses the best tool for each site.

## Architecture

### Redis Hash Registry

Replaces DynamoDB-based deduplication with Redis:

```python
# Key format: hash:{env}:{dgroup}:{sha256_hash}
hash:dev:nyiso_load_forecast:abc123...

# Automatic TTL (default 365 days)
# Environment namespacing (dev/staging/prod isolation)
```

### S3 Date Partitioning

```
s3://bucket/sourcing/{dgroup}/year={YYYY}/month={MM}/day={DD}/{filename}

Example:
s3://bucket/sourcing/nyiso_load_forecast/year=2025/month=01/day=20/load_forecast_20250120_14.json
```

**Note:** Files are stored in their original format (uncompressed) to preserve file integrity and enable direct access.

### JSON Structured Logging

```json
{
  "timestamp": "2025-01-20T14:30:05Z",
  "level": "INFO",
  "logger": "sourcing_app",
  "message": "Successfully collected",
  "module": "scraper_nyiso_load",
  "function": "run_collection",
  "candidate": "load_forecast_20250120_14.json",
  "hash": "abc123...",
  "s3_path": "s3://..."
}
```

## Configuration

### Optional: Scraper Configuration Files

You can pre-configure scrapers using `.scraper-dev.md` files in your mono-repo:

**Location:**
```
sourcing/scraping/{dataSource}/{dataSet}/.scraper-dev.md
```

**Example:**
```yaml
---
data_source: NYISO
data_type: load_forecast
collection_method: HTTP/REST API
api_base_url: https://api.nyiso.com/v1
api_endpoint: /load/hourly
---
```

**Benefits:**
- Agent automatically finds and uses config values
- Only prompts for missing information
- Supports multiple projects in mono-repo
- See `.scraper-dev.example.md` for full example

### Environment Variables

```bash
# Redis
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0

# S3
export S3_BUCKET=your-s3-bucket-name
export AWS_PROFILE=default  # or use IAM role

# Kafka (optional)
export KAFKA_CONNECTION_STRING="kafka://host:port/topic?security_protocol=SASL_PLAINTEXT&X_sasl_file=/path/to/creds"
# Or use environment variables for SASL
export SASL_USERNAME=your_username
export SASL_PASSWORD=your_password

# Source-specific API keys
export NYISO_API_KEY=your_key_here
export IBM_API_KEY=your_key_here
```

## Development

### Dependencies

For code generation and quality checks:
```bash
# Required for scraper execution
uv pip install redis boto3 click confluent-kafka pydantic

# Required for code quality (optional but recommended)
uv pip install mypy ruff

# Required for testing
uv pip install pytest pytest-cov fakeredis
```

### Run Tests

```bash
# Install all dependencies
uv pip install pytest pytest-cov redis fakeredis boto3 confluent-kafka pydantic

# Run all tests
pytest tests/ -v --cov=infrastructure

# Run specific test
pytest tests/test_hash_registry.py -v
```

### Code Quality

Generated scrapers are automatically checked with mypy and ruff:

```bash
# Manual check (auto-run during generation)
mypy sourcing/scraping/*/scraper_*.py
ruff check sourcing/scraping/*/scraper_*.py

# Auto-fix ruff issues
ruff check --fix sourcing/scraping/*/scraper_*.py
```

### Generated Scraper Structure

Each scraper follows this pattern:

```python
class MyCollector(BaseCollector):
    def generate_candidates(self, **kwargs) -> List[DownloadCandidate]:
        """Create list of files to download"""

    def collect_content(self, candidate: DownloadCandidate) -> bytes:
        """Download file via HTTP/FTP/etc."""

    def validate_content(self, content: bytes, candidate) -> bool:
        """Validate downloaded content"""
```

## Features

### v1.4.6 (Current) - Enhanced Business Analysis
- ✅ **Enhanced BA agent** - Browser automation for JavaScript-rendered documentation sites
- ✅ **MCP Puppeteer integration** - Extracts API docs from SPAs, React sites, modern portals
- ✅ **/analyze-api command** - Analyze API documentation with graceful fallbacks
- ✅ **JSON format preference** - Defaults to JSON for structured data with override option
- ✅ All v1.4.2 features (uv package management, tabbed questions, type-safe code)

### v1.4.2 - Modern Python Tooling
- ✅ **uv package management** - Modernized to use uv instead of pip for faster, more reliable dependency installation
- ✅ All v1.4.1 features (tabbed question interface, text-input fields, type-safe code, quality checks)

### v1.4.1 - Improved UX
- ✅ **Tabbed question interface** - Visual tabs with radio buttons for better user experience
- ✅ **Text-input fields** - Data Source, Data Type, and Format use free-form text input (no suggestions)
- ✅ All v1.4.0 features (type-safe code, quality checks, auto-fix, quality reporting)

### v1.4.0 - Code Quality
- ✅ **Type-safe code generation** - All generated scrapers include comprehensive type hints
- ✅ **Automatic quality checks** - mypy and ruff checks run after generation
- ✅ **Auto-fix capability** - Automatically fixes ruff style issues
- ✅ **Quality reporting** - Clear reports on type errors and style issues
- ✅ **pyproject.toml configuration** - Automatically installs quality tool configs

### v1.3.0 Features
- ✅ Version tracking in generated scrapers
- ✅ `/fix-scraper` command for debugging and fixing issues
- ✅ `/update-scraper` command for infrastructure sync
- ✅ Anti-hallucination rules to prevent example data contamination
- ✅ Infrastructure verification and auto-install

### v1.0-1.2 Features
- v1.2.0: Config file support (.scraper-dev.md)
- v1.1.0: Self-contained Kafka support
- v1.0.0: HTTP/REST API, Website parsing, FTP/SFTP, Email attachment scrapers
- v1.0.0: Redis hash deduplication, S3 date partitioning, JSON logging
- v1.0.0: 80%+ test coverage, auto-generated documentation

### v2.0 (Future)
- ⏳ GraphQL scrapers
- ⏳ WebSocket scrapers
- ⏳ Bulk migration tool (update 1000s of existing scrapers)
- ⏳ Grafana metrics integration
- ⏳ Data catalog integration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Support

- Issues: File on GitHub
- Documentation: See `docs/` directory
- Examples: See `examples/` directory

## License

MIT License

---

**Generated by:** Claude Scraper Agent v1.4.6
**Last Updated:** 2025-12-05
