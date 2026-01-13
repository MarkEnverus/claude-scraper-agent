# Integration Handoff: Phase‑0 Detection + P1/P2 Routing + Extraction Spike

**Date:** January 13, 2026  
**Priority:** HIGH (P0 routing correctness, P1 extraction improvement)  
**Audience:** Next implementing agent  

---

## 1) Problem Statement (Business Objective vs Current Behavior)

### Business objective
For a given seed, discover *actual* data interfaces:
- **API sources:** real REST endpoints/specs/operations
- **WEBSITE portal sources:** real dataset download paths (file-browser style), not site plumbing
- **FTP sources:** directory/file listing + download targets

### Observed failure mode
MISO‑style API portals (developer portals listing multiple APIs) are frequently classified as `DataSourceType.WEBSITE` and routed into WEBSITE P1/P2 handlers. WEBSITE P1 expects file-browser/download hierarchies and fails on API portals.

---

## 2) Root Cause (Confirmed in Code)

### Prompt bias forces API portals → WEBSITE
File: `agentic_scraper/business_analyst/prompts/phase0.py`

The Phase‑0 prompt contains a “Landing Page Detection” rule that explicitly instructs the model:
- If page looks like a **Developer Portal / API Catalog / Browse APIs** and lists multiple APIs
- Then classify it as **WEBSITE** (with confidence ~0.6–0.8)

This is structurally incompatible with P1/P2 routing semantics:
- WEBSITE P1 is for file-browser/download hierarchies.
- API P1 is for specs/operations/OpenAPI/APIM-style pages.

**Conclusion:** even if the LLM is “doing what it was told”, the graph routes incorrectly.

---

## 3) Non‑Negotiable Guardrails (Hallucination Reduction + Scope Control)

1. **No prompt-only fixes.** Prompts can guide, but routing must be resilient to LLM variance.
2. **No invented endpoints.** Every endpoint must be grounded in:
   - extracted page content, or
   - extracted navigation links, or
   - captured network calls.
3. **No random clicking.** Any UI interaction must be deterministic and logged.
4. **One PR per theme.**
   - PR1: classification + routing correctness
   - PR2: extraction backend spike behind a flag

---

## 4) P0: Fix Phase‑0 Classification (Prompt + Deterministic Backstop)

### 4.1 Prompt changes (required but not sufficient)
File: `agentic_scraper/business_analyst/prompts/phase0.py`

**Change “Landing Page Detection”** from:
- “Developer portal landing pages are WEBSITE until you reach docs”
to:
- “Developer portal landing pages are **API sources** (API management portals).”

Add modern API-portal signals (explicitly):
- hash routing patterns: `#api=...`, `#/apis/`, `#!/...`
- APIM-style URLs: `/developer/apis/`, `/operations`, `/products`
- spec markers: `/openapi`, `/swagger`, `/api-docs`
- REST markers: `/v1/`, `/v2/`, `/graphql`

**Important guardrail:** do not introduce a rule that flips to API based on the word “API” alone. Require a hard signal in links/network calls/content.

### 4.2 Deterministic backstop (mandatory)
File: `agentic_scraper/business_analyst/nodes/analyst.py`

After Phase‑0 returns `Phase0Detection`, apply an evidence-based correction:

If the model returns `WEBSITE` but:
- there are **no** file-browser/download signals (examples):
  - no `file-browser-api` URLs in `artifact.network_calls`
  - no download-like links (`.csv`, `.xlsx`, `.zip`, etc.)
AND
- there **are** strong API portal signals (examples):
  - `/developer/apis/`, `/operations`
  - `/openapi`, `/swagger`, `/api-docs`
  - `/v1/`, `/v2/`, `/graphql`

Then:
- coerce `detected_type = DataSourceType.API`
- set confidence to a bounded value (e.g., `0.75–0.9`)
- append an indicator such as: `"Coerced to API: APIM/REST signals present; no WEBSITE download evidence"`

**Why this exists:** prevents routing regressions if prompt changes drift later.

---

## 5) P0: P1/P2 Routing Must Be End-to-End Functional

### 5.1 Required state fields
File: `agentic_scraper/business_analyst/state.py`
- `detected_source_type`
- `detection_confidence`
- `last_analyzed_url` (P1 needs artifact context after analyst clears `current_url`)

### 5.2 Analyst must persist routing inputs
File: `agentic_scraper/business_analyst/nodes/analyst.py`
On successful analysis, return:
- `detected_source_type = phase0_result.detected_type` (or coerced type)
- `detection_confidence = phase0_result.confidence` (or adjusted)
- `last_analyzed_url = current_url`

### 5.3 P1 handlers must consume `last_analyzed_url`
Files:
- `agentic_scraper/business_analyst/nodes/website_p1_handler.py`
- `agentic_scraper/business_analyst/nodes/api_p1_handler.py`

Requirement:
- Pull artifact using `last_analyzed_url` and never rely on `current_url` being present post-analyst.

### 5.4 P2 must be able to terminate the graph
File: `agentic_scraper/business_analyst/graph.py`

Requirement:
- When P2 validation passes (sets `p2_complete=True` and `next_action="stop"`), graph must route to `summarizer` (or `END`), not always back to planner.

### 5.5 CLI must support enabling P1/P2
File: `agentic_scraper/business_analyst/cli.py`
- Provide flag: `--enable-p1-p2-routing`
- Wire into `BAConfig(enable_p1_p2_routing=...)`

---

## 6) Known Footguns (Fix or Remove)

### 6.1 Planner tool output ingestion
The planner exposes tools, but any tool whose output is ignored by ingestion creates “dead turns”.

Action:
- Either ensure `extract_links` tool results affect the queue/state, or remove it from the planner tool list to avoid silent no-op exploration.

### 6.2 Botasaurus runtime stability (can block verification)
If portal runs take extremely long (tens of minutes to hours), treat it as a **P0 runtime bug**, not “site complexity”.

The main high-risk Botasaurus settings/patterns in this repo:
- `wait_for_complete_page_load=True` on `Driver(...)` can hang indefinitely on SPAs with long-polling or never-idle network.
- CDP response-body parsing loops can be unbounded if the page triggers many JSON responses:
  - `network.get_response_body()` + `json.loads()` + recursive URL extraction across many responses can explode runtime.
- Full-page screenshot via resizing to `scrollHeight` is risky (huge heights can freeze/consume memory):
  - `driver.set_window_size(..., document.body.scrollHeight)` can be extremely slow on infinite/virtualized pages.

Required mitigations (pick the minimal set that makes runs reliable):
1. Prefer `wait_for_complete_page_load=False` for SPA/portal extraction and control readiness with bounded waits.
2. Cap CDP processing:
   - process only first N responses (e.g., 25), and/or
   - only process responses whose URL matches a whitelist (e.g., `file-browser-api`, `download`, `.json` of known shape).
3. Cap screenshot work:
   - take viewport screenshot only, or
   - enforce a max height (e.g., 15000px) and skip full-height capture above that.
4. Add a hard timeout wrapper around Botasaurus extraction (recommended if hangs persist):
   - run extraction in a subprocess with a max wall-clock budget and kill on timeout,
   - return partial results with `extraction_error="timeout"` rather than blocking the entire graph.

---

## 7) Verification Plan (No Guessing, Evidence Only)

Use Bedrock SSO env:
```bash
AWS_PROFILE=genai-power-user AWS_SDK_LOAD_CONFIG=1 AWS_EC2_METADATA_DISABLED=true
```

### Test A (MISO): must route to API P1
```bash
agentic-scraper analyze "https://data-exchange.misoenergy.org/api-details#api=pricing-api" \
  --max-depth 2 \
  --output-dir ./outputs_verification/miso \
  --enable-p1-p2-routing \
  --debug
```

Pass criteria:
- Logs show Phase‑0 type is API (or a logged coercion to API).
- Logs show: `Routing to API P1 handler`.
- Output contains real API endpoints (e.g., `https://apim.misoenergy.org/pricing/v1/...`).

### Test B (SPP): must route to WEBSITE P1
```bash
agentic-scraper analyze "https://portal.spp.org/groups/integrated-marketplace" \
  --max-depth 2 \
  --output-dir ./outputs_verification/spp \
  --enable-p1-p2-routing \
  --debug
```

Pass criteria:
- Logs show: `Routing to WEBSITE P1 handler`.
- WEBSITE P1 discovers `file-browser-api` URLs and/or download URLs.
- WEBSITE P2 validates and can terminate (or continues with actionable gaps).

### Proof artifacts required (reject “it works” without these)
For each test:
- `outputs_verification/<site>/state.json`
- `outputs_verification/<site>/site_report.json`
- Grep snippets:
  - `Phase 0 complete: Type=...`
  - `Routing to ... P1 handler`
  - P2 stop reason (if validated)

---

## 8) P1 Spike: Evaluate `agent-browser` as an A/B Extraction Backend (PR2)

### Goal
Improve extraction on SPA portals (SPP-style) by using deterministic accessibility snapshots with stable element refs + explicit network request capture.

### Constraints
- Must be behind a feature flag (no behavior change by default).
- Must return the existing normalized schema used by downstream:
  - `full_text`, `markdown`, `navigation_links`, `network_calls`, `screenshot`.
- No “random clicks”. If you interact, click only deterministic refs extracted from `snapshot --json`, and log every ref clicked.

### Minimal integration approach
1. Add `BAConfig.browser_backend: "botasaurus" | "agent_browser"` (default `"botasaurus"`).
2. Introduce a backend wrapper used by `render_page_with_js` (and any network capture tool):
   - Botasaurus backend: current implementation
   - Agent-browser backend: subprocess driver

### Agent-browser subprocess flow
```bash
agent-browser open <url>
agent-browser wait --load networkidle
agent-browser snapshot -i -c --json
agent-browser network requests --json
agent-browser screenshot <path>
agent-browser close
```

### Spike success metrics
- SPP: materially higher count of file-browser paths and download links vs baseline.
- MISO: no regression in endpoint discovery.
