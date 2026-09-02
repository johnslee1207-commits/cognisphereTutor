# Untracked Asset Review

Date: 2026-09-02

Scope: `D:\Projects\cognisphereTutor`

This review classifies the current historical untracked files in the Tutor
working tree.

## Summary

| Path group | Recommendation | Rationale |
| --- | --- | --- |
| `.aetheros/` | `ignore` | Local AetherOS planning, state, budget, compatibility, and evidence files are per-machine runtime state. |
| `.opencode/` | `ignore` | Local agent, command, rule, plugin, and skill configuration should not be committed as Tutor product code without a separate governance decision. |
| `.mcp.json` | `ignore` | Local connector/server settings may contain machine-specific paths or account assumptions. |
| `opencode.jsonc` | `ignore` | Local OpenCode configuration should remain machine-specific unless promoted as a project template. |

## Current Decision

No historical untracked Tutor assets should be committed in bulk.

Tutor already ignores `docs/`, `runtime/`, `.claude`, `.cursor/`, and generated
data paths. This review adds explicit ignore rules for `.aetheros/`,
`.opencode/`, `.mcp.json`, and `opencode.jsonc` so future AI infra commits stay
focused on source, tests, manifests, and intentional product documentation.

## Promotion Rule

If any local agent configuration becomes a product requirement, promote it
through a separate review as one of:

- a tracked template under `examples/`
- project documentation under an explicitly force-added doc path
- a generic Tutor integration test
- a plugin-owned manifest in `CognisphereLearningPlugins`

Do not use local tool state as the authoritative source for Tutor behavior.
