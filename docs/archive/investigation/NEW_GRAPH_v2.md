# NEW_GRAPH_v2: BA → Validated Data Spec → Scraper Generation (with Guards)

**Date:** 2026-01-13  
**Audience:** Engineering (handoff to implementing agent)  
**Scope:** *New* LangGraph BA pipeline (`agentic_scraper/business_analyst/*`) + integration into scraper generation (`agentic_scraper/generators/*`)  

---

## 0) Executive Summary (What We’re Building)

We need two distinct outputs from the BA system:

1) **Audit output (exhaustive):** everything the BA discovered (including auth/nav/system noise) for debugging and traceability.  
2) **Generator input (validated + focused):** a **filtered, capped** set of *data-relevant* endpoints/links to feed the scraper generator without creating dozens of useless scrapers.

This document defines:
- How we classify sources (API vs WEBSITE vs FTP) and route the graph
- How we extract portal evidence reliably (Botasaurus issues + mitigations)
- How we produce a **Validated Data Spec** using **LLM-assisted ranking** with **deterministic guardrails**
- How we generate an **executive analysis** that focuses on data collection only
- How we A/B spike `agent-browser` as an extraction backend if Botasaurus remains unstable

---

## 1) Current Architecture (Facts From Repo)

### BA Graph (new system)
File: `agentic_scraper/business_analyst/graph.py`
- Nodes:
  - `planner_react` → tool-driven exploration
  - `analyst` → Phase 0 + Phase 1 extraction (vision + text)
  - `summarizer` → writes `site_report.json` and `site_report.md`
  - Optional routing: `website_p1` → `website_p2`, `api_p1` → `api_p2` gated by `--enable-p1-p2-routing`

### Outputs today
Files:
- `agentic_scraper/business_analyst/nodes/summarizer.py` writes to `outputs/<hostname>/site_report.json` and `outputs/<hostname>/site_report.md`
- CLI also supports writing a final `state.json` via `agentic_scraper/business_analyst/output.py` when `--output-dir` is used.

### Scraper generator expectations today
File: `agentic_scraper/generators/orchestrator.py`
- Expects `datasource_analysis/validated_datasource_spec.json` as input (or user provides it explicitly)
- Generates **one scraper per endpoint** when `len(endpoints) > 1` (this is a key risk)

### Executive summary generator exists but targets the old “ValidatedSpec”
File: `agentic_scraper/agents/ba_executive_summary_generator.py`
- Input: `ValidatedSpec` from `agentic_scraper/types/ba_analysis.py`
- The new graph does **not** produce `ValidatedSpec` today.

---

## 2) Non‑Negotiable Guardrails (Prevents “Looks Good” Failures)

1) **No hallucinated endpoints.** Every endpoint kept for generation must be grounded in:
   - extracted navigation links, or
   - captured network calls, or
   - explicit URLs/paths in extracted page content.

2) **LLM is not the only gate.** LLM can classify/rank, but code must enforce hard constraints:
   - cap number of generated endpoints
   - prevent auth/nav/system endpoints from being passed through by mistake
   - preserve audit trail of what was removed and why

3) **No explosion of scrapers.** The generator creates one scraper per endpoint today.
   - Passing 50 endpoints => 50 scrapers (unacceptable).
   - We must cap/group before generation.

4) **One PR per theme.**
   - PR1: Validated Data Spec generation (filtering + output files)
   - PR2: Extraction backend spike (`agent-browser`) behind a flag

---

## 3) Source Type Routing (API vs WEBSITE vs FTP)

### Current routing mechanism
File: `agentic_scraper/business_analyst/graph.py`
- Routes to P1 handlers based on:
  - `state.detected_source_type`
  - `state.detection_confidence >= 0.7`
  - feature flag: `BAConfig.enable_p1_p2_routing` (CLI: `--enable-p1-p2-routing`)

### Known classification pitfall (confirmed)
File: `agentic_scraper/business_analyst/prompts/phase0.py`
- “Landing Page Detection” currently biases **multi-API developer portals** to `WEBSITE` (this caused MISO misrouting historically).

### Required design rule (going forward)
We have two “WEBSITE-like” realities:

1) **WEBSITE_FILE_PORTAL**
   - has file-browser APIs / direct download links
   - P1 goal: discover download links and folder traversal routes

2) **WEBSITE_INTERACTIVE**
   - no file-browser URLs; data is behind JSON APIs and UI calls
   - P1 goal: discover *data APIs* via network calls and remove portal plumbing

**Important:** “WEBSITE” is too broad as a single branch. If SPP has no file-browser, WEBSITE P1 must not assume file-browser patterns.

---

## 4) Portal Extraction Reality Check (SPP Lessons)

### What we observed in the SPP run
- WEBSITE P1 executed ~37 times and found **0 file-browser-api URLs**.

This can mean either:
1) SPP truly does not expose file-browser calls in the pages we reached, or
2) our extraction pipeline is dropping them.

### Concrete extraction risk in current code
File: `agentic_scraper/tools/botasaurus_tool.py`
- `_capture_late_network_calls()` filters captured calls to those starting with `http`, which drops relative calls like `/file-browser-api/...` if the portal uses them.

### Required extraction mitigation
- Normalize network call URLs:
  - keep relative URLs and convert them to absolute using the page origin.
- Always record request URLs (not only URLs discovered inside JSON bodies).

---

## 5) Botasaurus Runtime Stability (P0 Reliability)

If runs take tens of minutes to hours, treat it as a runtime bug, not “site complexity”.

High-risk settings/patterns in this repo:
- `wait_for_complete_page_load=True` can hang on SPAs with long-polling / never-idle network.
- CDP response body parsing can explode runtime if many JSON responses are processed.
- Full-page screenshot via resizing window to `scrollHeight` can freeze on very tall/virtualized pages.

Required mitigations (minimum viable set):
1) Use bounded waits on portals; avoid “complete page load” semantics for SPAs.
2) Cap CDP response processing:
   - only first N responses (e.g., 25), and/or
   - only response URLs matching whitelist patterns (e.g., `file-browser-api`, dataset APIs).
3) Cap screenshot capture:
   - viewport-only or enforce a maximum height threshold.
4) If hangs persist: run extraction in a subprocess with a hard wall-clock timeout and return partial results with `extraction_error="timeout"`.

---

## 6) BA Output Strategy (Audit vs Generator)

### Output A: Audit (exhaustive, for debugging)
Already exists:
- `site_report.json` / `site_report.md`
- includes everything discovered (endpoints, nav pages, auth pages, etc.)

### Output B: Generator Input (validated + data-only)
**We must add this.**

Write a second artifact:
- `validated_datasource_spec.json` (generator input)
- optionally: `endpoint_inventory.json` (full categorized list + reasons)

This spec must:
- include only **data-relevant** endpoints/links for generation
- include auth posture + “how to get access” as metadata, not as endpoints to scrape
- include a cap (or grouping) to prevent generating dozens of scrapers

---

## 7) Endpoint Filtering (Hybrid: LLM Ranking + Deterministic Guards)

### Why “LLM-only” is not enough
Because the generator produces **one scraper per endpoint**.
If the model over-includes endpoints, we create dozens of scrapers, most useless.

### Proposed hybrid approach

#### Step 1: Deterministic pre-filter (small, stable list)
Drop only obvious junk:
- static assets (`.js`, `.css`, images/fonts)
- obvious auth flows (`/login`, `/signin`, `/signup`, `/logout`, `/oauth`, `/token`)
- obvious policy/docs plumbing (`/terms`, `/privacy`, `/sitemap`)

This list stays small and low-maintenance.

#### Step 2: LLM classification + ranking (the “smart” filter)
Ask the LLM to process the remaining candidates and output structured JSON:
- For each endpoint candidate:
  - `category`: `DATA` | `AUTH` | `NAV` | `SYSTEM` | `UNKNOWN`
  - `keep_for_generation`: boolean
  - `confidence`: 0.0–1.0
  - `reason`: evidence-based, referencing URL + relevant page/network evidence
- Additionally:
  - `top_endpoints_for_generation`: max N (e.g., 3–5)
  - `auth_notes`: token/signup URLs (metadata)

**Inputs to provide the LLM (context matters):**
- Seed URL + domain
- Candidate endpoints list
- `candidate_api_calls` from state (network calls)
- A short summary of top pages visited (URLs) and key evidence
- Explicit instruction: “Only keep endpoints that return data payloads relevant to the business objective.”

#### Step 3: Deterministic post-constraints (non-negotiable)
Even if the LLM says keep:
- Enforce max `N` endpoints passed to generator.
- Enforce scheme/format rules (http/https only; avoid HTML “pages” for API generator).
- Always preserve a full audit inventory:
  - `discarded_endpoints` with `category` + `reason`
  - never delete silently

---

## 8) Validated Data Spec: Minimal Schema (Generator-Compatible)

The generator validates only:
- `source`
- `source_type`
- `endpoints` (non-empty list)

But for good generation, include:
- `url` (seed URL)
- `datasource`, `dataset` (to avoid generator fallbacks)
- `authentication` (required/method/header/evidence)
- `executive_summary` (data-focused)
- `endpoints` (filtered + capped list; data endpoints only)
- `discarded_endpoints` (audit trail; not used for generation)

### Where to build/write it
Best location: `agentic_scraper/business_analyst/nodes/summarizer.py`
- It already aggregates final state and writes reports.
- It’s the right “integration seam” between BA and generator.

Also write the file when CLI `--output-dir` is used:
File: `agentic_scraper/business_analyst/output.py`

---

## 9) Executive Analysis (Data‑Focused)

We still want a high-level write-up, but it must focus on **data collection**, not portal plumbing.

Outputs:
- `site_report.md` remains a full stakeholder summary (existing).
- Add `executive_data_summary.md` (new) that focuses on:
  - what data is available (datasets / endpoints)
  - how to access it (auth requirements)
  - recommended collection method (API vs WEBSITE vs FTP)
  - a short list of **data endpoints** (the filtered list)

Implementation options:
1) **Use existing `summarizer_node` LLM markdown** but feed it the filtered spec (recommended).
2) Later: integrate `BAExecutiveSummaryGenerator` once we actually produce a compatible `ValidatedSpec` object.

---

## 10) Verification (What Counts as “Working”)

### MISO (API portal)
Pass criteria:
- `detected_source_type == API`
- filtered spec contains only real data endpoints (not `/signin`, `/products`, etc.)
- generator endpoints are capped (≤ N)

### SPP (portal)
Two acceptable outcomes:
1) WEBSITE_FILE_PORTAL: discovers file-browser/download links → WEBSITE P1 path
2) WEBSITE_INTERACTIVE: discovers data APIs via network calls → WEBSITE_INTERACTIVE path (to be implemented)

**Failure criteria:**
- No data endpoints/links discovered but many `/api/menu`/`/api/app-info` endpoints remain.

---

## 11) `agent-browser` Spike (A/B Backend, Not a Rewrite)

Use this if Botasaurus remains unstable or extraction remains incomplete for portals.

Feature flag:
- `BAConfig.browser_backend = "botasaurus" | "agent_browser"` (default botasaurus)

agent-browser subprocess flow:
```bash
agent-browser open <url>
agent-browser wait --load networkidle
agent-browser snapshot -i -c --json
agent-browser network requests --json
agent-browser screenshot <path>
agent-browser close
```

Success metrics:
- improves discovery of data-relevant calls/links on SPP-like portals
- no regression for MISO endpoint discovery

---

## 12) Implementation Checklist (What the next agent must deliver)

### PR1: Validated Data Spec + Data-Focused Executive Summary
1) Build endpoint candidates from state:
   - `state.endpoints` + `state.candidate_api_calls`
2) Deterministic pre-filter (small denylist: static/auth/policy)
3) LLM classify + rank to choose top N data endpoints
4) Deterministic caps + audit trail
5) Write:
   - `validated_datasource_spec.json`
   - `endpoint_inventory.json` (optional)
   - `executive_data_summary.md` (data-focused)

### PR2: Extraction Backend Spike (optional)
1) Add backend interface + feature flag
2) Implement `agent-browser` backend as subprocess wrapper
3) A/B test on SPP + MISO and record metrics

