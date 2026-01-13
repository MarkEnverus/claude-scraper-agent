# Business Analyst TODO: Outstanding Issues

**Date**: January 13, 2026
**Source**: Code review feedback
**Status**: Needs Implementation

---

## Outstanding Architectural Issues

### 1. SPP Link Coverage - Extract_links() doesn't use portal extraction

**Location**: `agentic_scraper/business_analyst/tools.py:238`

**Issue**:
- `extract_links()` always uses `extract_comprehensive_data()` (no portal click-pass path)
- Planner prompt explicitly recommends `extract_links()` as the "faster" option
- If the agent picks it on SPP, we get top-nav links but miss real content links

**Impact**:
- SPP exploration can miss file-browser content depending on which tool planner chooses
- May not discover the actual data files/endpoints

**Recommended Fix**:
- Add portal extraction logic to `extract_links()` tool
- OR update planner prompt to recommend `render_page_with_js()` for portal sites
- OR make `extract_links()` check `is_portal_url()` and delegate to portal extractor

---

### 2. MISO Portal Classification - is_portal_url() doesn't match MISO

**Location**: `agentic_scraper/business_analyst/tools.py:17`

**Issue**:
- `is_portal_url()` only matches domains with "portal" or paths like `/groups/`
- MISO `data-exchange.misoenergy.org/api-details#api=...` does not match
- Falls back to `extract_comprehensive_data()` (no generic click-pass)

**Impact**:
- Missing left-side operation links on MISO API details pages
- Missing "API Definition" centered content
- May not discover all available operations

**Recommended Fix**:
- Add MISO-specific pattern to `is_portal_url()`:
  ```python
  if 'api-details' in url_lower or '/developer/apis/' in url_lower:
      return True
  ```
- OR add generic detection for APIM portal patterns
- Validate that portal extraction includes operations sidebar/tabs

---

### 3. max_depth Not Enforced - Only referenced in prompts, not code

**Location**: `agentic_scraper/business_analyst/nodes/planner_react.py`

**Issue**:
- `current_depth` is printed in prompts but never updated anywhere
- `BAConfig.max_steps` referenced in prompt but not used to stop exploration
- No hard enforcement of navigation depth limits

**Impact**:
- Stopping behavior governed by queue emptiness + LLM "stop" decision + recursion limit only
- `max_depth` config doesn't actually control depth
- Potential infinite loops or over-exploration

**Recommended Fix**:
- Track `current_depth` in state for each URL (distance from seed)
- Update depth when adding URLs to visit queue
- Enforce `max_depth` check before allowing navigation
- OR remove `max_depth` from config/prompts if not enforced
- Implement hard `max_steps` enforcement (count pages visited, stop when limit reached)

---

### 4. Vision for Portals - Portal extractor sets screenshot=None

**Location**: `agentic_scraper/business_analyst/tools.py:65`

**Issue**:
- `_adapt_portal_schema_to_standard()` sets `screenshot=None` in portal extractor path
- For SPP-classified-as-portal, vision may not run at all
- Vision model not utilized even when configured

**Impact**:
- Missing visual analysis for portal sites
- Can't leverage screenshot-based discovery for complex UIs
- May miss visual-only navigation elements

**Recommended Fix**:
- Keep screenshot in portal extractor results
- OR add separate screenshot capture step after portal extraction
- Ensure vision model is invoked for portal sites when `render_mode` allows it
- Test that SPP portal extraction includes screenshots

---

## Priority Order

1. **High**: Issue #2 (MISO Portal Classification) - Directly impacts MISO discovery
2. **High**: Issue #1 (SPP Link Coverage) - Directly impacts SPP discovery
3. **Medium**: Issue #3 (max_depth enforcement) - Code quality and config correctness
4. **Low**: Issue #4 (Vision for portals) - Enhancement, not blocking current objectives

---

## Related Files

- `agentic_scraper/business_analyst/tools.py` - Portal detection and extraction logic
- `agentic_scraper/business_analyst/nodes/planner_react.py` - Navigation depth tracking
- `agentic_scraper/business_analyst/config.py` - max_depth, max_steps configuration
- `agentic_scraper/business_analyst/state.py` - State management for depth tracking

---

## Testing Requirements

After fixes:
- [ ] Test MISO `data-exchange.misoenergy.org/api-details#api=pricing-api` discovers all operations
- [ ] Test SPP discovers file-browser content regardless of tool choice
- [ ] Test `max_depth=2` actually stops at depth 2
- [ ] Test `max_steps=10` actually stops after 10 pages
- [ ] Test portal sites capture screenshots when vision enabled
