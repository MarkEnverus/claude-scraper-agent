---
description: Analyze any data source (API, FTP, website, email) using Python CLI
---

Analyze any data source from a URL using the Python CLI implementation.

**Supported source types:**
- REST/SOAP APIs
- FTP/SFTP servers
- Email data sources
- Website portals with downloadable data
- Database connection documentation

**Usage:**
```
/scraper-dev:analyze {url}
```

**Implementation:**

1. Run the Python CLI BA analyzer:
```bash
uv run python -m claude_scraper.cli.main run --mode analyze --url "{url}"
```

2. Read and present the validated specification:
```bash
cat datasource_analysis/validated_datasource_spec.json
```

**Output files:**
- `datasource_analysis/phase0_detection.json` - Type detection
- `datasource_analysis/phase1_documentation.json` - Documentation extraction
- `datasource_analysis/phase2_tests.json` - Live testing results
- `datasource_analysis/validated_datasource_spec.json` - Final validated spec (present this to user)
- `api_validation_tests/test_*.txt` - HTTP test outputs

**Features:**
- ✅ Botasaurus browser automation (handles JavaScript)
- ✅ Type-safe with BAML + Pydantic
- ✅ Live HTTP testing with rate limiting
- ✅ Cross-validation and discrepancy detection
