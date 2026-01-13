# Unused Code Cleanup Summary

## Legacy Nodes (Replaced by planner_react in Phase B Architecture)

### 1. auth_probe.py ❌ UNUSED
- **Status**: Legacy - replaced by planner_react ReAct agent
- **Usage**: Only imported in nodes/__init__.py (not used in graph)
- **Action**: DELETE

### 2. fetcher.py ❌ UNUSED  
- **Status**: Legacy - replaced by planner_react ReAct agent
- **Usage**: Only imported in nodes/__init__.py (not used in graph)
- **Action**: DELETE

### 3. link_selector.py ✅ KEEP
- **Status**: ACTIVE - used by extract_links tool
- **Usage**: tools.py line 246 (AI filtering for >50 links)
- **Action**: KEEP

### 4. test_auth_probe.py ❌ MISPLACED
- **Status**: Test file in wrong location (should be in tests/)
- **Usage**: Tests auth_probe.py (which is being deleted)
- **Action**: DELETE

### 5. README files in nodes/ ❌ DOCUMENTATION CRUFT
- AUTH_PROBE_README.md
- FETCHER_README.md
- LINK_SELECTOR_README.md
- **Action**: DELETE (link_selector docs can move to link_selector.py docstring if needed)

## Files to Delete

```
agentic_scraper/business_analyst/nodes/auth_probe.py
agentic_scraper/business_analyst/nodes/fetcher.py
agentic_scraper/business_analyst/nodes/test_auth_probe.py
agentic_scraper/business_analyst/nodes/AUTH_PROBE_README.md
agentic_scraper/business_analyst/nodes/FETCHER_README.md
agentic_scraper/business_analyst/nodes/LINK_SELECTOR_README.md
```

## Files to Update

1. **agentic_scraper/business_analyst/nodes/__init__.py**
   - Remove auth_probe imports (lines ~13-19)
   - Remove fetcher imports (lines ~21-26)
   - Keep link_selector imports (still used)

## Impact Analysis

- ✅ No graph nodes affected (auth_probe/fetcher not in graph.py)
- ✅ No runtime impact (replaced by planner_react)
- ✅ Cleaner codebase (removes 3 legacy files + 3 READMEs)
- ✅ Reduces maintenance burden

