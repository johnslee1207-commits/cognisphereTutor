"""DT-P4/P5/P6 — product binding bridge to Cognisphere offline plugin runtimes.

Callbacks in ``runtime_callbacks`` persist events; this module *drives* the
plugin P2–P5 runtimes (Socratic / sandbox / mistake / skill / interview) and
then feeds results through those callbacks.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any

from cognispheretutor.integrations.cognisphere._contract import load_runtime_adapters
from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError
from cognispheretutor.integrations.cognisphere.registry_client import PluginRegistryClient
from cognispheretutor.integrations.cognisphere.runtime_callbacks import (
    apply_mastery_update,
    ingest_sandbox_result,
    on_tutor_session_event,
    sync_mistake_memory,
)
from cognispheretutor.integrations.cognisphere.security_gates import is_sandbox_authorized


def _adapters() -> dict[str, Any]:
    return load_runtime_adapters()


def _adapter(name: str) -> dict[str, Any]:
    cfg = _adapters()
    adapters = cfg.get("adapters") or {}
    item = adapters.get(name)
    if not isinstance(item, dict):
        raise CognisphereIntegrationError(
            "unknown_capability:" + name,
            message=f"runtime adapter not configured: {name}",
        )
    return item


def load_runtime_module(
    adapter_name: str,
    *,
    domain: str | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> ModuleType:
    """Import the plugin runtime module declared in runtime_adapters.json."""
    adapter = _adapter(adapter_name)
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    resolved_domain = domain or str(_adapters().get("default_domain") or "leetcode")
    registry.ensure_import_paths(domain=resolved_domain, root=plugins_root)
    module_path = str(adapter.get("module") or "")
    if not module_path:
        raise CognisphereIntegrationError(
            "unknown_capability:" + adapter_name,
            message="adapter missing module path",
        )
    try:
        return import_module(module_path)
    except ImportError as exc:
        raise CognisphereIntegrationError(
            "benchmark_unavailable" if adapter_name == "benchmark" else "plugins_root_missing",
            message=f"cannot import runtime module {module_path}: {exc}",
            details={
                "adapter": adapter_name,
                "module": module_path,
                "domain": resolved_domain,
                "plugins_root": str(plugins_root),
            },
        ) from exc


def _call(mod: ModuleType, attr: str, *args: Any, **kwargs: Any) -> Any:
    fn = getattr(mod, attr, None)
    if not callable(fn):
        raise CognisphereIntegrationError(
            "missing_deeptutor_func:" + attr,
            message=f"runtime function missing: {attr}",
        )
    return fn(*args, **kwargs)


def start_tutor_session(
    problem_slug: str,
    *,
    hint_level: int = 0,
    domain: str | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
    persist: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    """Start offline Socratic dialogue (plugin P2) and log via DT-P4 callback."""
    adapter = _adapter("socratic_tutor")
    lo = int(adapter.get("hint_level_min", 0))
    hi = int(adapter.get("hint_level_max", 4))
    if hint_level < lo or hint_level > hi:
        raise CognisphereIntegrationError(
            "tutor_must_ask_not_spoil",
            message=f"hint_level must be {lo}–{hi}",
            details={"hint_level": hint_level},
        )

    mod = load_runtime_module("socratic_tutor", domain=domain, root=root, client=client)
    session = _call(
        mod,
        str(adapter["start"]),
        problem_slug,
        hint_level=hint_level,
        persist=persist,
        **kwargs,
    )
    if not isinstance(session, dict):
        raise CognisphereIntegrationError(
            "export_envelope_invalid",
            message="socratic start returned non-object",
        )

    if session.get("safety", {}).get("full_solution_included") is True:
        raise CognisphereIntegrationError(
            "tutor_must_ask_not_spoil",
            details={"session_id": session.get("session_id")},
        )

    session_id = str(session.get("session_id") or f"tutor:{problem_slug}")
    event_receipt = on_tutor_session_event(
        session_id,
        {
            "type": "session_started",
            "stage_id": session.get("current_phase"),
            "hint_level": session.get("hint_level", hint_level),
            "problem_slug": problem_slug,
            "asks_not_spoils": True,
            "full_solution_included": False,
            "domain": domain or _adapters().get("default_domain"),
        },
    )
    status = str(session.get("status") or "ok")
    return {
        "ok": status in {"ok", "started", "in_progress"},
        "phase": "DT-P4",
        "status": status,
        "session": session,
        "callback": event_receipt,
        "source": "plugin_socratic_tutor_runtime",
    }


def advance_tutor_session(
    session: dict[str, Any],
    *,
    event: str = "advance",
    checkpoint: str | None = None,
    learner_reply: str | None = None,
    domain: str | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Advance an offline Socratic session and persist the stage event."""
    adapter = _adapter("socratic_tutor")
    mod = load_runtime_module("socratic_tutor", domain=domain, root=root, client=client)
    call_kwargs = dict(kwargs)
    call_kwargs["event"] = event
    if checkpoint is not None:
        call_kwargs["checkpoint"] = checkpoint
    if learner_reply is not None:
        call_kwargs["learner_reply"] = learner_reply
    updated = _call(mod, str(adapter["advance"]), session, **call_kwargs)
    if not isinstance(updated, dict):
        raise CognisphereIntegrationError(
            "export_envelope_invalid",
            message="socratic advance returned non-object",
        )

    # Plugin may return the session nested or as the top-level object.
    payload = updated.get("session") if isinstance(updated.get("session"), dict) else updated
    session_id = str(payload.get("session_id") or session.get("session_id") or "tutor")
    event_receipt = on_tutor_session_event(
        session_id,
        {
            "type": event,
            "stage_id": payload.get("current_phase") or payload.get("phase"),
            "hint_level": payload.get("hint_level"),
            "asks_not_spoils": True,
            "full_solution_included": bool(
                (payload.get("safety") or {}).get("full_solution_included")
            ),
        },
    )
    return {
        "ok": True,
        "phase": "DT-P4",
        "session": payload,
        "raw": updated,
        "callback": event_receipt,
        "source": "plugin_socratic_tutor_runtime",
    }


def verify_submission(
    *,
    slug: str | None = None,
    source_code: str | None = None,
    offline_simulated: bool = True,
    outcome: dict[str, Any] | None = None,
    execute: bool = False,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run plugin P3 verification (offline/dry by default) and ingest via DT-P4."""
    adapter = _adapter("code_verification")
    authorized = is_sandbox_authorized()
    if execute and not authorized:
        raise CognisphereIntegrationError("sandbox_unauthorized")
    if adapter.get("require_authorized_or_offline") and not offline_simulated and not authorized:
        raise CognisphereIntegrationError("sandbox_unauthorized")

    mod = load_runtime_module("code_verification", root=root, client=client)
    if outcome is not None:
        analysis = _call(mod, str(adapter["analyze"]), outcome, **kwargs)
        verification = {"status": "ok", "analysis": analysis, "outcome": outcome}
    else:
        call_kwargs = dict(kwargs)
        call_kwargs["source_code"] = source_code
        call_kwargs["execute"] = execute and authorized
        verification = _call(mod, str(adapter["verify"]), **call_kwargs)

    if not isinstance(verification, dict):
        raise CognisphereIntegrationError(
            "export_envelope_invalid",
            message="verification returned non-object",
        )

    passed = verification.get("passed")
    if passed is None:
        status = str(verification.get("status") or verification.get("outcome") or "").lower()
        # Categorized dry-runs often return status=ok with per-fixture outcomes.
        passed = status in {"ok", "ac", "passed", "success"} and not any(
            str(item.get("outcome") or "").upper() in {"WA", "RE", "TLE", "CE", "MLE"}
            for item in list(verification.get("results") or [])
            if isinstance(item, dict)
        )

    problem_slug = (
        slug
        or verification.get("problem_slug")
        or verification.get("slug")
        or (outcome or {}).get("problem_slug")
    )
    ingest_payload = {
        "session_id": str(verification.get("session_id") or problem_slug or "sandbox"),
        "slug": problem_slug,
        "passed": bool(passed),
        "status": "passed" if passed else "failed",
        "offline_simulated": offline_simulated or not execute or not authorized,
        "verification": verification,
    }
    ingest = ingest_sandbox_result(ingest_payload)
    return {
        "ok": True,
        "phase": "DT-P4",
        "verification": verification,
        "ingest": ingest,
        "source": "plugin_sandbox_verification_runtime",
    }


def suggest_tutor_focus(
    *,
    problem_slug: str | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """DT-P5: call plugin mistake_memory.suggest_tutor_focus and sync locally."""
    adapter = _adapter("mistake_memory")
    mod = load_runtime_module("mistake_memory", root=root, client=client)
    suggestion = _call(mod, str(adapter["suggest"]), problem_slug=problem_slug)
    if not isinstance(suggestion, dict):
        raise CognisphereIntegrationError(
            "export_envelope_invalid",
            message="suggest_tutor_focus returned non-object",
        )

    sync = sync_mistake_memory(
        {
            "source": "plugin_mistake_memory",
            "slug": suggestion.get("problem_slug") or problem_slug,
            "suggest_tutor_focus": suggestion.get("suggestion"),
            "hint_level": suggestion.get("hint_level"),
            "plugin_result": suggestion,
        }
    )
    return {
        "ok": True,
        "phase": "DT-P5",
        "suggestion": suggestion,
        "sync": sync,
        "source": "plugin_mistake_memory",
        "product_binding": {
            "next_step": "Prefer suggestion + hint_level when starting the next tutor session",
            "capability": "mastery_path",
        },
    }


def plan_skill_path(
    *,
    learner_id: str | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """DT-P5: plan next learning path via plugin skill_graph_runtime."""
    adapter = _adapter("skill_graph")
    mod = load_runtime_module("skill_graph", root=root, client=client)
    plan = _call(mod, str(adapter["plan_path"]), learner_id=learner_id, **kwargs)
    if not isinstance(plan, dict):
        raise CognisphereIntegrationError(
            "export_envelope_invalid",
            message="plan_learning_path returned non-object",
        )

    evidence = {
        "source": "plugin_skill_graph",
        "learner_id": learner_id,
        "path_id": plan.get("path_id") or plan.get("plan_id"),
        "skill_ids": list(plan.get("skill_ids") or plan.get("skills") or []),
        "recommended": plan.get("recommended") or plan.get("sequence") or plan.get("next"),
        "plugin_result": plan,
    }
    mastery = apply_mastery_update(evidence)
    return {
        "ok": True,
        "phase": "DT-P5",
        "plan": plan,
        "mastery": mastery,
        "source": "plugin_skill_graph_runtime",
    }


def run_interview_session(
    *,
    case_id: str | None = None,
    learner_id: str | None = None,
    responses: dict[str, dict[str, Any]] | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
    persist: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """DT-P6: drive offline interview via plugin expert_benchmark_runtime."""
    adapter = _adapter("benchmark")
    try:
        mod = load_runtime_module("benchmark", root=root, client=client)
    except CognisphereIntegrationError as exc:
        return {
            "ok": False,
            "phase": "DT-P6",
            "status": "stubbed",
            "code": "benchmark_unavailable",
            "issues": [exc.code],
            "note": str(exc),
        }

    if responses is not None:
        result = _call(
            mod,
            str(adapter["run_flow"]),
            responses,
            case_id=case_id,
            learner_id=learner_id,
            persist=persist,
            **kwargs,
        )
    else:
        result = _call(
            mod,
            str(adapter["start_interview"]),
            case_id=case_id,
            learner_id=learner_id,
            persist=persist,
            **kwargs,
        )

    if not isinstance(result, dict):
        return {
            "ok": False,
            "phase": "DT-P6",
            "status": "stubbed",
            "code": "benchmark_unavailable",
            "note": "interview runtime returned non-object",
        }

    status = str(result.get("status") or "ok")
    return {
        "ok": status == "ok",
        "phase": "DT-P6",
        "status": "imported" if status == "ok" else status,
        "result": result,
        "source": "plugin_expert_benchmark_runtime",
        "live_llm": False,
        "note": "Offline deterministic interview only; live LLM interviewer remains gated",
    }


def list_benchmark_cases(
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    adapter = _adapter("benchmark")
    try:
        mod = load_runtime_module("benchmark", root=root, client=client)
        cases = _call(mod, str(adapter["list_cases"]), **kwargs)
    except CognisphereIntegrationError as exc:
        return {
            "ok": False,
            "phase": "DT-P6",
            "status": "stubbed",
            "code": "benchmark_unavailable",
            "issues": [exc.code],
        }
    return {
        "ok": True,
        "phase": "DT-P6",
        "cases": cases,
        "source": "plugin_expert_benchmark_runtime",
    }
