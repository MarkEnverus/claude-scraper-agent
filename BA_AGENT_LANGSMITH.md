# LangSmith Tracing Implementation Spec (BA Agents)

Revoke/rotate any exposed `LANGSMITH_API_KEY` immediately and treat it as compromised. Never commit keys into the repo.

## Goal
Make it so a developer can run `agentic-scraper analyze …` (and orchestration that calls it) and reliably see a full LangSmith trace tree showing:
- LangGraph run + node-level steps (`planner_react`, `analyst`, `website_p1`, `api_p1`, `summarizer`, etc.)
- Agent messages (as captured by LangChain tracing)
- Tool calls (`render_page_with_js`, `http_get_headers`, `extract_links`)
- LLM calls (Bedrock via `ChatBedrockConverse`)
- Useful run metadata/tags (seed URL, hostname, component, recursion limit, etc.)

…while allowing safe redaction/hiding of sensitive inputs/outputs.

## Current State (repo facts)
- LangGraph workflow exists and runs via `graph.invoke()` in `agentic_scraper/business_analyst/cli.py`.
- Planner uses `langchain.agents.create_agent` and calls `agent.invoke()` in `agentic_scraper/business_analyst/nodes/planner_react.py`.
- `BAConfig.enable_langsmith` exists (`agentic_scraper/business_analyst/config.py`) but is not referenced anywhere, so it currently has no effect.
- No explicit tracer/callback setup is present; tracing only happens via env vars (and only if the installed library versions honor the specific env var names used).

## Target Behavior (what “proper tracing setup” means)
1. **Single switch**: `BAConfig.enable_langsmith` (plus env presence) deterministically controls whether tracing is enabled.
2. **Version-proof env bridging**: support both LangSmith-style and LangChain-style env var names because different versions/components honor different flags.
3. **Consistent run identity**:
   - unique, sanitized `thread_id` per invocation (avoid embedding raw URL directly as ID)
   - human-friendly `run_name` (e.g., `BA Analyze: <hostname>`)
   - consistent `project` naming (from env or CLI/config)
4. **Rich metadata/tags**:
   - tags: `component=ba`, `subsystem=langgraph`, `node=<node_name>` (where feasible), `provider=bedrock`, etc.
   - metadata: `seed_url`, `hostname`, `max_depth`, `recursion_limit`, `render_mode`, `git_sha` (optional), `package_version` (optional)
5. **Safe-by-default redaction** aligned with `BAConfig.enable_pii_redaction`:
   - ability to hide inputs/outputs from LangSmith entirely
   - avoid sending page HTML, cookies, auth headers, tokens, screenshot binary paths, etc., unless explicitly enabled
6. **No tracing in CI/tests by default**:
   - don’t create accidental outbound calls
   - tests should not require network or LangSmith availability

## Implementation Spec (exactly what to implement)

### 1) Add a small “observability/tracing” module
Create a single internal module responsible for:
- deciding “should we trace?”
- normalizing env vars
- building per-run config (tags/metadata/run_name/thread_id)
- (optional) providing a redacting callback handler if you need finer control than “hide inputs/outputs”

This module should not import heavy dependencies at import time if tracing is off (keep startup safe/fast).

#### Responsibilities
- Read `BAConfig.enable_langsmith` and `BAConfig.enable_pii_redaction`
- Detect if a LangSmith API key is present (via env only)
- Export:
  - `should_enable_tracing(config) -> bool`
  - `prepare_langsmith_env(config) -> None` (sets/normalizes env vars for the current process)
  - `build_run_config(...) -> dict` (returns a dict suitable to merge into LangGraph/LangChain invoke configs: `tags`, `metadata`, possibly `run_name`, and the sanitized `thread_id`)

#### Env var normalization (do this even if user sets only one style)
If tracing is enabled, ensure **both** “LangSmith” and “LangChain” env keys are set consistently:
- project: `LANGSMITH_PROJECT` and `LANGCHAIN_PROJECT`
- endpoint: `LANGSMITH_ENDPOINT` and `LANGCHAIN_ENDPOINT`
- api key: `LANGSMITH_API_KEY` and `LANGCHAIN_API_KEY`
- tracing enable: `LANGSMITH_TRACING=true` and `LANGCHAIN_TRACING_V2=true`

If tracing is disabled, do not force-disable global env (avoid surprising callers), but you may set `LANGCHAIN_TRACING_V2=false` within the CLI process if you want strict behavior—document the choice.

#### PII redaction behavior
If `enable_pii_redaction` is true, prefer “hide inputs/outputs” mode:
- set `LANGSMITH_HIDE_INPUTS=true` and `LANGSMITH_HIDE_OUTPUTS=true` (and the LangChain equivalents if available in your versions)

Provide an override escape hatch via env (e.g., if a developer explicitly sets `LANGSMITH_HIDE_INPUTS=false`, honor it).

### 2) Wire tracing into the CLI entrypoint (primary control point)
In `agentic_scraper/business_analyst/cli.py`:
- Before `create_ba_graph()` / before the first `graph.invoke()`:
  - call the tracing module to:
    - normalize env vars (if enabled)
    - compute a sanitized thread/run identity
    - compute common tags/metadata
- Merge the returned run config into `graph_config` (currently includes `configurable.thread_id` and `recursion_limit`).

#### Thread/run identity requirements
- Stop using raw `seed_url` in `thread_id` directly.
- Implement:
  - `thread_id = "ba-" + <hostname> + "-" + <short_hash(seed_url + timestamp)>`
  - include the raw `seed_url` in metadata instead (safe to show/hide)
- Keep `recursion_limit` in metadata so it’s visible in LangSmith.

### 3) Ensure the planner agent invocation inherits the same run context
In `agentic_scraper/business_analyst/nodes/planner_react.py`, the `thread_config` passed to `agent.get_state()` and `agent.invoke()` should be aligned with the outer run:
- Use the **same sanitized thread_id** (or a stable derived child id).
- Add consistent `tags`/`metadata` and an explicit `run_name` for the planner invocation if supported by your installed LangChain core.
- Ensure tool calls and LLM calls created inside the agent inherit the callbacks/tracing context (usually automatic if config/env is correct, but passing `tags`/`metadata` reduces ambiguity).

### 4) (Optional but recommended) Add node-level naming/tags in LangGraph
LangGraph node-level visibility varies by version/config.
Implementation options (pick one based on what your installed `langgraph==1.0.5` supports cleanly):
- If supported, pass a `run_name` or tags per node when adding nodes or invoking.
- Otherwise, rely on the run tree created by LangChain tracing inside node implementations (agent/tool/llm calls will still appear), and add node name into logs/metadata at node start.

The “good enough” bar: you can click a run and see which node you were in when tool/LLM calls happened.

### 5) Make `BAConfig.enable_langsmith` meaningful
Define semantics clearly:
- `enable_langsmith=false` → never trace, even if env vars exist.
- `enable_langsmith=true` → trace only if API key exists in env (don’t error if missing; just log a single INFO/WARN).

### 6) Don’t leak secrets (explicit non-negotiables)
- Never log the API key, org id, or workspace id.
- If you include `seed_url` in metadata, consider stripping query params by default (tokens often live there). If you must keep full URL, only do so when inputs are not hidden and redaction is disabled.

### 7) Documentation to add/update
Add a short “Observability / LangSmith Tracing” section in the most discoverable doc (pick one: `README`, `BA_AGENT_FLOW.md`, or a new `docs/observability.md`), containing:
- Required env vars (both `LANGSMITH_*` and `LANGCHAIN_*` recommended)
- How to disable tracing (`enable_langsmith=false` or env override)
- How to control hiding inputs/outputs
- Where to find the project in LangSmith

### 8) Validation / Acceptance Criteria

#### Local checks (no LangSmith network needed)
- Running with `enable_langsmith=false` does not set/modify tracing env vars and does not attempt to initialize any tracer client.
- Running with `enable_langsmith=true` but no API key logs a single message and proceeds normally.
- Thread IDs are sanitized and stable format.

#### With LangSmith enabled (developer-run, network allowed)
- One top-level run appears in `LANGSMITH_PROJECT`.
- The run contains child runs for:
  - graph execution
  - planner agent invocations
  - tool calls
  - LLM calls
- Metadata shows `seed_url` (redacted or hidden per config), `hostname`, and key config knobs.

## Recommended default env setup
Even if you keep `LANGSMITH_TRACING=true`, always also set:
- `LANGCHAIN_TRACING_V2=true`
- `LANGCHAIN_PROJECT=$LANGSMITH_PROJECT`
- `LANGCHAIN_ENDPOINT=$LANGSMITH_ENDPOINT`
- `LANGCHAIN_API_KEY=$LANGSMITH_API_KEY`

This avoids the “it works for one component but not the other” problem across LangChain/LangGraph versions.

## Deliverable checklist for the implementing agent
- [ ] Tracing module added (decision + env normalization + run config builder)
- [ ] `agentic_scraper/business_analyst/cli.py` uses it to configure graph invoke
- [ ] `agentic_scraper/business_analyst/nodes/planner_react.py` aligns agent invoke config to the same run context
- [ ] `BAConfig.enable_langsmith` actually controls behavior
- [ ] PII redaction behavior tied to `BAConfig.enable_pii_redaction`
- [ ] Doc section added explaining how to use it
- [ ] No secrets logged; no keys in repo; tests/CI safe by default

