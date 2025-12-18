# Claude Scraper Agent v1.13.0

Automated scraper generation system for data collection pipelines using Claude Code. Generates type-safe, quality-checked scrapers with tabbed question interface, version tracking, and maintenance tools.

**Latest Updates (v1.13.0):**
- BA Agent v2.2.0: CRITICAL - Explicit tool usage enforcement (no pseudo-code), absolute hallucination prohibition, working directory awareness

## Overview

This project contains:
- **Infrastructure Code**: Base classes for Redis hash registry, JSON logging, Kafka notifications, and collection framework
- **Claude Code Plugin**: Agents that generate production-ready scrapers
- **Tests**: Unit tests for infrastructure components
- **Examples**: Sample generated scrapers
- **Documentation**: Usage guides and API references

## Project Structure

```
claude_scraper_agent/
├── infrastructure/          # Base classes to be copied to sourcing project
│   ├── hash_registry.py
│   ├── logging_json.py
│   ├── kafka_utils.py
│   └── collection_framework.py
├── plugin/                  # Claude Code plugin
│   ├── plugin.json
│   ├── agents/
│   ├── commands/
│   └── skills/
├── tests/                   # Unit tests
├── examples/                # Example generated scrapers
└── docs/                    # Documentation
```

## Installation

### Method 1: Install from Marketplace (Recommended)

Install the Claude Code plugin directly from the marketplace:

```bash
# Add the marketplace
claude plugin marketplace add https://github.com/MarkEnverus/claude-scraper-agent

# Install the plugin
claude plugin install scraper-dev@scraper-agent-marketplace
```

**That's it!** Infrastructure files are automatically installed when you first run `/create-scraper`.

### Method 2: Install via GitHub URL

Install directly from the GitHub repository:

```bash
# Add the GitHub repository as a marketplace
claude plugin marketplace add https://github.com/MarkEnverus/claude-scraper-agent

# Install the plugin
claude plugin install scraper-dev@scraper-agent-marketplace
```

### Verify Installation

1. **Restart Claude Code** (close and reopen terminal)
2. Type `/create-scraper` - command should autocomplete
3. If available, the plugin is installed correctly

For detailed installation instructions and troubleshooting, see [INSTALLATION.md](INSTALLATION.md).

## Usage

### Generate a New Scraper

```bash
# In Claude Code
/create-scraper
```

The agent will interview you about:
- Data source name
- Data type
- Collection method (HTTP API, Website, FTP, etc.)
- Authentication requirements
- Update frequency

### Fix an Existing Scraper

```bash
# In Claude Code
/fix-scraper
```

Use this when a scraper stops working due to:
- API endpoint changes
- Data format changes
- Authentication updates
- Import errors
- Any other code issues

The agent will:
1. Scan for existing scrapers
2. Let you select which one to fix
3. Diagnose the problem
4. Propose and apply fixes

### Update Scrapers to New Infrastructure

```bash
# Scan mode (just report what needs updating)
/update-scraper
/update-scraper --mode=scan

# Auto mode (propose and apply updates)
/update-scraper --mode=auto
```

Use this when infrastructure is updated to:
- Sync scrapers with new framework versions
- Add missing features (e.g., Kafka support)
- Update imports after refactoring
- Apply bug fixes and improvements

The agent will:
1. Scan all scrapers for version information
2. Report which scrapers need updates
3. (In auto mode) Propose updates and apply with approval
4. Preserve all custom business logic

### Example Workflow

```
User: /create-scraper

Agent: I'll help you create a new scraper. Let me gather some information...

1. Data Source Name: NYISO
2. Data Type: hourly_load
3. Collection Method: HTTP REST API
4. Data Format: JSON
5. Update Frequency: hourly
6. Historical Support: Yes
7. Authentication: API Key

Agent: [Generates complete scraper with tests and documentation]

Generated files:
✓ sourcing/scraping/nyiso/scraper_nyiso_hourly_load_http.py
✓ sourcing/scraping/nyiso/tests/test_scraper_nyiso_hourly_load_http.py
✓ sourcing/scraping/nyiso/tests/fixtures/sample_response.json
✓ sourcing/scraping/nyiso/README.md
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
