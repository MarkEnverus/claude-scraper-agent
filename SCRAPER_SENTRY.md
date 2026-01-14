# Sentry Integration for Agentic Scraper - Implementation Specification

**Date**: January 13, 2026
**Status**: READY FOR IMPLEMENTATION
**Branch**: code-migration
**Scope**: Generator stack + fixer/updater + shared infra (sourcing/commons) + Sentry instrumentation

---

## 0) Non-Negotiables / Guardrails (read first)

- Do not "half-integrate" Sentry (e.g., capture_exception sprinkled around) without centralized init and scrubbing. That creates noise + leaks secrets.
- Do not introduce Sentry into BA graph in this PR unless explicitly requested. This handoff is generation/fix/update + generated scrapers runtime.
- Keep changes behind env flags: if no DSN, Sentry must be a no-op.
- Never send secrets to Sentry:
    - redact API keys (Authorization, Ocp-Apim-Subscription-Key, cookies)
    - redact query params that may contain tokens
- Keep PRs tight:
    - PR1: infra path resolution unblock (if not already done by other agent)
    - PR2: Sentry integration (commons + generator + fixer/updater + templates)
- Avoid repo-wide renames (sourcing/ stays as-is for now).

---

## 1) Current State (Facts from codebase)

### 1.1 Generator is Bedrock/LangChain-based (not LangGraph)

- agentic_scraper/generators/orchestrator.py:
    - Uses LLMFactory (Bedrock ChatBedrockConverse), creates HybridGenerator.
    - Multi-endpoint spec => generates one scraper per endpoint.
- agentic_scraper/generators/hybrid_generator.py:
    - Uses LLMFactory.create_reasoning_model() and factory.invoke_structured(...) to produce code blocks.
    - Renders Jinja templates via TemplateRenderer and writes main.py, tests/test_main.py, README.md, INTEGRATION_TEST.md.

### 1.2 Fixer/updater exist but are partially placeholders

- agentic_scraper/fixers/fixer.py
    - Applies deterministic string replacements and "marks validation passed" without actual QA execution.
- agentic_scraper/fixers/updater.py
    - Detects generator type but regeneration is a placeholder ("Would regenerate scraper").
    - Updates version metadata.

### 1.3 Sentry is not integrated in this repo

- rg -n "sentry" returns nothing in this workspace.
- No sentry_sdk imports in generator/fixer/updater.

### 1.4 Infra mismatch blocks generator init (important)

- ScraperOrchestrator() currently fails on init in this repo due to expecting ./commons (repo root).
- Your actual infra is under ./sourcing/commons and/or ./sourcing/scraping/commons.
- This must be fixed (or already being fixed by another agent) before end-to-end generator testing is meaningful.

---

## 2) Goals

1. Make Sentry available to:
    - generated scrapers at runtime
    - generator/orchestrator pipeline
    - fixer/updater pipeline
2. Provide consistent tags + context so you can answer:
    - which datasource/dataset/endpoint is failing
    - whether failure is generation-time or runtime
    - what infra version produced the scraper
3. Preserve local-first UX:
    - no DSN => no Sentry overhead
    - Sentry errors should not prevent scraper execution

---

## 3) What to Track (Recommended Observability Model)

### 3.1 Core Tags (apply everywhere)

Set these tags on events:

- app: agentic-scraper
- component: generator | orchestrator | fixer | updater | collector
- datasource: from BA spec (datasource or derived)
- dataset: from BA spec (dataset)
- endpoint_id: when single-endpoint scraper
- source_type: API|WEBSITE|FTP|EMAIL
- infrastructure_version: from templates / metadata
- scraper_version: from templates / metadata
- repo: optional (if you have monorepo id)
- env: dev|staging|prod
- release: git sha or build version if available

### 3.2 Errors (what should be events)

- Unhandled exceptions in:
    - collect_content
    - validate_content
    - CLI entrypoints / main collector run
- Generation failures:
    - invalid BA spec
    - template rendering failures
    - code validation failures (CodeValidator critical errors)
    - infra copy failures
- Update/fix failures:
    - "generator detection failed"
    - file I/O failures
    - validation failures (when real QA gets implemented)

### 3.3 Breadcrumbs (high-value, low-noise)

Add breadcrumbs:

- HTTP requests (method, host, path) — but do not include headers or full query strings.
- Retry attempts and backoff decisions.
- For API scrapers: a breadcrumb for "candidate url built" (with redacted query).

### 3.4 Performance (optional but useful)

- Use Sentry performance tracing only if you're ready:
    - collect_content span
    - validate_content span
    - generator spans: transform, llm_collect, llm_validate, render, write_files

Start with errors only; add tracing later.

---

## 4) Redaction / PII & Secret Handling (Required)

Implement a shared scrubber in one place:

- Redact headers:
    - Authorization
    - Cookie
    - Set-Cookie
    - X-API-Key and variants
    - Ocp-Apim-Subscription-Key
- Redact query parameters by name:
    - token, access_token, refresh_token, apikey, api_key, key, sig, signature, session, code
- Consider removing the entire query string from captured URLs by default (store only scheme://host/path), and keep a separate local debug log if needed.

---

## 5) Where to Implement Sentry (Architecture)

### 5.1 Add to shared infra (preferred)

Create a shared helper in sourcing/commons so every generated scraper can use it without duplicating logic:

- File: sourcing/commons/sentry_utils.py
- Expose:
    - init_sentry(dsn: str | None, environment: str, release: str | None, tags: dict)
    - sentry_configured() -> bool
    - capture_exception(e, extra: dict = None, tags: dict = None)
    - add_breadcrumb(...)
- This also lets fixer/updater/generator reuse the same behavior if they import from sourcing.commons.

### 5.2 Update generator templates to call init_sentry

In templates (likely agentic_scraper/templates/scraper_main.py.j2):

- On program start / class init:
    - read SENTRY_DSN, SENTRY_ENV, SENTRY_RELEASE
    - call init_sentry(...) if DSN set
- Set tags from template vars:
    - datasource/dataset/infrastructure_version/scraper_version/etc.

### 5.3 Instrument generator/orchestrator/fixer/updater

- Generator/Orchestrator:
    - Initialize Sentry at top of CLI run or orchestrator init (DSN from env).
    - Wrap major stages with try/except that calls capture_exception and re-raises (so CLI still fails properly).
- Fixer/Updater:
    - Same pattern: init once per run; capture exceptions and tag scraper_path, generator_agent, old_version, target_version.

---

## 6) Compatibility Note: "Use existing Sentry patterns"

You referenced: /Users/mark.johnson/Desktop/source/repos/enverus-pr/pr.prt.sourcing/sourcing/scraping.
I cannot read that path from this workspace. The implementing agent should:

- copy the existing Sentry bootstrap pattern from that repo if it exists
- otherwise follow Sentry's Python SDK best practices:
    - sentry_sdk.init(...)
    - before_send for redaction
    - integrations=[LoggingIntegration(...)] if you want logs to appear in Sentry

---

## 7) Concrete Implementation Checklist (what the agent must do)

### Phase A: Pre-req — generator must run locally

- Confirm infra source resolution is fixed (generator currently expects ./commons but infra is ./sourcing/commons).
- If not yet fixed, implement infra resolver first (separate PR).

### Phase B: Add shared Sentry helper

- Add sourcing/commons/sentry_utils.py with:
    - DSN optional behavior
    - before_send scrubber
    - header/query redaction utilities
    - minimal dependencies (sentry-sdk)

### Phase C: Add dependency

- Add sentry-sdk to pyproject.toml dependencies (or optional extra if you prefer).
- Ensure it is included in runtime environment for generated scrapers.

### Phase D: Template integration (generated scrapers runtime)

- Update agentic_scraper/templates/scraper_main.py.j2 to:
    - import init_sentry from sourcing.commons.sentry_utils
    - call init_sentry early
    - wrap collect_content and validate_content with exception capture
    - add breadcrumbs around HTTP calls (redacted)

### Phase E: Instrument generator/orchestrator/fixer/updater

- agentic_scraper/generators/orchestrator.py
- agentic_scraper/generators/hybrid_generator.py
- agentic_scraper/fixers/fixer.py
- agentic_scraper/fixers/updater.py
  Add:
- init_sentry call at entry
- capture_exception on failures with tags/extra
- Don't swallow errors; rethrow after capture.

### Phase F: Tests (offline only)

Add unit tests for:

- redaction function behavior
- "no DSN" mode is no-op
- before_send scrubs secrets
- templates render with Sentry imports present
  Do not require network or real Sentry.

---

## 8) What NOT to do (common failure modes)

- Don't send full request URLs with query strings to Sentry.
- Don't attach response bodies by default.
- Don't log API keys in breadcrumbs.
- Don't let Sentry init crash the scraper (wrap init in try/except, log warning, continue).
- Don't add Sentry initialization in multiple places in the same process (guard with a module-level singleton).

---

## 9) Generator "Does it work / pass tests?" Reality Check

- In the current environment:
    - pytest execution is not working (missing/uv issues in this sandbox).
    - Several generator tests are stale vs current generator API (they still use HybridGenerator(llm_provider=...)).
- The implementing agent should update tests to match the current signature (HybridGenerator(factory=LLMFactory(...)) or a mock factory).

---

## 10) Recommended Deliverables

- PR1 (if needed): Infra path resolution so generator initializes against sourcing/commons.
- PR2: Sentry integration:
    - sourcing/commons/sentry_utils.py
    - template updates
    - generator/orchestrator/fixer/updater instrumentation
    - tests

If you want, I can also provide a "minimal Sentry init" code sketch for sourcing/commons/sentry_utils.py (still no repo changes) that the implementing agent can paste in safely.

---

---

# ADDENDUM: Where to Integrate Sentry in "Commons" / Shared Infrastructure

This section updates the prior handoff to explicitly list which shared modules in your infra ("commons") should be Sentry-aware, and how to do it without spreading Sentry calls everywhere.

---

## A) Commons Locations to Integrate Sentry (Recommended)

Your generated scrapers (and eventually fixer/updater) rely on shared utilities. The best practice is:

1. One centralized Sentry bootstrap + redaction module
2. Thin optional hooks in high-churn operational modules (logging, HTTP, Kafka, S3), but only where it creates high signal without leaking secrets.

### A.1 sourcing/commons/sentry_utils.py (NEW, single source of truth)

Add this file and treat it as the only module that calls sentry_sdk.init().

Responsibilities:

- init_sentry(...) with env-driven config (SENTRY_DSN, SENTRY_ENV, SENTRY_RELEASE)
- before_send redaction (headers + query params + tokens)
- set_tags_context(...) helper (datasource/dataset/endpoint/infrastructure versions)
- wrappers: capture_exception, capture_message, add_breadcrumb, start_span (optional)

Guardrails:

- No DSN => no-op
- Never raise from Sentry init; log warning and continue

---

## B) Existing Commons Files: What to Add (Minimal, High Value)

You currently have commons in:

- ./sourcing/commons
- ./sourcing/scraping/commons

And infra manager expects these files conceptually:

- collection_framework.py
- s3_utils.py
- kafka_utils.py
- hash_registry.py
- logging_json.py

### B.1 sourcing/commons/collection_framework.py (HIGH priority)

This is the best place to attach Sentry context because it's the "runtime spine" of collectors.

Add:

- Early call to init_sentry() in the base collector initialization or CLI entrypoint.
- set_tags_context(...) once per run:
    - datasource, dataset, endpoint_id, infrastructure_version, collector_version, component="collector"
- Wrap the main execution boundary:
    - if collector raises unhandled exception → capture_exception + rethrow

Why here:

- Every generated scraper will run through this base framework.
- You get consistent tagging and consistent "crash reporting" without modifying every scraper method.

### B.2 sourcing/commons/logging_json.py (HIGH priority)

If logging_json.py is the structured logging sink, integrate a Sentry logging integration pattern.

Add:

- Optional Sentry log capture only at ERROR+ (or use LoggingIntegration).
- Ensure logs don't include secrets; if your JSON logger can see headers, redact there too.

Why here:

- You'll automatically capture exceptions that are logged (even if they're handled) and correlate them with runs.

Guardrail:

- Do not capture INFO/DEBUG logs into Sentry by default—noise + cost.

### B.3 sourcing/commons/s3_utils.py (MED priority)

Instrument only meaningful failures:

- Wrap S3 upload/download failures with capture_exception
- Add breadcrumbs (bucket/key prefix only; do not attach full payload)

Why:

- S3 failures are operationally important and often environment/permissions-related.

Guardrail:

- Do not attach object contents to Sentry.

### B.4 sourcing/commons/kafka_utils.py (MED priority)

Capture producer/consumer failures:

- publish failures
- serialization errors
- auth/connection failures

Add:

- tags: kafka_topic, kafka_cluster (if safe)
- breadcrumbs for "published message" without including the message body

Guardrail:

- Never send raw messages to Sentry (could contain PII).

### B.5 sourcing/commons/hash_registry.py (LOW/MED priority)

Only capture:

- corrupted registry errors
- write failures
- unexpected state transitions

Why:

- Useful for diagnosing dedupe/idempotency regressions, but not as critical as runtime collectors.

### B.6 Requests/HTTP utilities (if present in commons)

If your scrapers centralize HTTP in a helper (some repos do):

- Add Sentry breadcrumbs per request (method + host + path)
- Capture exceptions with tags (http_status, host), but do not include headers/body.

If there is no shared HTTP helper:

- Prefer adding breadcrumbs in collection_framework.py around request calls (or use requests integration, but scrub aggressively).

---

## C) Generated Scrapers: Where Sentry Should Be Used (via Commons)

In templates (e.g., agentic_scraper/templates/scraper_main.py.j2):

- Import only from commons: from sourcing.commons.sentry_utils import init_sentry, capture_exception, add_breadcrumb
- Call init_sentry() once early (or rely on base framework doing it)
- Do not call sentry_sdk.init() directly in generated code.

---

## D) Fixer/Updater: Where Commons Sentry Helps

Even if fixer/updater are not using commons today, the recommended pattern is:

- Use the same sentry_utils module for consistency.
- Set component="fixer" / component="updater" and tags:
    - scraper_path, old_version, target_version, generator_agent

---

## E) Implementation Guardrails (Commons-specific)

- Never embed Sentry DSN into code; env only.
- Always scrub:
    - Authorization, cookies, APIM subscription key headers
    - token-like query params
- Never attach data payloads/artifacts to Sentry by default.
- Avoid multiple init calls; sentry_utils should maintain an "initialized" flag.

---

## F) Deliverable Update (What the agent must ship)

1. sourcing/commons/sentry_utils.py (new)
2. Minimal integration into:
    - sourcing/commons/collection_framework.py
    - sourcing/commons/logging_json.py
3. Optional integration into:
    - sourcing/commons/s3_utils.py
    - sourcing/commons/kafka_utils.py
    - sourcing/commons/hash_registry.py
4. Template update to use commons hooks (if framework doesn't already initialize)

This keeps Sentry "infrastructure-first" and avoids fragile per-scraper instrumentation.

---

## Implementation Sequence (Recommended Order)

1. **Add sentry-sdk dependency** (5 min)
   - Update pyproject.toml
   - Run `uv sync`

2. **Create sentry_utils.py** (30 min)
   - Implement init, scrubbers, capture helpers
   - Update sourcing/commons/__init__.py exports

3. **Add unit tests for sentry_utils** (20 min)
   - Test redaction logic
   - Test no-DSN mode
   - Test before_send scrubber

4. **Instrument commons - HIGH priority** (30 min)
   - collection_framework.py
   - logging_json.py

5. **Instrument commons - MED priority** (20 min)
   - s3_utils.py
   - kafka_utils.py

6. **Update scraper templates** (20 min)
   - scraper_main.py.j2

7. **Instrument generator/orchestrator** (20 min)
   - orchestrator.py
   - hybrid_generator.py

8. **Instrument fixer/updater** (15 min)
   - fixer.py
   - updater.py

9. **Test generated scrapers** (15 min)
   - Generate test scraper
   - Verify Sentry imports present
   - Verify no crashes without DSN

10. **Documentation** (15 min)
    - Update README with SENTRY_DSN setup
    - Add environment variable docs

**Total Estimated Time**: 3-4 hours

---

## Success Criteria

After implementation:

✅ **No DSN = No-op**
- Generator/scrapers run without SENTRY_DSN
- No Sentry overhead or errors

✅ **Secrets Redacted**
- Authorization headers show [REDACTED]
- URLs have query strings stripped
- API keys never appear in events

✅ **Consistent Tagging**
- All events have app/component/datasource/dataset tags
- Easy to filter by scraper or endpoint

✅ **Generated Scrapers Instrumented**
- Templates include Sentry imports
- Scrapers auto-capture exceptions
- Breadcrumbs added for HTTP requests

✅ **Generator/Fixer/Updater Instrumented**
- Failures captured with context
- Tags include scraper_path, generator_agent, versions

✅ **Tests Pass**
- All unit tests pass offline
- No network required
- Redaction logic verified

---

## Files Modified Summary

### New Files (2)
1. `sourcing/commons/sentry_utils.py` - Core Sentry utilities (~300 lines)
2. `tests/test_sentry_utils.py` - Unit tests (~200 lines)

### Modified Files (9)
1. `pyproject.toml` - Add sentry-sdk dependency
2. `sourcing/commons/__init__.py` - Export Sentry functions
3. `sourcing/commons/collection_framework.py` - Add Sentry init + instrumentation
4. `sourcing/commons/logging_json.py` - Add Sentry logging integration (optional)
5. `sourcing/commons/s3_utils.py` - Add exception capture
6. `sourcing/commons/kafka_utils.py` - Add exception capture
7. `agentic_scraper/templates/scraper_main.py.j2` - Add Sentry init + instrumentation
8. `agentic_scraper/generators/orchestrator.py` - Add Sentry init + instrumentation
9. `agentic_scraper/generators/hybrid_generator.py` - Add exception capture

### Optional Files (2)
1. `agentic_scraper/fixers/fixer.py` - Add Sentry instrumentation
2. `agentic_scraper/fixers/updater.py` - Add Sentry instrumentation

**Total**: 13 files (2 new, 9 modified, 2 optional)
