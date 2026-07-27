# cognisphereTutor — Agent-Native Architecture

## Overview

cognisphereTutor is an **agent-native** intelligent learning companion organized
around a two-layer plugin model — single-shot **Tools** invoked by the
LLM, and multi-stage **Capabilities** that take over a turn — exposed
through three entry points: CLI, WebSocket API, and Python SDK.

## Architecture

```
Entry Points:  CLI (Typer)  |  WebSocket /api/v1/ws  |  Python SDK
                    ↓                   ↓                   ↓
              ┌─────────────────────────────────────────────────┐
              │              ChatOrchestrator                    │
              │   routes UnifiedContext → selected Capability    │
              │   (defaults to `chat`)                           │
              └──────────┬──────────────┬───────────────────────┘
                         │              │
              ┌──────────▼──┐  ┌────────▼──────────┐
              │ ToolRegistry │  │ CapabilityRegistry │
              │  (Level 1)   │  │   (Level 2)        │
              └──────────────┘  └────────────────────┘
```

All capabilities emit on a shared `StreamBus`; the orchestrator fans
events out to consumers. Runtime settings live in
`data/user/settings/*.json` — project-root `.env` files are intentionally
ignored.

### Cognisphere Learning Plugins — ownership boundary

Domain-specific learning (ontology, knowledge, benchmarks, domain
runtimes) is implemented by **Cognisphere Learning Plugins**. This repo
owns generic orchestration, negotiation, trusted-context, runtime bridge
callbacks, cross-domain compose (DT-P1…P6 under
`integrations/cognisphere/`), and the teaching loop (Learning Space /
`mastery_path` / chat). Do **not** hardcode domain logic (e.g. LeetCode /
AP Calculus / AWS) into Tutor core — keep it in plugins or thin
data-driven adapters (`manifests/runtime_adapters.json`, registry).

### Level 1 — Tools

Single-function tools the LLM picks on demand. Four user-toggleable tools
surface in `/settings/tools`:

| Tool           | Description                                   |
| -------------- | --------------------------------------------- |
| `brainstorm`   | Breadth-first idea exploration with rationale |
| `web_search`   | Web search with citations                     |
| `paper_search` | arXiv preprint search                         |
| `reason`       | Dedicated deep-reasoning LLM call             |

The rest are **context-gated**: the chat capability auto-mounts them from
`ToolMountFlags` (presence of a KB, attachments, sandbox availability, …), and
any of them can also be force-enabled via `--tool`. Auto-mounted set: `rag`,
`read_source`, `read_memory`, `write_memory`, `read_skill`, `load_tools`,
`exec`, `code_execution` (sandboxed Python: NL intent → code → run),
`list_notebook`, `write_note`, `web_fetch`, `github`, `cron`,
`ask_user` (pauses the turn and resumes with the user's reply), plus the
mastery-path tools. `geogebra_analysis` ships as a user-toggleable tool.
`COMING_SOON_TOOL_TYPES` is an empty parking slot for redesign-in-progress
tools (settings shows a badge only when that tuple is non-empty).

### Level 2 — Capabilities

Multi-stage pipelines that own the turn:

| Capability       | Stages                                                |
| ---------------- | ----------------------------------------------------- |
| `chat`           | exploring → responding (single agentic loop, default) |
| `mastery_path`   | responding (Guided Learning — chat loop + mastery tools, gated per topic type) |
| `deep_solve`     | planning → reasoning → writing                        |
| `deep_question`  | ideation → generation                                 |
| `deep_research`  | rephrasing → decomposing → researching → reporting    |
| `visualize`      | analyzing → generating → reviewing (SVG / Chart.js / Mermaid / HTML; or routes to Manim sub-stages via `render_type`) |
| `math_animator`  | concept_analysis → concept_design → code_generation → code_retry → summary → render_output |

All capabilities converge on `emit_capability_result()` in
`cognispheretutor/capabilities/_shared.py` so every turn emits the same envelope
(response payload + `cost_summary` from `UsageTracker`). Status copy and
prompts are i18n'd via `capabilities/prompts/{en,zh}/<name>.yaml`.

## CLI Usage

```bash
# Install
pip install cognispheretutor      # Full app (CLI + Web/API + packaged Web assets)
pip install cognispheretutor-cli  # CLI-only

# Run any capability
cognispheretutor run chat "Explain Fourier transform"
cognispheretutor run deep_solve "Solve x^2=4" -t rag --kb my-kb
cognispheretutor run visualize "Animate sine wave" --config render_mode=manim_video

# Interactive REPL
cognispheretutor chat
# (inside the REPL: /regenerate or /retry re-runs the last user message)

# Partners (IM-connected companions)
cognispheretutor partner list

# Knowledge bases, memory, server
cognispheretutor kb list
cognispheretutor kb create my-kb --doc textbook.pdf
cognispheretutor memory show
cognispheretutor serve --port 8001       # API server only
cognispheretutor start                   # backend + frontend together
```

## Key Files

| Path                                       | Purpose                              |
| ------------------------------------------ | ------------------------------------ |
| `cognispheretutor/runtime/orchestrator.py`        | `ChatOrchestrator` — unified entry   |
| `cognispheretutor/runtime/launcher.py`            | Backend + frontend lifecycle / port discovery |
| `cognispheretutor/runtime/registry/`              | Tool + Capability registries         |
| `cognispheretutor/runtime/bootstrap/builtin_capabilities.py` | Built-in capability class paths |
| `cognispheretutor/services/config/runtime_settings.py` | JSON settings + process-env overrides |
| `cognispheretutor/core/stream.py`, `stream_bus.py` | StreamEvent protocol + async fan-out |
| `cognispheretutor/core/tool_protocol.py`          | `BaseTool` + `ToolDefinition`         |
| `cognispheretutor/core/capability_protocol.py`    | `BaseCapability` + `CapabilityManifest` |
| `cognispheretutor/core/context.py`                | `UnifiedContext` dataclass            |
| `cognispheretutor/tools/builtin/__init__.py`      | All built-in tool wrappers           |
| `cognispheretutor/capabilities/`                  | Built-in capability implementations  |
| `cognispheretutor/integrations/cognisphere/`      | Cognisphere Learning Plugins client (DT-P1…P6: discover / negotiate / validate / import / trusted-context / runtime callbacks + offline runtime bridge / compose). **Boundary:** domain learning lives in plugins; Tutor = generic orchestration + teaching loop only — no domain-exclusive logic in core. |
| `cognispheretutor/agents/_shared/capability_result.py` | Shared final envelope (`emit_capability_result`); **must keep unit tests in `tests/agents/_shared/test_capability_result.py`** |
| `cognispheretutor/agents/_shared/tool_composition.py` | Shared tool mount policy (`compose_enabled_tools`); **must keep unit tests in `tests/agents/_shared/test_tool_composition.py`** |
| `cognispheretutor/app.py`                         | `cognisphereTutorApp` — Python SDK facade    |
| `cognispheretutor_cli/main.py`                    | Typer CLI entry point                |
| `cognispheretutor/api/routers/unified_ws.py`      | Unified WebSocket endpoint           |

## Dependency Layers

Public install paths and source extras are defined in `pyproject.toml`.
Requirements files mirror the same dependency groups for Docker/CI installs.

```
pip install cognispheretutor      — Full app (CLI + Web/API + packaged Web assets)
pip install cognispheretutor-cli  — CLI-only (LLM + RAG + providers + document parsing)
pip install -e .           — Source install for development

Source extras (.[ extra ], defined in pyproject.toml):
.[cli]            — CLI-only dependency set
.[server]         — Web/API server dependencies
.[partners]       — Partner channel SDKs + MCP client  (legacy alias: .[tutorbot])
.[matrix]         — Matrix channel for Partners (matrix-nio; needs libolm)
.[matrix-e2e]     — Matrix with end-to-end encryption (matrix-nio[e2e])
.[math-animator]  — Manim addon (powers `visualize` Manim renders + `cognispheretutor run math_animator`)
.[dev]            — Test / lint tooling
.[all]            — Everything above
```

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **DeepTutor** (42552 symbols, 80000 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/DeepTutor/context` | Codebase overview, check index freshness |
| `gitnexus://repo/DeepTutor/clusters` | All functional areas |
| `gitnexus://repo/DeepTutor/processes` | All execution flows |
| `gitnexus://repo/DeepTutor/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
