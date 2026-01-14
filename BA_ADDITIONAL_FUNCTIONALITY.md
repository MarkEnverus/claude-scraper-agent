# BA Agent – Additional Functionality (Plugin-Inspired Enhancements)

This document proposes **concrete enhancements** to the local Business Analyst (BA) agent based on the `/discover-api` workflow from Rui Barros’ “data-journalism-marketplace” plugin.

It is written to be **agent-readable**: each enhancement includes (1) what exists today (with source pointers), (2) what to build, (3) where to implement, and (4) acceptance criteria.

## Work-In-Progress Notice (Unapproved Local Changes)

This workspace currently contains **unapproved, incomplete refactor work** that was started while exploring the “break compatibility” path you requested later.

If you are a follow-on agent, treat the section below as a **handoff + stop point** (what changed, what’s broken, what’s still required).

### Why “Backwards Compatible” Was Mentioned Earlier

The original recommendation to “add a new field (backwards compatible)” was about avoiding a multi-file break: historically, the BA pipeline treated network evidence as a **URL list** (`network_calls: List[str]`) and multiple components assumed that shape (e.g., artifact construction in `agentic_scraper/business_analyst/nodes/planner_react.py:420` and API-call extraction utilities). If you change the contract in only one place (tool output or state model), the graph breaks at runtime.

After you clarified “we’re still in dev, break behavior”, the refactor path switched to a **contract-breaking change** (replace URL lists with structured `network_events`) plus a set of coordinated updates across consumers.

### What Changed (Concrete, File-Scoped)

- `network_calls` → `network_events` contract change:
  - `PageArtifact` now stores `network_events: List[Dict[str, Any]]` instead of `network_calls: List[str]` (`agentic_scraper/business_analyst/state.py:119` to `agentic_scraper/business_analyst/state.py:136`).
  - `render_page_with_js` now returns `network_events` (portal adapter also emits `network_events`) (`agentic_scraper/business_analyst/tools.py:139` to `agentic_scraper/business_analyst/tools.py:218`).
  - `planner_react` now writes `PageArtifact(network_events=...)` and extracts candidate API URLs from events (`agentic_scraper/business_analyst/nodes/planner_react.py:420` to `agentic_scraper/business_analyst/nodes/planner_react.py:473`).
  - `analyst_node` now derives URL lists from network events before building the Phase 0 prompt (`agentic_scraper/business_analyst/nodes/analyst.py:160` to `agentic_scraper/business_analyst/nodes/analyst.py:170`).

- New “extract URLs from events” helper:
  - Added `urls_from_network_events(...)` utility (`agentic_scraper/business_analyst/utils/network_events.py:1`).
  - This exists because some utilities still accept `List[str]` inputs (see “Where Work Stopped / Remaining Tasks”).

- Network extraction refactor in Botasaurus:
  - Network capture is now event-based (`extract_network_events`) with `{url, initiator_type, trigger}` (`agentic_scraper/tools/botasaurus_tool.py:102` to `agentic_scraper/tools/botasaurus_tool.py:166`).
  - `extract_comprehensive_data` now returns `network_events` instead of `network_calls` (see return dict in `agentic_scraper/tools/botasaurus_tool.py:342` to `agentic_scraper/tools/botasaurus_tool.py:355`).

- API-call extraction now expects events:
  - `extract_api_calls_from_network_events(network_events, ...)` replaces the previous URL-list function (`agentic_scraper/business_analyst/utils/api_call_extractor.py:259` to `agentic_scraper/business_analyst/utils/api_call_extractor.py:306`).

- APIM logic now reads network evidence from events:
  - APIM detection checks patterns against URLs extracted from `artifact.network_events` (`agentic_scraper/business_analyst/nodes/api_p1_handler.py:100` to `agentic_scraper/business_analyst/nodes/api_p1_handler.py:105`).
  - APIM/OpenAPI fallback now passes URL lists derived from `artifact.network_events` into OpenAPI spec discovery (`agentic_scraper/business_analyst/nodes/api_p1_handler.py:533` to `agentic_scraper/business_analyst/nodes/api_p1_handler.py:541`).

- Website portal P1 now reads file-browser signals from events:
  - WEBSITE P1 derives file-browser URLs from `artifact.network_events` (`agentic_scraper/business_analyst/nodes/website_p1_handler.py:153` to `agentic_scraper/business_analyst/nodes/website_p1_handler.py:158`).

- Prompt shape changes:
  - `phase0_single_page_prompt` parameter renamed to `network_call_urls` (still a list of URLs for readability) (`agentic_scraper/business_analyst/prompts/phase0.py:10`).
  - `phase0_iterative_prompt` now expects each page dict to use `network_events` (and derives URLs from event dicts) (`agentic_scraper/business_analyst/prompts/phase0.py:175` to `agentic_scraper/business_analyst/prompts/phase0.py:207`).

- Tool rename for direct capture:
  - `capture_network_events` tool exists and uses `BotasaurusTool.extract_network_events` (`agentic_scraper/business_analyst/tools.py:289` to `agentic_scraper/business_analyst/tools.py:323`).

### APIM: What Was Added (Documentation + Implementation Wiring)

**Documentation (strategy guidance)**
- The “APIM improvements (without over-special-casing)” section was added to describe an APIM posture that treats APIM as “documentation”:
  - OpenAPI-first, APIM-operations-second (`BA_ADDITIONAL_FUNCTIONALITY.md:186`)
  - Stay focused on a selected API via `primary_api_name` (`BA_ADDITIONAL_FUNCTIONALITY.md:192`)
  - Generalize portal detection via adapters (APIM as one adapter) (`BA_ADDITIONAL_FUNCTIONALITY.md:196`)

**Implementation wiring (network evidence source change)**
- APIM detection + OpenAPI fallback now pull network evidence from `artifact.network_events` via URL extraction, not from `artifact.network_calls` (`agentic_scraper/business_analyst/nodes/api_p1_handler.py:100` and `agentic_scraper/business_analyst/nodes/api_p1_handler.py:535`).

### Where Work Stopped / Remaining Tasks

- Utility signatures still use older naming (`network_calls: List[str]`) even though the pipeline now stores events:
  - OpenAPI discovery still expects a URL list (`agentic_scraper/business_analyst/utils/openapi_parser.py:47` to `agentic_scraper/business_analyst/utils/openapi_parser.py:65`); current call sites pass URLs extracted from events (see API P1 handler at `agentic_scraper/business_analyst/nodes/api_p1_handler.py:535` to `agentic_scraper/business_analyst/nodes/api_p1_handler.py:540`).
  - File-browser URL extraction still expects a URL list (`agentic_scraper/business_analyst/utils/url_decoder.py:111` to `agentic_scraper/business_analyst/utils/url_decoder.py:152`); current call sites pass URLs extracted from events (see WEBSITE P1 at `agentic_scraper/business_analyst/nodes/website_p1_handler.py:153`).
  - Follow-on agent should decide whether to (A) keep these utilities “URL-list based” and always adapt at boundaries, or (B) refactor them to accept events directly.

- Late-call capture is still URL-list based:
  - Botasaurus still has `_capture_late_network_calls(...)-> list[str]` (see `agentic_scraper/tools/botasaurus_tool.py:2469` in repo search results). This was not migrated into structured events, so event capture is not fully unified.

- Tests and deletions need review:
  - There are extensive uncommitted changes reported in `git status --porcelain` (example: modified BA agent files plus deleted `docs/archive/investigation/*` and deleted `sourcing/scraping/*`). A follow-on agent should verify whether those deletions are intentional; if not, revert them before continuing the refactor.

### Workspace Status Snapshot (For Follow-On Agent)

At time of writing, `git diff --stat` shows large churn (including deletions), and `git status --porcelain` includes:
- Modified: `agentic_scraper/business_analyst/nodes/analyst.py`, `agentic_scraper/business_analyst/nodes/api_p1_handler.py`, `agentic_scraper/business_analyst/nodes/planner_react.py`, `agentic_scraper/business_analyst/nodes/website_p1_handler.py`, `agentic_scraper/business_analyst/prompts/phase0.py`, `agentic_scraper/business_analyst/state.py`, `agentic_scraper/business_analyst/tools.py`, `agentic_scraper/business_analyst/utils/api_call_extractor.py`, `agentic_scraper/tools/botasaurus_tool.py`, `tests/business_analyst/test_tools.py`
- Deleted: multiple `docs/archive/investigation/*.md` and `sourcing/scraping/*` files (verify whether accidental)
- Untracked: `BA_ADDITIONAL_FUNCTIONALITY.md`, `agentic_scraper/business_analyst/utils/network_events.py`, plus other local files

Follow-on agent should re-run:
- `git status --porcelain`
- `git diff --stat`

## Source Inputs (Grounding)

- `/discover-api` workflow emphasizes **interactive UI-driven discovery + network monitoring**:
  - Open + snapshot + identify controls, then trigger requests via search/filters/pagination/exports, then document endpoints/params/pagination/auth (`https://raw.githubusercontent.com/ruimgbarros/data-journalism-marketplace/main/plugins/slash-commands/discover-api/discover-api.md`).
- Our BA agent is a LangGraph workflow with planner→analyst→specialized API/website handlers→summarizer (`BA_AGENT_FLOW.md:1`, `agentic_scraper/business_analyst/graph.py:56`).

## Current BA Agent Capabilities (Facts From This Repo)

### Evidence capture (page render + links + network calls)

- `render_page_with_js` returns `full_text`, `markdown`, `navigation_links`, and `network_events` (`agentic_scraper/business_analyst/tools.py:127`).
- Botasaurus “comprehensive extraction” explicitly expands collapsible sections, extracts nav links, captures network calls, and produces markdown (`agentic_scraper/tools/botasaurus_tool.py:188` to `agentic_scraper/tools/botasaurus_tool.py:259`).
- For website-like portals, Botasaurus additionally captures CDP JSON responses and extracts URLs from them (`agentic_scraper/tools/botasaurus_tool.py:2041` to `agentic_scraper/tools/botasaurus_tool.py:2103`).

### “No hallucination” constraint

- Phase 0 prompt includes explicit “NO HALLUCINATION / NO GUESSING” rules (`agentic_scraper/business_analyst/prompts/phase0.py:48`).

### OpenAPI/Swagger support

- We scan links/network calls/text for common OpenAPI/Swagger spec URLs and fetch/parse JSON/YAML (`agentic_scraper/business_analyst/utils/openapi_parser.py:47`, `agentic_scraper/business_analyst/utils/openapi_parser.py:108`).
- Parser supports OpenAPI 3.x and Swagger 2.0 basics (`agentic_scraper/business_analyst/utils/openapi_parser.py:182`).

### APIM support (already present, but can be strengthened)

- API P1 handler includes Azure APIM portal detection heuristics (`agentic_scraper/business_analyst/nodes/api_p1_handler.py:78`).
- It extracts API names from URLs like `#api=pricing-api` and `/apis/{name}` (`agentic_scraper/business_analyst/nodes/api_p1_handler.py:45`).
- It attempts to fetch APIM operations JSON at `/developer/apis/{api_name}/operations` (`agentic_scraper/business_analyst/nodes/api_p1_handler.py:115`).
- Planner pipeline prioritizes “APIM calls” from network traffic (implementation referenced at call site) (`agentic_scraper/business_analyst/nodes/planner_react.py:465` to `agentic_scraper/business_analyst/nodes/planner_react.py:471`).
- The BA CLI extracts a `primary_api_name` from URL fragment `#api=...` to keep focus when a portal lists multiple APIs (`agentic_scraper/business_analyst/cli.py:31` to `agentic_scraper/business_analyst/cli.py:59`), and prompts include focus controls (`agentic_scraper/business_analyst/prompts/phase0.py:35` to `agentic_scraper/business_analyst/prompts/phase0.py:44`).

### Output artifacts (already closer to “deliverables” than the plugin)

- Summarizer writes structured outputs including `validated_datasource_spec.json` and `endpoint_inventory.json` (`agentic_scraper/business_analyst/nodes/summarizer.py:472`, `agentic_scraper/business_analyst/nodes/summarizer.py:588`).
- `save_results` copies those artifacts into a user-selected output directory (`agentic_scraper/business_analyst/output.py:114`).

## Key Gap vs `/discover-api`: Interaction-Driven Discovery

The plugin workflow explicitly instructs agents to **interact with the UI** (search forms, date pickers, pagination, filters, export buttons) while monitoring network requests (`discover-api.md` “Step 2: Interaction and Monitoring”).

In this repo, we capture network calls during render and by expansion, but we do **not** expose an explicit, repeatable “interaction script” primitive in `agentic_scraper/business_analyst/tools.py` (tool list in `agentic_scraper/business_analyst/tools.py:445`).

## Enhancements (Proposed Work Items)

### E1 (P0): Add “Interaction Script” Tool to Trigger Network Calls

**Goal**
Trigger additional network calls by performing deterministic UI actions (type, click, select, paginate), then return **captured network evidence**.

**Why (Grounded)**
`/discover-api` expects endpoint discovery to happen during interactive actions (filters/pagination/exports) (`discover-api.md` Step 2).

**What exists today**
- We can render and capture network events on load (`agentic_scraper/business_analyst/tools.py:127`).
- Botasaurus already expands collapsible sections (`agentic_scraper/tools/botasaurus_tool.py:239`).

**Design**
- Add a new LangChain tool, e.g. `interact_and_capture(url, actions: list[dict]) -> dict`, that:
  - Navigates to `url`
  - Executes `actions` sequentially (click/type/select/scroll)
  - Captures resulting network events (and optionally response metadata)
  - Returns updated `network_events`, and optionally a screenshot and extracted text/markdown

**Where to implement**
- Tool wrapper: `agentic_scraper/business_analyst/tools.py` (new `@tool`).
- Botasaurus primitive: extend `BotasaurusTool` with an interaction runner that can:
  - find elements by CSS selector / text
  - run JS events
  - wait after actions
  - capture network events after actions
  - (Botasaurus already runs JS, extracts text, and captures network events; this builds on those patterns in `agentic_scraper/tools/botasaurus_tool.py:188`.)

**State / evidence changes**
- Minimum: append new events to `PageArtifact.network_events` (`agentic_scraper/business_analyst/state.py:119`).

**Acceptance criteria**
- Given a portal page where a search/pagination action triggers XHR, `interact_and_capture` returns new network call URLs not present after the initial render.
- The BA agent can call the tool from `planner_react` and feed the result into artifact creation flow (pattern already exists for `render_page_with_js` in `agentic_scraper/business_analyst/nodes/planner_react.py:415`).

### E2 (P0): Store Structured Network Evidence (Beyond URL Strings)

**Goal**
Upgrade evidence capture from `List[str]` URLs to **structured request/response metadata** needed to document endpoints (method, query/body, status, content-type).

**Why (Grounded)**
The plugin deliverables require method, parameters, pagination mechanism, auth, etc. (`discover-api.md` Step 3).

**What exists today**
- `PageArtifact.network_events` is `List[Dict[str, Any]]` with at least `url` (`agentic_scraper/business_analyst/state.py:119`).
- `EndpointFinding` has parameter storage and Phase 1.5 enrichment exists (`agentic_scraper/business_analyst/state.py:152`, `agentic_scraper/business_analyst/nodes/param_p15_handler.py:24`).

**Design**
- Replace `PageArtifact.network_calls: List[str]` with `PageArtifact.network_events: list[dict]` with keys:
  - `url`, `method` (optional), `request_headers` (optional), `request_body` (optional)
  - `status` (optional), `response_headers` (optional), `content_type` (optional)
  - `observed_at` (optional timestamp), `trigger` (“page_load”, “expand_sections”, “interaction_script”)

**Where to implement**
- Data model: `agentic_scraper/business_analyst/state.py` (add field).
- Botasaurus capture: likely in CDP hooks used in website extraction (`agentic_scraper/tools/botasaurus_tool.py:2041`), and/or internal network extraction method used by `extract_comprehensive_data` (`agentic_scraper/tools/botasaurus_tool.py:247`).
- Planner artifact build: extend `agentic_scraper/business_analyst/nodes/planner_react.py:420` to store the new field.

**Acceptance criteria**
- For captured calls, the BA agent can produce (at least) URL + method + status in the final audit output.

### E3 (P0): Propagate Parameter Metadata Into Generator Inputs

**Goal**
Don’t throw away Phase 1.5 parameter enrichment when writing `validated_datasource_spec.json`.

**Why (Grounded)**
- Phase 1.5 explicitly enriches parameters for accurate generation (`agentic_scraper/business_analyst/nodes/param_p15_handler.py:3` to `agentic_scraper/business_analyst/nodes/param_p15_handler.py:11`).
- Current conversion to generator schema sets parameters to `{}` (`agentic_scraper/business_analyst/nodes/summarizer.py:455` to `agentic_scraper/business_analyst/nodes/summarizer.py:469`) despite `EndpointDetails.parameters` being a typed field (`agentic_scraper/types/ba_analysis.py:174` to `agentic_scraper/types/ba_analysis.py:189`).

**Design**
- Convert `EndpointFinding.parameters: List[Dict]` (`agentic_scraper/business_analyst/state.py:152`) into `EndpointDetails.parameters: dict[str, Parameter]` (`agentic_scraper/types/ba_analysis.py:133`).
- Preserve: name/type/required/description + enriched fields (format/example/default/enum/min/max/pattern) where available.

**Where to implement**
- `convert_endpoint_finding_to_details` in `agentic_scraper/business_analyst/nodes/summarizer.py:398`.

**Acceptance criteria**
- When Phase 1.5 runs and enriches parameters, `validated_datasource_spec.json` includes those parameters per endpoint (not empty dicts).

### E4 (P1): Add an “API_DOCUMENTATION.md”-style Output Artifact

**Goal**
Produce a dedicated API reference document similar to the plugin’s `API_DOCUMENTATION.md` deliverable, but grounded in our already-produced structured artifacts.

**Why (Grounded)**
The plugin explicitly emits a clean markdown API reference with endpoints/auth/pagination/examples (`discover-api.md` “Deliverables”, plus `README.md:73`).

**What exists today**
- We already write:
  - `endpoint_inventory.json` (audit) (`agentic_scraper/business_analyst/nodes/summarizer.py:588`)
  - `validated_datasource_spec.json` (generator input) (`agentic_scraper/business_analyst/nodes/summarizer.py:472`)
  - `site_report.md` (executive) (`agentic_scraper/business_analyst/nodes/summarizer.py:889`)

**Design**
- Add a new writer `write_api_documentation_md(...)` that renders:
  - Base URL + auth summary
  - Per-endpoint: method, URL/path, parameters (from E3), response format
  - Notes for pagination/auth/rate-limits when known (or “unknown” when not)
- Output path aligned to our outputs dir (e.g. `outputs/{hostname}/API_DOCUMENTATION.md`).

**Where to implement**
- `agentic_scraper/business_analyst/nodes/summarizer.py` near other writers (`agentic_scraper/business_analyst/nodes/summarizer.py:472`).

**Acceptance criteria**
- `outputs/{hostname}/API_DOCUMENTATION.md` is generated and is fully derived from `FilteringResult` + `EndpointFinding` data (no invented endpoints).

### E5 (P1): Make “Robots / Rate Limit” Handling Operational (Not Just Noted)

**Goal**
If configured, actively fetch robots.txt and use its results during exploration/decisioning.

**What exists today**
- Config fields exist (`agentic_scraper/business_analyst/config.py:34`, `agentic_scraper/business_analyst/config.py:43`).
- Tool exists to fetch/parse robots (`agentic_scraper/business_analyst/tools.py:361`).

**Design**
- When `config.respect_robots` is true:
  - call `http_get_robots` early in `planner_react`
  - store `robots_disallowed` / disallowed paths in state (field exists in state comments but enforcement needs confirming) (`agentic_scraper/business_analyst/state.py:29` mentions `robots_disallowed` in grep results; if missing in TypedDict, add it consistently)
  - use it as a hard filter for candidate URLs

**Where to implement**
- `agentic_scraper/business_analyst/nodes/planner_react.py` (decisioning + link scoring pipeline).

**Acceptance criteria**
- With `respect_robots=True`, the agent does not enqueue or visit disallowed paths for `User-agent: *` returned by `http_get_robots`.

## APIM Enhancement Notes (Grounded + Aligned With “APIM is Documentation”)

You noted: “APIM = Microsoft Azure API Management portal (just a documentation site, nothing special).”

Grounded view from this repo:
- We currently **treat APIM as a recognizable documentation portal pattern** and optionally extract operations metadata if the portal exposes it (`agentic_scraper/business_analyst/nodes/api_p1_handler.py:78` and `agentic_scraper/business_analyst/nodes/api_p1_handler.py:115`).

### APIM improvements (without over-special-casing)

1. **Use OpenAPI-first, APIM-operations-second**
   - We already have robust OpenAPI/Swagger parsing (`agentic_scraper/business_analyst/utils/openapi_parser.py:47`).
   - APIM portals sometimes link to OpenAPI specs; keep searching links/network evidence/page text for specs first, then use operations JSON as a fallback/augmentation.

2. **Stay focused on the user-selected API within APIM catalogs**
   - Continue to leverage `primary_api_name` extraction from `#api=...` (`agentic_scraper/business_analyst/cli.py:31`).
   - Ensure Phase 0 focus controls are always applied when `primary_api_name` is present (`agentic_scraper/business_analyst/prompts/phase0.py:35`).

3. **Generalize “portal pattern detection” beyond APIM**
   - Today, APIM detection is based on URL patterns and network call markers (`agentic_scraper/business_analyst/nodes/api_p1_handler.py:92`).
   - Create a registry of “documentation portal adapters” with:
     - detection heuristics
     - spec discovery strategy (OpenAPI/Swagger/WADL/etc.)
     - optional machine-readable metadata endpoints (like APIM operations JSON)
   - Keep APIM as one adapter, not a hard-coded special case.

## Other Major API Documentation Styles (Current + Proposed)

### Current (facts)
- OpenAPI / Swagger JSON/YAML: supported (`agentic_scraper/business_analyst/utils/openapi_parser.py:108`).
- Swagger 2.0: supported via `swagger` + `securityDefinitions` parsing (`agentic_scraper/business_analyst/utils/openapi_parser.py:210` to `agentic_scraper/business_analyst/utils/openapi_parser.py:233`).

### Proposed (extensions)
- If you want broader “major styles” coverage, add parsers/adapters incrementally, driven by evidence:
  - Extend spec URL detection patterns (similar to `find_openapi_spec_urls`) and add new parser modules.
  - Only claim support for a format when there is a parser + tests + confirmed examples in outputs.

## Implementation Checklist (For Another Agent)

- [ ] E1: Add `interact_and_capture` tool; wire into `planner_react` artifact ingestion.
- [ ] E2: Add `network_events` to `PageArtifact`; capture method/status/content-type where possible.
- [ ] E3: Map `EndpointFinding.parameters` → `EndpointDetails.parameters` in `convert_endpoint_finding_to_details`.
- [ ] E4: Add `write_api_documentation_md` output (derived from existing artifacts; no hallucination).
- [ ] E5: Enforce `respect_robots` using `http_get_robots` during planning and link enqueueing.
- [ ] APIM: Refactor portal detection into adapters; keep APIM as one adapter with OpenAPI-first strategy.
