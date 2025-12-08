# LanceDB Plugin Integration Guide

## Overview

This guide explains how to integrate the Claude Code scraper plugin with the external LanceDB infrastructure **after** it has been deployed.

**Prerequisites:**
- LanceDB infrastructure is deployed and operational (see LANCEDB_INFRASTRUCTURE.md)
- MCP server is accessible
- API endpoints are working

**What This Guide Covers:**
- Configuring MCP connection in Claude Code
- Updating agent prompts to use LanceDB tools
- Testing the integration

**What This Does NOT Cover:**
- Building the LanceDB infrastructure (see other guide)
- No changes to scraper infrastructure (Redis, S3, Kafka stay as-is)

---

## Architecture (Plugin Perspective)

```
┌─────────────────────────────────────────────────────────────┐
│ EXTERNAL: LanceDB Infrastructure (Already Built)            │
│  - Indexer service (running in K8s)                         │
│  - Query API (FastAPI at https://lancedb-api.example.com)   │
│  - MCP Server (at https://mcp.example.com or stdio)         │
└────────────────┬────────────────────────────────────────────┘
                 │ (MCP protocol)
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ THIS PLUGIN: Claude Code Agents (This Repo)                 │
│                                                             │
│  plugin/agents/ba-enhanced.md                               │
│    → Add Phase 0 using MCP tool: find_similar_apis         │
│                                                             │
│  plugin/agents/scraper-generator.md                         │
│    → Add context-aware generation using: find_similar_apis  │
│                                                             │
│  plugin/agents/scraper-fixer.md                             │
│    → Add fix pattern retrieval using: get_fix_patterns      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 1: Configure MCP Connection

### Option A: MCP Server via HTTP

If the LanceDB MCP server is deployed as an HTTP service:

Create `.claude/lancedb.mcp.json`:

```json
{
  "mcpServers": {
    "lancedb": {
      "url": "https://mcp.example.com",
      "type": "http",
      "description": "LanceDB query service for scraper data"
    }
  }
}
```

### Option B: MCP Server via stdio

If running MCP server locally:

Create `.claude/lancedb.mcp.json`:

```json
{
  "mcpServers": {
    "lancedb": {
      "command": "python",
      "args": ["-m", "lancedb_mcp"],
      "env": {
        "LANCEDB_API_URL": "https://lancedb-api.example.com"
      }
    }
  }
}
```

### Verify MCP Connection

Test that Claude Code can see the MCP tools:

```bash
# In Claude Code terminal
claude mcp list

# Expected output:
# mcp__lancedb__search_scrapes
# mcp__lancedb__find_similar_apis
# mcp__lancedb__get_fix_patterns
```

---

## Step 2: Update Agent Prompts

### 2.1: Update BA Enhanced Agent

**File:** `plugin/agents/ba-enhanced.md`

Add a new Phase 0 section BEFORE Phase 1:

```markdown
## Phase 0: Historical Context (Optional)

Before analyzing the API, check if we've seen similar APIs before. This helps inform your analysis with real-world patterns from our existing scraper collection.

**Tool**: `mcp__lancedb__find_similar_apis`

**When to Use**:
- Always run this at the start (before Phase 1)
- Especially useful for common data providers (ISOs, weather APIs, financial data)

**Steps**:
1. Extract basic API information from the documentation URL:
   - Domain/provider
   - Endpoint patterns
   - General purpose (if obvious)

2. Call the tool with a simple API spec:
   ```json
   {
     "endpoint": "extracted_from_docs",
     "provider": "provider_name"
   }
   ```

3. Review similar APIs we've scraped before:
   - **Authentication methods** actually required (not just what docs say)
   - **Rate limiting** we've observed in practice
   - **Pagination** patterns that worked
   - **Common issues** encountered

4. Use this context to inform your Phase 1-3 analysis

**Output**:
- Note any relevant patterns in your phase1_documentation.json
- Adjust confidence levels based on historical success with similar APIs

**Example**:

If you find we've successfully scraped 5 other ISO APIs with API key auth, you can:
- Be more confident when documentation is unclear about auth
- Know to check for `Ocp-Apim-Subscription-Key` header patterns
- Expect rate limits around 60 requests/minute

---

## Phase 1: Documentation Extraction
... (rest of existing content)
```

### 2.2: Update Scraper Generator Agent

**File:** `plugin/agents/scraper-generator.md`

Add a new section after the interview (around line 120):

```markdown
## Context-Aware Generation

After completing the interview, retrieve examples of similar scrapers to inform your generation.

**Tool**: `mcp__lancedb__find_similar_apis`

**When to Use**:
- After Batch 1-2 (interview completed)
- Before routing to specialist agent
- Especially for HTTP/REST API scrapers

**Steps**:
1. Build API spec from interview answers:
   ```json
   {
     "endpoint": "<api_base_url + api_endpoint>",
     "method": "GET",
     "auth_required": true/false,
     "data_format": "JSON/CSV/XML",
     "provider": "<data_source>"
   }
   ```

2. Call `mcp__lancedb__find_similar_apis` with spec

3. Review top 3-5 similar scrapers:
   - Code patterns used
   - Authentication handling
   - Error handling approaches
   - Pagination strategies
   - Rate limiting implementation

4. Adapt proven patterns to new scraper:
   - Use similar auth flow if available
   - Apply same error handling structure
   - Include lessons learned in code comments

**Example**:

If similar scrapers show we always use:
- Retry with exponential backoff (3 attempts)
- Rate limiting at 50 req/min for this provider
- Custom auth header `X-API-Key`

Then generate new scraper with same proven patterns.

**Benefits**:
- Higher quality code generation
- Fewer bugs (learned from past)
- Consistent patterns across scrapers
- Faster troubleshooting later

---

## Specialist Agent Routing
... (rest of existing content)
```

### 2.3: Update Scraper Fixer Agent

**File:** `plugin/agents/scraper-fixer.md`

Add a new section in the diagnosis phase (around line 50):

```markdown
## Learn from Past Fixes

When diagnosing issues, check if we've seen similar failures before and how they were resolved.

**Tool**: `mcp__lancedb__get_fix_patterns`

**When to Use**:
- After identifying the error type
- Before proposing a fix
- Especially for recurring issues (auth failures, API changes, rate limits)

**Steps**:
1. Identify the error type from logs/symptoms:
   - `api_auth_failure` - 401, 403 errors
   - `api_endpoint_changed` - 404 errors, schema mismatches
   - `rate_limit_exceeded` - 429 errors, throttling
   - `api_schema_changed` - Parse errors, missing fields
   - `network_timeout` - Connection issues

2. Call tool with scraper name and error type:
   ```json
   {
     "scraper_name": "nyiso_load_forecast",
     "error_type": "api_auth_failure"
   }
   ```

3. Review past fix patterns:
   - **Original error** - What failed?
   - **Fix applied** - What solved it?
   - **Success rate** - Did it work long-term?
   - **Context** - Similar circumstances?

4. Apply proven fix pattern:
   - If similar issue was solved by updating auth header → try that first
   - If schema change required field mapping → check for same pattern
   - If rate limit needed throttling → apply same approach

5. If fix works, it will be stored for future reference

**Example**:

**Scenario**: MISO scraper failing with 401 errors

**Query**: `{"scraper_name": "miso_day_ahead_pricing", "error_type": "api_auth_failure"}`

**Result**: Past fix showed MISO changed from API key to subscription key:
```python
# Old (broken):
headers = {"X-API-Key": api_key}

# Fix (worked):
headers = {"Ocp-Apim-Subscription-Key": subscription_key}
```

**Action**: Apply same fix to current scraper, update auth header pattern.

**Benefits**:
- Faster diagnosis (learned from history)
- Higher fix success rate
- Avoid repeating failed approaches
- Build institutional knowledge

---

## Diagnosis Phase
... (rest of existing content)
```

---

## Step 3: Test Integration

### 3.1: Test BA Agent with Context

Run the BA agent on a new API and verify it retrieves context:

```bash
# In Claude Code
/scraper-dev:analyze-api https://api.example.com/docs
```

**Expected behavior:**
1. Agent runs Phase 0 first
2. Calls `mcp__lancedb__find_similar_apis`
3. Reviews similar APIs
4. Mentions historical context in phase1 output
5. Proceeds with normal 3-phase validation

**Verify:**
- Check phase1_documentation.json mentions "similar APIs found"
- Confidence scores adjusted based on history
- No errors calling MCP tool

### 3.2: Test Generator with Context

Create a new scraper and verify context retrieval:

```bash
# In Claude Code
/scraper-dev:create-scraper
```

**Expected behavior:**
1. Complete interview (Batch 1-2)
2. Agent calls `mcp__lancedb__find_similar_apis` after interview
3. Reviews 3-5 similar scrapers
4. Generates code using proven patterns
5. Includes comments referencing similar scrapers

**Verify:**
- Generated code includes "Based on similar scraper..." comments
- Auth/error handling matches proven patterns
- No errors calling MCP tool

### 3.3: Test Fixer with Past Patterns

Trigger a scraper fix and verify pattern retrieval:

```bash
# In Claude Code, with a broken scraper
/scraper-dev:fix-scraper path/to/broken_scraper.py
```

**Expected behavior:**
1. Agent diagnoses error type
2. Calls `mcp__lancedb__get_fix_patterns`
3. Reviews past similar fixes
4. Applies proven fix pattern
5. Mentions "This fix worked for X similar scraper" in output

**Verify:**
- Fix matches past successful patterns
- Agent explains why this fix should work
- No errors calling MCP tool

---

## Step 4: Update Plugin Configuration (Optional)

If you want to make the MCP tools discoverable in plugin documentation:

**File:** `plugin/plugin.json`

Add to the agent descriptions:

```json
{
  "agents": [
    {
      "name": "ba-enhanced",
      "description": "Business analyst with 3-phase validation and historical context via LanceDB",
      "file": "agents/ba-enhanced.md",
      "color": "blue"
    },
    {
      "name": "scraper-generator",
      "description": "Master orchestrator with context-aware generation from similar scrapers (LanceDB)",
      "file": "agents/scraper-generator.md",
      "color": "blue"
    },
    {
      "name": "scraper-fixer",
      "description": "Diagnoses and fixes scrapers using historical fix patterns (LanceDB)",
      "file": "agents/scraper-fixer.md",
      "color": "yellow"
    }
  ]
}
```

---

## Troubleshooting

### MCP Tools Not Available

**Symptom**: Agent says "Tool not found: mcp__lancedb__find_similar_apis"

**Fix**:
1. Verify MCP server is running:
   ```bash
   curl https://lancedb-api.example.com/
   ```

2. Check MCP configuration:
   ```bash
   cat .claude/lancedb.mcp.json
   ```

3. Restart Claude Code to reload MCP config

### MCP Tool Returns Empty Results

**Symptom**: Tool calls succeed but return empty `similar_apis: []`

**Possible causes:**
1. **LanceDB not indexed yet** - Wait for indexer to process some files
2. **Query too specific** - Try broader API spec
3. **Different data source** - May not have similar scrapers yet

**Verify indexing:**
```bash
curl "https://lancedb-api.example.com/api/v1/scrapes/search?limit=10"
```

Should return some results if indexer is working.

### Agent Ignores MCP Context

**Symptom**: Agent doesn't mention similar APIs in output

**Possible causes:**
1. **Tool call failed silently** - Check agent trace logs
2. **No relevant results** - Tool returned empty, agent skipped
3. **Agent prompt not clear** - May need to emphasize using tool

**Fix**: Update agent prompt to be more explicit about WHEN and HOW to use the tool.

---

## Success Criteria

### ✅ Integration Complete When:

1. **MCP Connection Working**
   - `claude mcp list` shows LanceDB tools
   - Test API calls succeed

2. **BA Agent Enhanced**
   - Phase 0 runs automatically
   - Context retrieved and mentioned in output
   - No errors in agent execution

3. **Generator Agent Enhanced**
   - Context retrieval after interview
   - Generated code uses proven patterns
   - Comments reference similar scrapers

4. **Fixer Agent Enhanced**
   - Fix patterns retrieved during diagnosis
   - Past solutions applied to current problems
   - Success rate improves over time

5. **Plugin Updated**
   - All agent files modified
   - Plugin version bumped
   - Documentation updated

---

## Files Modified (Checklist)

- [ ] `.claude/lancedb.mcp.json` - MCP server configuration
- [ ] `plugin/agents/ba-enhanced.md` - Added Phase 0 (historical context)
- [ ] `plugin/agents/scraper-generator.md` - Added context-aware generation
- [ ] `plugin/agents/scraper-fixer.md` - Added fix pattern retrieval
- [ ] `plugin/plugin.json` - Updated agent descriptions (optional)
- [ ] `README.md` - Document LanceDB integration (optional)

---

## Next Steps After Integration

1. **Monitor Usage**
   - Track how often agents use MCP tools
   - Measure success rate improvements
   - Collect feedback from team

2. **Iterate on Prompts**
   - Refine WHEN agents should use context
   - Adjust HOW they incorporate historical data
   - Add more specific guidance based on results

3. **Expand Use Cases**
   - Add more agent context endpoints as needed
   - Consider adding frontend queries
   - Build dashboards showing historical patterns

4. **Document Learnings**
   - Track which patterns work best
   - Document common fix patterns
   - Share insights with team

---

## Cost Impact

**Good News**: Plugin changes have ZERO additional cost!

The LanceDB infrastructure costs ~$94/month (see other guide), but:
- This plugin just USES it via MCP
- No new infrastructure in this repo
- No additional compute/storage
- Only benefit, no cost

**What This Means**:
- Free improvement to agent quality
- No operational burden on plugin
- All costs managed by LanceDB team
- Clear separation of concerns

---

## Summary

**What Changed:**
- Added Phase 0 to BA agent (historical context)
- Added context-aware generation to scraper-generator
- Added fix pattern retrieval to scraper-fixer
- Configured MCP connection to LanceDB

**What Didn't Change:**
- Scraper infrastructure (Redis, S3, Kafka)
- Infrastructure files (hash_registry, collection_framework, kafka_utils)
- Agent core functionality (still does 3-phase validation, generation, fixing)

**Impact:**
- Better agent decisions (learned from history)
- Higher quality generated code (proven patterns)
- Faster fixes (known solutions)
- No additional infrastructure burden
