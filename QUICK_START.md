# Quick Start Guide: BA Analyzer

## Installation

```bash
# Clone the repo
cd claude_scraper_agent

# Install dependencies
uv sync

# Verify installation
uv run python -m claude_scraper.cli.main --help
```

## Basic Usage

### 1. Command Line (Easiest)

```bash
# Analyze any data source
uv run python -m claude_scraper.cli.main run --mode analyze \
  --url "https://data-exchange.misoenergy.org/api-details#api=pricing-api"
```

**Output:**
```
datasource_analysis/
├── phase0_detection.json          (Type detection + endpoints)
├── phase1_documentation.json      (Documentation extraction)
├── phase2_tests.json              (Live testing results)
└── validated_datasource_spec.json (Final validated spec)

api_validation_tests/
└── test_*.txt                     (HTTP test outputs)
```

**Time:** 15-20 seconds

### 2. Python Script

Create `analyze.py`:
```python
import asyncio
from claude_scraper.agents.ba_analyzer import BAAnalyzer
from claude_scraper.tools.botasaurus_tool import BotasaurusTool

async def main():
    # Initialize
    analyzer = BAAnalyzer(botasaurus=BotasaurusTool())

    # Analyze
    spec = await analyzer.run_full_analysis(
        "https://api.example.com/docs"
    )

    # Results
    print(f"Type: {spec.source_type}")
    print(f"Endpoints: {len(spec.endpoints)}")
    print(f"Auth: {spec.authentication.method}")
    print(f"Confidence: {spec.validation_summary.confidence_score:.2f}")

asyncio.run(main())
```

Run it:
```bash
uv run python analyze.py
```

### 3. Interactive Python

```python
import asyncio
from claude_scraper.agents.ba_analyzer import BAAnalyzer
from claude_scraper.tools.botasaurus_tool import BotasaurusTool

# In async context (Jupyter, IPython with asyncio)
analyzer = BAAnalyzer(botasaurus=BotasaurusTool())
spec = await analyzer.run_full_analysis("https://api.example.com")

# Check results
spec.validation_summary.confidence_score
spec.endpoints[0].path
spec.authentication.required
```

## Common Use Cases

### Case 1: Analyze API Documentation

```bash
uv run python -m claude_scraper.cli.main run --mode analyze \
  --url "https://api.example.com/docs"
```

**What it does:**
1. Detects it's an API (Phase 0)
2. Extracts endpoints + parameters (Phase 1)
3. Tests endpoints for auth (Phase 2)
4. Validates and cross-checks (Phase 3)

### Case 2: Analyze Data Portal

```bash
uv run python -m claude_scraper.cli.main run --mode analyze \
  --url "https://portal.example.com/data"
```

**What it does:**
1. Detects it's a website portal (Phase 0)
2. Finds download links (Phase 1)
3. Tests link accessibility (Phase 2)
4. Validates file metadata (Phase 3)

### Case 3: Programmatic Integration

```python
from claude_scraper.agents.ba_analyzer import BAAnalyzer
from claude_scraper.tools.botasaurus_tool import BotasaurusTool

class MyScraperFactory:
    def __init__(self):
        self.analyzer = BAAnalyzer(botasaurus=BotasaurusTool())

    async def create_scraper(self, url: str):
        # Analyze the source
        spec = await self.analyzer.run_full_analysis(url)

        # Generate scraper based on spec
        if spec.scraper_recommendation.type == "API_CLIENT":
            return self.generate_api_scraper(spec)
        elif spec.scraper_recommendation.type == "WEBSITE_PARSER":
            return self.generate_web_scraper(spec)

    def generate_api_scraper(self, spec):
        # Use spec.endpoints, spec.authentication, etc.
        pass
```

## What You Get

### Validated Datasource Spec (JSON)

```json
{
  "source": "MISO Energy Pricing API",
  "source_type": "API",
  "validation_summary": {
    "confidence_score": 0.8,
    "confidence_level": "HIGH",
    "recommendation": "Spec validated - ready for scraper generation"
  },
  "authentication": {
    "required": true,
    "method": "API_KEY",
    "header_name": "Ocp-Apim-Subscription-Key",
    "registration_url": "https://data-exchange.misoenergy.org/"
  },
  "endpoints": [
    {
      "name": "Day-Ahead Market Prices",
      "path": "/pricing/v1/da-lmp",
      "method": "GET",
      "parameters": {...},
      "authentication": {"required": "true", "method": "API_KEY"}
    }
  ],
  "discrepancies": [
    {
      "type": "endpoint_url_mismatch",
      "severity": "high",
      "resolution": "Use https://api.misoenergy.org base URL"
    }
  ],
  "scraper_recommendation": {
    "type": "API_CLIENT",
    "complexity": "MEDIUM",
    "estimated_effort": "4-6 hours"
  }
}
```

## Advanced: Phase-by-Phase Control

```python
import asyncio
from claude_scraper.agents.ba_analyzer import BAAnalyzer
from claude_scraper.tools.botasaurus_tool import BotasaurusTool

async def analyze_custom():
    analyzer = BAAnalyzer(botasaurus=BotasaurusTool())
    url = "https://api.example.com/docs"

    # Phase 0: Detection
    phase0 = await analyzer.analyze_phase0(url)
    if phase0.confidence < 0.8:
        print("Low confidence - manual review needed")
        return

    # Phase 1: Documentation
    phase1 = await analyzer.analyze_phase1(url, phase0)
    if len(phase1.endpoints) == 0:
        print("No endpoints found - stopping")
        return

    # Phase 2: Testing (only first 3 endpoints)
    limited_phase1 = phase1.copy()
    limited_phase1.endpoints = phase1.endpoints[:3]
    phase2 = await analyzer.analyze_phase2(url, phase0, limited_phase1)

    # Phase 3: Validation
    phase3 = await analyzer.analyze_phase3(url, phase0, phase1, phase2)

    return phase3

asyncio.run(analyze_custom())
```

## Key Features

### 1. Botasaurus Browser Automation
- ✅ JavaScript-rendered pages (React, Vue, Angular)
- ✅ Anti-bot detection handling
- ✅ Network traffic monitoring
- ✅ Pure Python (no Node.js needed)

### 2. Type Safety (BAML + Pydantic)
- ✅ All data structures validated
- ✅ IDE autocomplete works
- ✅ Runtime type checking
- ✅ No hallucination of data structures

### 3. Live Testing
- ✅ HTTP testing of endpoints
- ✅ Authentication detection
- ✅ Rate limiting (1 req/sec)
- ✅ Error handling

### 4. Cross-Validation
- ✅ Compares documentation vs. reality
- ✅ Identifies discrepancies
- ✅ Confidence scoring
- ✅ Actionable recommendations

## Troubleshooting

### Issue: Module not found
```bash
# Make sure dependencies are installed
uv sync

# Run with uv
uv run python -m claude_scraper.cli.main --help
```

### Issue: Botasaurus fails
```bash
# Install/update Botasaurus
uv pip install --upgrade botasaurus

# Check if Chrome/Chromium is installed
```

### Issue: BAML errors
```bash
# Regenerate BAML types
cd baml_src
baml generate
```

## Next Steps

1. **Try the examples:**
   ```bash
   uv run python examples/simple_analysis.py
   ```

2. **Read the migration guide:**
   ```bash
   cat MIGRATION_STATUS.md
   ```

3. **Run the test suite:**
   ```bash
   uv run pytest tests/
   ```

4. **Build your own integration:**
   - Use `BAAnalyzer` as a library
   - Import types from `baml_client.types`
   - Customize the analysis flow

## Support

- **Documentation:** See `MIGRATION_STATUS.md`
- **Examples:** See `examples/` directory
- **Tests:** See `tests/` directory for usage patterns
- **Issues:** Check the repo's issue tracker

---

**That's it! You're ready to analyze any data source with type-safe, validated specifications.** 🚀
