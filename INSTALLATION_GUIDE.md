## Quick Start

```bash
cd /Users/mark.johnson/Desktop/source/repos/mark.johnson/claude_scraper_agent

# Install to your sourcing project
./install.sh /path/to/your-sourcing-project

# Restart Claude Code or reload plugins

# Test the plugin
# In Claude Code, type: /create-scraper
```

## What Was Created

### Infrastructure Code (`infrastructure/`)
1. **hash_registry.py** - Redis-based content hash deduplication
2. **logging_json.py** - JSON structured logging for Grafana
3. **collection_framework.py** - Base collector class with S3/Redis/Kafka integration

### Claude Code Plugin (`plugin/`)
1. **plugin.json** - Plugin manifest
2. **agents/** - 3 specialist agents:
   - scraper-generator.md (master orchestrator)
   - http-collector-generator.md (HTTP/REST APIs)
   - website-parser-generator.md (website parsing)
3. **commands/create-scraper.md** - Slash command entry point
4. **skills/scraper-creation.md** - Reusable templates and patterns

### Tests (`tests/`)
1. **test_hash_registry.py** - Comprehensive unit tests for Redis registry

### Documentation
1. **README.md** - Complete project documentation
2. **INSTALLATION_GUIDE.md** - This file
3. **SCRAPER_AGENT_PLAN.md** - Full implementation plan (in sourcing project)

### Installation Script
1. **install.sh** - Automated installer

## Installation Steps

### 1. Install Infrastructure Code

The install script copies infrastructure files to your sourcing project:

```bash
./install.sh /path/to/your-sourcing-project
```

This copies:
- `hash_registry.py` → `sourcing/scraping/commons/`
- `logging_json.py` → `sourcing/common/`
- `collection_framework.py` → `sourcing/scraping/commons/`

### 2. Install Plugin

The script also installs the Claude Code plugin:

```bash
# Automatically copied to:
~/.claude/plugins/scraper-dev/
```

### 3. Install Python Dependencies

```bash
uv pip install redis boto3 click requests beautifulsoup4 lxml
```

### 4. Configure Environment

```bash
# Redis
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0

# S3
export S3_BUCKET=your-s3-bucket-name
export AWS_PROFILE=default  # or use IAM role

# Kafka (optional)
export KAFKA_CONNECTION_STRING="kafka://host:port/topic?..."
```

### 5. Start Redis (if not running)

```bash
# Docker
docker run -d -p 6379:6379 redis:latest

# Or via Homebrew
brew services start redis
```

### 6. Restart Claude Code

Restart Claude Code to load the new plugin, or use the plugin reload command if available.

## Using the Plugin

### Generate Your First Scraper

1. In Claude Code, type: `/create-scraper`
2. Answer the interview questions:
   - Data source name (e.g., NYISO)
   - Data type (e.g., hourly_load)
   - Collection method (HTTP/REST API)
   - Data format (JSON)
   - Update frequency (hourly)
   - Historical support (yes)
   - Authentication (API Key)

3. Provide API-specific details:
   - Base URL
   - Endpoint path
   - Query parameters
   - Rate limits

4. The agent will generate:
   - Complete scraper implementation
   - Comprehensive test suite
   - Sample fixtures
   - README documentation

### Test the Generated Scraper

```bash
# Set API key
export NYISO_API_KEY=your_key_here

# Run tests
cd /path/to/your-sourcing-project
pytest sourcing/scraping/nyiso/tests/ -v --cov

# Test the scraper
python sourcing/scraping/nyiso/scraper_nyiso_hourly_load_http.py \
  --start-date 2025-01-20 \
  --end-date 2025-01-21 \
  --environment dev \
  --skip-hash-check  # For first test run
```

## Architecture Overview

### Data Flow

```
1. Generate Candidates
   ↓
2. For each candidate:
   - Collect content (HTTP GET, FTP download, etc.)
   - Validate content
   - Calculate SHA256 hash
   - Check Redis (skip if exists)
   - Upload to S3 (with gzip compression)
   - Publish Kafka notification
   - Register hash in Redis
   ↓
3. Return summary statistics
```

### Redis Hash Registry

```
Key Format: hash:{env}:{dgroup}:{sha256_hash}

Example:
hash:dev:nyiso_load_forecast:abc123def456...

Value (JSON):
{
  "s3_path": "s3://bucket/sourcing/nyiso_load_forecast/year=2025/...",
  "registered_at": "2025-01-20T14:30:00Z",
  "metadata": {...}
}

TTL: 365 days (configurable)
```

### S3 Date Partitioning

```
Pattern:
s3://{bucket}/{prefix}/{dgroup}/year={YYYY}/month={MM}/day={DD}/{filename}.gz

Example:
s3://bucket/sourcing/nyiso_load_forecast/year=2025/month=01/day=20/load_forecast_20250120_14.json.gz

Benefits:
- Efficient S3 list operations
- Athena/Presto partition pruning
- Easy lifecycle policies
- Simplified data retention
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
  "line": 145,
  "candidate": "load_forecast_20250120_14.json",
  "hash": "abc123...",
  "s3_path": "s3://..."
}
```

Compatible with:
- Grafana Loki
- CloudWatch Logs Insights
- Elasticsearch
- Splunk

## Troubleshooting

### Plugin Not Found

```bash
# Verify installation
ls -la ~/.claude/plugins/scraper-dev/

# Check plugin.json
cat ~/.claude/plugins/scraper-dev/plugin.json

# Restart Claude Code completely
```

### Redis Connection Error

```bash
# Test Redis connectivity
redis-cli ping
# Should return: PONG

# Check environment variables
echo $REDIS_HOST
echo $REDIS_PORT
```

### S3 Upload Error

```bash
# Verify AWS credentials
aws sts get-caller-identity

# Test S3 access
aws s3 ls s3://your-bucket-name/

# Check IAM permissions (need PutObject, GetObject)
```

### Import Errors

```bash
# Ensure infrastructure files are in the right location
ls -la /path/to/your-sourcing-project/sourcing/scraping/commons/hash_registry.py
ls -la /path/to/your-sourcing-project/sourcing/common/logging_json.py
ls -la /path/to/your-sourcing-project/sourcing/scraping/commons/collection_framework.py

# Check Python path
cd /path/to/your-sourcing-project
python -c "from sourcing.scraping.commons.hash_registry import HashRegistry; print('OK')"
```

### Generated Scraper Errors

```bash
# Run linting
cd /path/to/your-sourcing-project
ruff check sourcing/scraping/{source}/

# Run tests
pytest sourcing/scraping/{source}/tests/ -v --tb=short

# Check imports
python -c "from sourcing.scraping.{source}.scraper_{source}_{type}_http import *"
```

## Running Tests

### Test Infrastructure

```bash
cd /Users/mark.johnson/Desktop/source/repos/mark.johnson/claude_scraper_agent

# Install test dependencies
uv pip install pytest pytest-cov

# Run all tests
pytest tests/ -v --cov=infrastructure

# Run specific test
pytest tests/test_hash_registry.py -v

# Generate coverage report
pytest tests/ --cov=infrastructure --cov-report=html
open htmlcov/index.html
```

### Test Generated Scrapers

```bash
cd /path/to/your-sourcing-project

# Run scraper tests
pytest sourcing/scraping/{source}/tests/ -v

# With coverage
pytest sourcing/scraping/{source}/tests/ -v --cov=sourcing.scraping.{source}

# Specific test
pytest sourcing/scraping/{source}/tests/test_scraper_{source}_{type}_http.py::test_generate_candidates -v
```

## Next Steps

1. **Generate Example Scraper**: Try creating a scraper for a simple API
2. **Review Generated Code**: Understand the patterns used
3. **Customize as Needed**: Modify validation logic, add custom methods
4. **Run in Production**: Deploy with proper credentials and monitoring
5. **Iterate**: Use feedback to improve the agent prompts

## Support

- **Documentation**: See `README.md` and `SCRAPER_AGENT_PLAN.md`
- **Examples**: Check `examples/` directory (to be added)
- **Issues**: Review common troubleshooting steps above

## Version History

- **v1.0.0** (2025-01-20): Initial release
  - HTTP/REST API scrapers
  - Website parsing scrapers
  - Redis hash deduplication
  - S3 date partitioning
  - JSON structured logging
  - Kafka notifications

---

**Happy Scraping!** 🎉
