# Scraper Generation + Fixer Deep Review (Handoff)

Audience: a follow-on dev/agent who will implement fixes.  
Scope: generator + templates + “fixer/updater” docs, with emphasis on “does the generated code actually run?” and “why do docs mention credentials for public APIs?”

---

## Repo Context (What This Project Is)

This repo contains:
- A **BA Analyzer** (LangGraph-based) that produces a validated datasource spec (`validated_datasource_spec.json` conceptually).
- A **HybridGenerator** (`agentic_scraper/generators/hybrid_generator.py`) that:
  1) transforms the BA spec into template variables (`VariableTransformer`)
  2) uses an LLM to generate method bodies (`collect_content`, `validate_content`, auth init)
  3) renders templates (`TemplateRenderer`) into a generated scraper package (scraper `main.py`, tests, README, integration protocol).
- A small **infra “collection framework”** under `sourcing/commons/` that generated scrapers import.

Key intended UX:
- `run_generator.py` calls `ScraperOrchestrator.generate_from_url()` → generates code and exits.
- The generated scraper is expected to run as a Click CLI and use the infra framework.

---

## Key Findings (Bugs / Mismatches That Prevent “Run the Generated Code”)

### 1) Generated CLI wiring is incompatible with the infra layer

**Evidence**
- Template CLI code in `agentic_scraper/templates/scraper_main.py.j2`:
  - Instantiates `S3Uploader(bucket_name=s3_bucket)` and `KafkaProducer(bootstrap_servers=..., topic=...)`.
  - Calls `collector.collect(...)`.
- Infra reality in `sourcing/commons/`:
  - `S3Uploader` is defined as `S3Uploader(config: S3Configuration)` in `sourcing/commons/s3_utils.py` (no `bucket_name=...` constructor).
  - `BaseCollector` defines `run_collection(...)` in `sourcing/commons/collection_framework.py` (not `collect(...)`).

**Impact**
- Any attempt to “run the generated code” beyond `--help` will fail quickly (constructor / method mismatches).
- This directly explains “why curl test?”: the generator pipeline currently doesn’t validate runtime execution of generated code.

**Root cause**
- Templates appear written for a *different* infra API than the `sourcing/commons` currently shipped in this repo.

---

### 2) Generated unit tests template does not match the current framework types

**Evidence**
- `agentic_scraper/templates/scraper_tests.py.j2` builds `DownloadCandidate(url=..., expected_filename=...)`.
- Actual `DownloadCandidate` dataclass in `sourcing/commons/collection_framework.py` expects:
  - `identifier`, `source_location`, `metadata`, `collection_params`, `file_date`.

**Impact**
- Even if the generated scraper compiles, generated tests will not run without edits.

---

### 3) README includes auth/credentials guidance even when `auth_required` is false

This is a template bug: auth-related prose is only partially conditional.

**Evidence**
- `agentic_scraper/templates/scraper_readme.md.j2` has some `{% if auth_required %}` blocks, but also includes auth env var exports unconditionally (e.g. “Using environment variables” contains `export {{ auth_env_var }}="your-api-key"` without guarding).
- It also includes sections like “Integration tests require valid credentials” and “Authentication Errors” troubleshooting that should be conditional.

**Impact**
- Public/no-auth APIs still get README guidance that implies credentials are required.

---

### 4) INTEGRATION_TEST protocol template is out of date (and mentions credentials unconditionally)

**Evidence**
- `agentic_scraper/templates/INTEGRATION_TEST.md.j2`:
  - “Required services” includes `{{ source }} API access with valid credentials` unconditionally.
  - Setup exports `{{ auth_env_var }}` unconditionally.
  - Contains import paths and object constructions that don’t match the shipped infra (e.g. `S3Uploader(bucket_name=...)` pattern appears here too).

**Impact**
- The integration test doc is misleading for public endpoints and not executable as written.

---

### 5) Several internal references still use old module naming (`claude_scraper`) vs `agentic_scraper`

**Evidence**
- `agentic_scraper/templates/scraper_readme.md.j2` references `python -m claude_scraper.updater ...`.
- `tests/test_template_renderer.py` expects default templates at `.../claude_scraper/templates` but `TemplateRenderer` defaults to `agentic_scraper/templates` (see `agentic_scraper/generators/template_renderer.py`).

**Impact**
- Docs/commands in generated artifacts may be wrong even if the generator works.

---

### 6) Kafka import path inside the infra layer looks inconsistent with this repo layout

**Evidence**
- In `sourcing/commons/collection_framework.py`, Kafka publish path uses:
  - `from sourcing.scraping.commons.kafka_utils import ...`
- But the repo contains `sourcing/commons/kafka_utils.py`.

**Impact**
- If Kafka is enabled at runtime, this will likely raise `ModuleNotFoundError` unless the runtime environment also has a `sourcing/scraping/commons/` package (it doesn’t exist in this repo).

---

## Why “curl test?” vs “run generated code?”

This repo currently has:
- Template rendering + AST-level checks in some tests (e.g., `tests/test_end_to_end_integration.py` parses AST).
- But **no step in the generator/orchestrator path** that executes the generated CLI or imports the generated module as a smoke test.

So curl was testing “remote API alive” and not “generated artifacts runnable”.

---

## Recommended Fix Tasks (Implementation Plan for Next Agent)

### P0 — Make generated code runnable with current `sourcing/commons` APIs

Target: `python main.py --help` works; `python main.py ...` runs far enough to start collection without immediate crashes.

Concrete edits likely needed in `agentic_scraper/templates/scraper_main.py.j2`:
- Remove/replace direct construction of `S3Uploader(bucket_name=...)` and `KafkaProducer(bootstrap_servers=...)`.
- Align CLI arguments with `BaseCollector.__init__`:
  - `--environment` (required or default)
  - `--s3-prefix` (default to something sane)
  - `--kafka-connection-string` (optional)
- Instantiate collector with:
  - `{{ class_name }}(dgroup=..., s3_bucket=..., s3_prefix=..., redis_client=..., environment=..., kafka_connection_string=..., api_key=...)`
- Replace `collector.collect(...)` call with `collector.run_collection(...)` (matching `sourcing/commons/collection_framework.py`).

### P0 — Fix templates so auth prose is fully conditional

Target: if `auth_required == false`, README and integration doc contain no credential instructions.

Edits likely needed in:
- `agentic_scraper/templates/scraper_readme.md.j2`:
  - Wrap env export examples, “integration tests require credentials”, and “authentication errors” troubleshooting in `{% if auth_required %}`.
- `agentic_scraper/templates/INTEGRATION_TEST.md.j2`:
  - Condition “valid credentials” requirements, exports, and auth-related steps.

### P0 — Fix generated tests template to match framework types

Target: generated tests import and run without manual edits.

Edits likely needed in `agentic_scraper/templates/scraper_tests.py.j2`:
- Build `DownloadCandidate(identifier=..., source_location=..., metadata=..., collection_params=..., file_date=...)`.
- Avoid relying on nonexistent `CollectedContent` / `ValidationResult` types unless they exist in `sourcing/commons` (current `collect_content` contract returns `bytes`).
- Mock network calls at the `requests` level and avoid/patch S3/Kafka side effects.

### P1 — Add a smoke test that runs the generated artifact (no network)

Target: ensure we test generated code, not just remote API.

Options:
- A generator flag (`--smoke`) that runs:
  - `python -m py_compile generated/main.py`
  - `python generated/main.py --help`
- Or a pytest that:
  - generates into `tmp_path`
  - imports the generated module (no execution)
  - runs `--help` via `subprocess` (should not hit network)

### P1 — Remove stale `claude_scraper.*` references

Target: docs + tests consistently use `agentic_scraper`.

Places to review:
- `agentic_scraper/templates/scraper_readme.md.j2`
- `tests/test_template_renderer.py`

### P1 — Resolve Kafka path mismatch in infra (if this repo is the authoritative runtime)

Target: Kafka-enabled runs don’t error on import.

Likely fix:
- Change `sourcing/commons/collection_framework.py` to import from `sourcing.commons.kafka_utils`.

---

## Validation Checklist (What the Next Agent Should Run)

No-network / local checks:
1) Generate a scraper from a local BA spec (mocked tests already exist):
   - Use `tests/test_end_to_end_integration.py` patterns (they use `mock_llm_factory`).
2) Verify generated code can at least:
   - `python -m py_compile <generated>/main.py`
   - `python <generated>/main.py --help`
3) Verify generated tests compile:
   - `python -m py_compile <generated>/tests/test_main.py`
4) Run repo tests (subset first):
   - `pytest -k "template_renderer or end_to_end_integration"`

If network-enabled integration is desired later:
- Run a real collection with Redis + localstack + optional Kafka only after the above is clean.

---

## Notes / Oddities Observed During Review

- Every shell command printed `"(eval):5: parse error near \`end'"` before output. This looks like a local zsh init issue in the environment, not a repo code issue, but it can confuse automation logs.

