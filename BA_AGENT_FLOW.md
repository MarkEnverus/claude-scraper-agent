# BA Agent Flow (LangGraph → Mermaid)

This document captures the **current** Business Analyst (BA) LangGraph execution flow as a Mermaid diagram, generated directly from the compiled LangGraph.

**Source of truth**
- Graph definition: `agentic_scraper/business_analyst/graph.py`
- Mermaid export: `create_ba_graph().get_graph().draw_mermaid()`

## Regenerate The Diagram

Run from repo root:

```bash
./.venv/bin/python - <<'PY'
from agentic_scraper.business_analyst.graph import create_ba_graph
app = create_ba_graph()
print(app.get_graph().draw_mermaid())
PY
```

## Mermaid (Auto-Generated)

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	planner_react(planner_react)
	analyst(analyst)
	summarizer(summarizer)
	website_p1(website_p1)
	website_p2(website_p2)
	api_p1(api_p1)
	param_p15(param_p15)
	api_p2(api_p2)
	__end__([<p>__end__</p>]):::last
	__start__ --> planner_react;
	analyst -.-> api_p1;
	analyst -.-> planner_react;
	analyst -.-> website_p1;
	api_p1 --> param_p15;
	api_p2 -.-> planner_react;
	api_p2 -.-> summarizer;
	param_p15 --> api_p2;
	planner_react -.-> analyst;
	planner_react -.-> summarizer;
	website_p1 --> website_p2;
	website_p2 -.-> planner_react;
	website_p2 -.-> summarizer;
	summarizer --> __end__;
	planner_react -.-> planner_react;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

## Legend / How To Read This

- `-->` = unconditional edge (`workflow.add_edge(...)`)
- `-.->` = conditional edge (`workflow.add_conditional_edges(...)`)
- `__start__` / `__end__` are LangGraph synthetic boundary nodes

## Node Responsibilities (High-Level)

- `planner_react`
  - Tool-driven exploration and URL selection (gated tools + allowed URL set).
  - Emits `state["next_action"]` as `"analyze_page" | "continue" | "stop"`.
- `analyst`
  - Extracts endpoints and Phase 0 detection (`state["detected_source_type"]`, `state["detection_confidence"]`).
  - Marks `state["last_analyzed_url"]` for downstream handlers.
- `website_p1` → `website_p2`
  - WEBSITE discovery/validation path (currently centered on file-portal style discovery).
- `api_p1` → `param_p15` → `api_p2`
  - API discovery/parameter-enrichment/validation path.
- `summarizer`
  - Produces audit outputs (`site_report.json/md`) and generator-ready artifacts (`validated_datasource_spec.json`, `endpoint_inventory.json`, `executive_data_summary.md`).

