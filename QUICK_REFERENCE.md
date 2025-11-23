# Claude Scraper Agent - Quick Reference Card

## Installation (One-Time)

```bash
cd /Users/mark.johnson/Desktop/source/repos/mark.johnson/claude_scraper_agent
./install.sh /Users/mark.johnson/Desktop/source/repos/enverus-pr/pr.prt.sourcing
# Restart Claude Code
```

## Generate a Scraper

```
In Claude Code, type: /create-scraper
Answer 7 questions → Agent generates complete scraper
```

## Environment Setup

```bash
export REDIS_HOST=localhost
export REDIS_PORT=6379
export S3_BUCKET=enverus-pr-ue1-cdr-unrestricted-prt-raw-prod
export NYISO_API_KEY=your_key  # Replace with actual source
```

## Test Generated Scraper

```bash
cd /path/to/pr.prt.sourcing
pytest sourcing/scraping/{source}/tests/ -v
python sourcing/scraping/{source}/scraper_{source}_{type}_http.py \
  --start-date 2025-01-20 --end-date 2025-01-21 --environment dev
```

## Key Patterns

| Component | Pattern |
|-----------|---------|
| Redis Keys | `hash:{env}:{dgroup}:{sha256}` |
| S3 Paths | `s3://bucket/sourcing/{dgroup}/year=YYYY/month=MM/day=DD/{file}.gz` |
| Class Names | `{Source}{Type}Collector` (CamelCase) |
| File Names | `scraper_{source}_{type}_{method}.py` (snake_case) |

## CLI Flags (All Scrapers)

```
--start-date YYYY-MM-DD   # Required for historical
--end-date YYYY-MM-DD     # Required for historical
--environment dev         # dev/staging/prod
--force                   # Bypass hash check
--skip-hash-check         # For testing
--kafka-connection-string # Optional Kafka config
--log-level INFO          # DEBUG/INFO/WARNING/ERROR
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Plugin not found | `ls ~/.claude/plugins/scraper-dev/` then restart Claude Code |
| Redis error | `redis-cli ping` should return PONG |
| S3 error | `aws sts get-caller-identity` verify credentials |
| Import error | Check files in `sourcing/scraping/commons/` |

## File Locations

```
claude_scraper_agent/
├── infrastructure/           # Copy to sourcing project
│   ├── hash_registry.py
│   ├── logging_json.py
│   └── collection_framework.py
├── plugin/                   # Copy to ~/.claude/plugins/
│   ├── plugin.json
│   ├── agents/
│   ├── commands/
│   └── skills/
└── tests/                    # Run: pytest tests/ -v
```

## Documentation

- `README.md` - Full documentation
- `INSTALLATION_GUIDE.md` - Installation steps
- `PROJECT_SUMMARY.md` - Project overview
- `SCRAPER_AGENT_PLAN.md` - Implementation plan (in sourcing project)

## Support

Questions? See `INSTALLATION_GUIDE.md` for detailed troubleshooting.

---

**Version:** 1.0.0 | **Date:** January 20, 2025
