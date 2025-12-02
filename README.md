# Claude Scraper Agent v1.0

Automated scraper generation system for data collection pipelines using Claude Code.

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
s3://bucket/sourcing/{dgroup}/year={YYYY}/month={MM}/day={DD}/{filename}.gz

Example:
s3://bucket/sourcing/nyiso_load_forecast/year=2025/month=01/day=20/load_forecast_20250120_14.json.gz
```

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

### Run Tests

```bash
# Install dependencies
pip install pytest pytest-cov redis fakeredis boto3 confluent-kafka pydantic

# Run all tests
pytest tests/ -v --cov=infrastructure

# Run specific test
pytest tests/test_hash_registry.py -v
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

### v1.0 (Current)
- ✅ HTTP/REST API scrapers
- ✅ Website parsing scrapers
- ✅ FTP/SFTP file download scrapers
- ✅ Email attachment download scrapers
- ✅ Redis hash deduplication
- ✅ S3 date partitioning
- ✅ JSON structured logging
- ✅ Kafka notifications (fully self-contained)
- ✅ 80%+ test coverage
- ✅ Auto-generated documentation

### v2.0 (Future)
- ⏳ FTP/SFTP scrapers
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

**Generated by:** Claude Scraper Agent v1.0
**Last Updated:** 2025-01-20
