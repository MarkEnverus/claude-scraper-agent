# Installation Guide

## Quick Start

The fastest way to get started with Claude Scraper Agent:

### 1. Install the Plugin

**Method 1: Install from Marketplace (Recommended)**

```bash
# Add the marketplace to Claude Code
claude plugin marketplace add https://github.com/MarkEnverus/claude-scraper-agent

# Install the plugin
claude plugin install scraper-dev@scraper-agent-marketplace
```

**Method 2: Install via GitHub URL**

```bash
# Add the GitHub repository as a marketplace
claude plugin marketplace add https://github.com/MarkEnverus/claude-scraper-agent

# Install the plugin
claude plugin install scraper-dev@scraper-agent-marketplace
```

Infrastructure files are bundled in the plugin and auto-installed on first use!

### 2. Configure Environment

```bash
# Install Python dependencies (required)
pip install redis boto3 click requests beautifulsoup4 playwright confluent-kafka pydantic

# Install code quality tools (optional but recommended)
pip install mypy ruff

# Set environment variables
export REDIS_HOST=localhost
export REDIS_PORT=6379
export S3_BUCKET=your-bucket-name

# Optional: Kafka configuration
export KAFKA_CONNECTION_STRING="kafka://localhost:9092/my-topic"
# Or with SASL authentication
export KAFKA_CONNECTION_STRING="kafka://localhost:9092/my-topic?security_protocol=SASL_PLAINTEXT"
export SASL_USERNAME=your_username
export SASL_PASSWORD=your_password
```

### 3. (Optional) Create Config Files

Speed up scraper generation by pre-configuring your datasets:

```bash
# Copy example config
cp .scraper-dev.example.md sourcing/scraping/nyiso/load_forecast/.scraper-dev.md

# Edit with your values
nano sourcing/scraping/nyiso/load_forecast/.scraper-dev.md
```

The agent will automatically find and use config values, only asking for what's missing.

### 4. Restart and Test

```bash
# Restart Claude Code
# In Claude Code, type:
/create-scraper
```

The agent will:
1. Check if infrastructure files exist in your project
2. Auto-install them if missing
3. Scan for `.scraper-dev.md` config files (optional)
4. Start the interactive scraper generation wizard

---

## Verification

After installation, verify everything is working:

### Check Plugin Installation

```bash
# List installed plugins
claude plugin list

# Should show:
# scraper-dev@scraper-agent-marketplace (enabled)
```

### Check Infrastructure Files

```bash
# Navigate to your sourcing project
cd /path/to/your-sourcing-project

# Check files exist
ls -l sourcing/scraping/commons/hash_registry.py
ls -l sourcing/scraping/commons/collection_framework.py
ls -l sourcing/scraping/commons/kafka_utils.py
ls -l sourcing/common/logging_json.py
```

### Test Plugin in Claude Code

1. Open Claude Code
2. Type `/create-`
3. Should see `/create-scraper` autocomplete
4. Run `/create-scraper` to test

---

## Troubleshooting

### Plugin Not Found

**Problem:** `/create-scraper` command doesn't autocomplete

**Solutions:**
1. Restart Claude Code completely (close terminal and reopen)
2. Verify plugin is installed: `claude plugin list`
3. Check plugin is enabled: `claude plugin enable scraper-dev`
4. Manually check `~/.claude/plugins/installed_plugins.json` contains `scraper-dev`

### Infrastructure Files Not Found

**Problem:** Generated scrapers fail with import errors

**Solutions:**
1. Verify files exist in correct locations
2. Check file permissions: `chmod 644 sourcing/scraping/commons/*.py`
3. Ensure Python can import from `sourcing/` directory
4. Add `__init__.py` files if needed

### Redis Connection Errors

**Problem:** Scrapers fail with "Redis connection refused"

**Solutions:**
1. Start Redis: `redis-server` or `docker run -p 6379:6379 redis`
2. Verify Redis is running: `redis-cli ping` (should return "PONG")
3. Check environment variables: `echo $REDIS_HOST`
4. Update connection string if using custom Redis

### S3 Upload Errors

**Problem:** Files collected but not uploaded to S3

**Solutions:**
1. Check AWS credentials: `aws sts get-caller-identity`
2. Verify S3 bucket exists: `aws s3 ls s3://your-bucket-name`
3. Check IAM permissions for S3 write access
4. Verify `S3_BUCKET` environment variable is set

---

## Updating

### Update Plugin

```bash
# Update marketplace
claude plugin marketplace update scraper-agent-marketplace

# Reinstall plugin
claude plugin install scraper-dev@scraper-agent-marketplace
```

### Update Infrastructure Files

Infrastructure files are bundled with the plugin and updated automatically when you update the plugin.

---

## Uninstalling

### Remove Plugin

```bash
claude plugin uninstall scraper-dev
```

### Remove Infrastructure Files

```bash
cd /path/to/your-sourcing-project
rm sourcing/scraping/commons/hash_registry.py
rm sourcing/scraping/commons/collection_framework.py
rm sourcing/common/logging_json.py
```

---

## Next Steps

After installation:
1. Read [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for usage guide
2. See [examples/](examples/) for generated scraper examples
3. Review [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) for architecture details
4. Contribute improvements via [CONTRIBUTING.md](CONTRIBUTING.md)

## Support

- **Issues:** https://github.com/yourusername/claude_scraper_agent/issues
- **Discussions:** https://github.com/yourusername/claude_scraper_agent/discussions
- **Documentation:** See [docs/](docs/) directory
