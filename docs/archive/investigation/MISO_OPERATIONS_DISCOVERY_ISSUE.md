# MISO Operations Discovery Issue

**Date:** January 13, 2026
**Status:** Issue Identified - Requires Fix

---

## Executive Summary

**Problem:** BA discovered only 2 API **catalog entries** (pricing-api, load-generation-api) instead of the 10+ individual **operations** within each API.

**Impact:** Filtering works correctly (21→2) but is filtering the wrong granularity. It should be filtering 50+ operations down to 10+ data operations.

**Root Cause:** The BA planner didn't visit the APIM `/operations` URLs during exploration, so `api_p1_handler` couldn't discover the individual API operations.

---

## Current State vs. Expected State

### Current (Incorrect Granularity)
```
BA Discovers:
├─ pricing-api (CATALOG ENTRY) ✅ kept
└─ load-generation-api (CATALOG ENTRY) ✅ kept

Generator Creates:
├─ scraper_pricing_api.py (scrapes ALL pricing operations)
└─ scraper_load_generation_api.py (scrapes ALL load operations)
```

### Expected (Correct Granularity)
```
BA Discovers:
├─ pricing-api (CATALOG)
│   ├─ GET /pricing-api/da-lmp (operation) ✅ kept
│   ├─ GET /pricing-api/rt-lmp (operation) ✅ kept
│   ├─ GET /pricing-api/mcp (operation) ✅ kept
│   ├─ GET /pricing-api/historical (operation) ✅ kept
│   └─ ... (5-10 more operations)
└─ load-generation-api (CATALOG)
    ├─ GET /load-api/demand (operation) ✅ kept
    ├─ GET /load-api/forecast (operation) ✅ kept
    ├─ GET /generation-api/cleared (operation) ✅ kept
    └─ ... (5-10 more operations)

Generator Creates:
├─ scraper_pricing_da_lmp.py (scrapes day-ahead LMP only)
├─ scraper_pricing_rt_lmp.py (scrapes real-time LMP only)
├─ scraper_pricing_mcp.py (scrapes market clearing price only)
└─ ... (one scraper per operation)
```

---

## Technical Analysis

### What Happened During MISO Analysis

**Phase 0 (Detection):**
- ✅ BA detected MISO as API source type
- ✅ BA routed to `api_p1_handler` (API Phase 1)

**Phase 1 (API Discovery via api_p1_handler):**
- ❌ BA planner didn't visit `/operations` URLs
- ❌ `api_p1_handler` couldn't find operations JSON
- ❌ Fell back to extracting catalog entries only

**Result:**
- 21 endpoints discovered (18 portal junk + 2 catalog entries + 1 home)
- Filtering worked: 21 → 2 (kept catalog entries)
- But wrong granularity!

### The Missing URLs

**These URLs exist but weren't visited:**
```
https://data-exchange.misoenergy.org/developer/apis/pricing-api/operations
https://data-exchange.misoenergy.org/developer/apis/load-generation-api/operations
```

**These URLs return JSON with operation lists:**
```json
{
  "operations": [
    {
      "id": "da-lmp",
      "path": "/pricing-api/da-lmp",
      "method": "GET",
      "summary": "Day-ahead Locational Marginal Pricing",
      ...
    },
    {
      "id": "rt-lmp",
      "path": "/pricing-api/rt-lmp",
      "method": "GET",
      "summary": "Real-time Locational Marginal Pricing",
      ...
    },
    ...
  ]
}
```

**APIM Pattern Recognition:**
- ✅ Pattern `/developer/apis/*/operations` is in `APIM_PRIORITY_PATTERNS`
- ✅ `is_apim_priority()` correctly identifies these URLs
- ❌ But planner never visited them!

---

## Root Cause Analysis

### Why Didn't the Planner Visit `/operations` URLs?

**Hypothesis 1: URLs Not Visible as Links**
- APIM portals often load operation lists via JavaScript clicks
- The `/operations` URLs might not be in `<a>` tags
- Planner relies on `extract_links` tool which only sees HTML links

**Hypothesis 2: Low Priority Scoring**
- Planner may have seen the links but scored them lower priority
- Focused on nav pages instead of drilling into each API

**Hypothesis 3: Early Stopping**
- BA might have hit stop conditions before visiting API details
- `max_steps` or `max_depth` reached too early

### The api_p1_handler Design

**File:** `agentic_scraper/business_analyst/nodes/api_p1_handler.py`

**How it works:**
1. Looks for OpenAPI/Swagger spec URLs in:
   - Navigation links
   - Network calls
   - Page text
2. Fetches and parses specs
3. Extracts all operations → EndpointFinding objects

**The Gap:**
- It's designed to parse **OpenAPI specs** (`/openapi.json`, `/swagger.json`)
- But MISO uses **APIM JSON** (`/operations` returns non-standard JSON)
- The `openapi_parser.py` might not handle APIM JSON format

---

## Solution Design

### Option 1: Enhance Planner to Visit APIM Operations URLs (Recommended)

**Approach:** Make planner proactively visit `/operations` URLs when APIM patterns detected.

**Implementation:**
1. After Phase 0 detects API source
2. Extract API names from catalog (pricing-api, load-generation-api)
3. Construct `/developer/apis/{api_name}/operations` URLs
4. Add these to high-priority queue
5. Force planner to visit them before stopping

**Code Changes:**
- `agentic_scraper/business_analyst/nodes/api_p1_handler.py`: Add APIM operations discovery
- `agentic_scraper/business_analyst/utils/openapi_parser.py`: Add APIM JSON parser

**Example:**
```python
def discover_apim_operations(artifact, api_names):
    """Construct and fetch APIM operation URLs."""
    operations_urls = []
    for api_name in api_names:
        url = f"https://{domain}/developer/apis/{api_name}/operations"
        operations_urls.append(url)

    all_operations = []
    for url in operations_urls:
        response = fetch_json(url)
        operations = parse_apim_operations_json(response)
        all_operations.extend(operations)

    return all_operations
```

**Pros:**
- Targeted fix for APIM portals
- Works with existing api_p1_handler
- Minimal changes to planner

**Cons:**
- Requires parsing APIM-specific JSON format
- Hardcodes APIM URL patterns

### Option 2: Enhance Planner Link Prioritization

**Approach:** Train planner to recognize and prioritize APIM operation URLs.

**Implementation:**
1. Add APIM patterns to link scoring
2. Boost score for URLs containing `/operations`, `/developer/apis/`
3. Ensure these links are visited early

**Code Changes:**
- `agentic_scraper/business_analyst/tools/link_rerank.py`: Add APIM boost
- `agentic_scraper/business_analyst/nodes/planner_react.py`: Prioritize APIM links

**Pros:**
- General solution (works for future portals)
- Uses existing planner exploration logic

**Cons:**
- Doesn't guarantee operation URLs are visited
- Still relies on URLs being visible as links

### Option 3: Phase 1.5 - Active APIM Probing (Most Robust)

**Approach:** Add a dedicated "APIM Probe" step after Phase 1 detection.

**Implementation:**
1. After Phase 0 detects API + APIM indicators
2. Run dedicated APIM probe:
   - Extract API names from page
   - Construct operation URLs programmatically
   - Fetch each `/operations` endpoint
   - Parse and merge all operations
3. Continue with normal flow

**Code Changes:**
- NEW: `agentic_scraper/business_analyst/nodes/apim_probe.py`
- UPDATE: `agentic_scraper/business_analyst/graph.py` (add apim_probe node)
- NEW: `agentic_scraper/business_analyst/utils/apim_parser.py`

**Pros:**
- Guaranteed to discover all operations
- Portal-specific optimization
- Doesn't rely on link visibility

**Cons:**
- More complex (new graph node)
- APIM-specific (not general)

---

## Recommended Implementation Plan

**Phase 1: Quick Fix (Option 1)**
1. Add `discover_apim_operations()` to `api_p1_handler.py`
2. When artifact contains `/api-details#api=` patterns:
   - Extract API names
   - Construct `/developer/apis/{api}/operations` URLs
   - Fetch and parse APIM JSON
3. Test on MISO (should discover 20+ operations)

**Phase 2: Robust Solution (Option 3)**
1. Create dedicated `apim_probe` node
2. Trigger when Phase 0 detects APIM portal indicators
3. Systematically probe all APIs for operations
4. Merge results with Phase 1 findings

---

## Testing Plan

### Test 1: MISO with Enhanced api_p1_handler
**Expected:**
- 50+ operations discovered (pricing + load + interchange)
- Filtering: 50+ → 10-15 data operations
- Generator: Creates 10-15 scrapers (not 2)

### Test 2: Verify Operation Details
**Check:**
- Each operation has correct path, method, parameters
- Operations have full metadata (auth, response format, etc.)
- No duplicate operations

### Test 3: Filtering Still Works
**Verify:**
- Stage 1 filters auth/nav/system operations
- Stage 2 LLM classifies data vs metadata operations
- Stage 3 caps at max 5 per API (or configurable)

---

## Next Steps

1. **Immediate:** Document this issue for team review
2. **Short-term:** Implement Option 1 (quick fix for MISO)
3. **Long-term:** Implement Option 3 (robust APIM handling)
4. **Testing:** Re-run MISO analysis to verify 10+ operations discovered

---

## Impact on NEW_GRAPH_v2 Filtering

**Good News:**
The filtering implementation is correct! It successfully filtered 21 endpoints down to 2 data-relevant entries.

**Adjustment Needed:**
Once operations discovery is fixed:
- Input will be 50+ endpoints (operations, not catalog entries)
- Filtering should keep 10-15 data operations
- Generator will create 10-15 scrapers (one per operation)

**Config Adjustment:**
```python
max_endpoints_for_generation: int = 15  # Increase from 5 to 15 for APIM portals
```

This allows more granular scraper generation while still preventing explosion.

---

## Conclusion

The NEW_GRAPH_v2 filtering works correctly, but it's operating on the wrong input granularity. Once we fix operations discovery in api_p1_handler, the filtering will work on actual API operations instead of catalog entries, producing more useful scrapers.

**Status:** Ready for operations discovery fix implementation.
