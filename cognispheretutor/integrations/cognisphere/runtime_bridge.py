"""DT-P4/P5/P6 — product binding bridge to Cognisphere offline plugin runtimes.

Callbacks in ``runtime_callbacks`` persist events; this module *drives* the
plugin P2–P5 runtimes (Socratic / sandbox / mistake / skill / interview) and
then feeds results through those callbacks.

Domain is always required — Tutor has no default domain. Module paths resolve
from plugin manifest ``runtime_modules`` when present, else
``module_template`` + adapter ``module_key``.
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


def _require_domain(domain: str | None) -> str:
    resolved = str(domain or "").strip()
    if not resolved:
        raise CognisphereIntegrationError(
            "domain_required",
            message=(
                "domain is required; cognisphereTutor has no default domain. "
                "Pass an explicit domain from plugin discovery."
            ),
        )
    return resolved


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


def resolve_adapter_module_path(
    adapter_name: str,
    domain: str,
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> str:
    """Resolve importable module path for ``adapter_name`` under ``domain``.

    Order:
    1. Plugin manifest ``runtime_modules[adapter_name]`` (or nested ``module``)
    2. ``module_template`` + adapter ``module_key``
    3. Legacy absolute ``module`` on the adapter (compat; discouraged)
    """
    adapter = _adapter(adapter_name)
    registry = client or PluginRegistryClient(root)
    try:
        record = registry.get_plugin(domain, root)
        manifest = (record.get("plugin") or {}).get("manifest") or {}
        runtime_modules = manifest.get("runtime_modules")
        if isinstance(runtime_modules, dict):
            declared = runtime_modules.get(adapter_name)
            if isinstance(declared, str) and declared.strip():
                return declared.strip()
            if isinstance(declared, dict):
                mod = str(declared.get("module") or "").strip()
                if mod:
                    return mod
    except CognisphereIntegrationError:
        pass

    module_key = str(adapter.get("module_key") or "").strip()
    template = str(_adapters().get("module_template") or "").strip()
    if template and module_key:
        try:
            return template.format(domain=domain, module_key=module_key)
        except (KeyError, ValueError) as exc:
            raise CognisphereIntegrationError(
                "unknown_capability:" + adapter_name,
                message=f"invalid module_template: {exc}",
                details={"domain": domain, "adapter": adapter_name},
            ) from exc

    # Legacy: absolute module path on adapter (pre-domain-generic manifests).
    legacy = str(adapter.get("module") or "").strip()
    if legacy:
        return legacy

    raise CognisphereIntegrationError(
        "unknown_capability:" + adapter_name,
        message=(
            "cannot resolve runtime module: plugin manifest has no "
            f"runtime_modules.{adapter_name} and adapter lacks module_key/template"
        ),
        details={"domain": domain, "adapter": adapter_name},
    )


def load_runtime_module(
    adapter_name: str,
    *,
    domain: str | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> ModuleType:
    """Import the plugin runtime module for ``domain`` + ``adapter_name``."""
    resolved_domain = _require_domain(domain)
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    registry.ensure_import_paths(domain=resolved_domain, root=plugins_root)
    module_path = resolve_adapter_module_path(
        adapter_name,
        resolved_domain,
        root=plugins_root,
        client=registry,
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
    resolved_domain = _require_domain(domain)
    adapter = _adapter("socratic_tutor")
    lo = int(adapter.get("hint_level_min", 0))
    hi = int(adapter.get("hint_level_max", 4))
    if hint_level < lo or hint_level > hi:
        raise CognisphereIntegrationError(
            "tutor_must_ask_not_spoil",
            message=f"hint_level must be {lo}–{hi}",
            details={"hint_level": hint_level},
        )

    mod = load_runtime_module(
        "socratic_tutor", domain=resolved_domain, root=root, client=client
    )
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
            "domain": resolved_domain,
        },
    )
    status = str(session.get("status") or "ok")
    return {
        "ok": status in {"ok", "started", "in_progress"},
        "phase": "DT-P4",
        "status": status,
        "domain": resolved_domain,
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
    resolved_domain = _require_domain(
        domain or (session.get("domain") if isinstance(session, dict) else None)
    )
    adapter = _adapter("socratic_tutor")
    mod = load_runtime_module(
        "socratic_tutor", domain=resolved_domain, root=root, client=client
    )
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
    if isinstance(payload, dict) and "domain" not in payload:
        payload = dict(payload)
        payload["domain"] = resolved_domain
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
            "domain": resolved_domain,
        },
    )
    return {
        "ok": True,
        "phase": "DT-P4",
        "domain": resolved_domain,
        "session": payload,
        "raw": updated,
        "callback": event_receipt,
        "source": "plugin_socratic_tutor_runtime",
    }


def verify_submission(
    *,
    domain: str | None = None,
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
    resolved_domain = _require_domain(domain)
    adapter = _adapter("code_verification")
    authorized = is_sandbox_authorized()
    if execute and not authorized:
        raise CognisphereIntegrationError("sandbox_unauthorized")
    if adapter.get("require_authorized_or_offline") and not offline_simulated and not authorized:
        raise CognisphereIntegrationError("sandbox_unauthorized")

    mod = load_runtime_module(
        "code_verification", domain=resolved_domain, root=root, client=client
    )
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
        "domain": resolved_domain,
        "verification": verification,
    }
    ingest = ingest_sandbox_result(ingest_payload)
    return {
        "ok": True,
        "phase": "DT-P4",
        "domain": resolved_domain,
        "verification": verification,
        "ingest": ingest,
        "source": "plugin_sandbox_verification_runtime",
    }


def suggest_tutor_focus(
    *,
    domain: str | None = None,
    problem_slug: str | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """DT-P5: call plugin mistake_memory.suggest_tutor_focus and sync locally."""
    resolved_domain = _require_domain(domain)
    adapter = _adapter("mistake_memory")
    mod = load_runtime_module(
        "mistake_memory", domain=resolved_domain, root=root, client=client
    )
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
            "domain": resolved_domain,
            "suggest_tutor_focus": suggestion.get("suggestion"),
            "hint_level": suggestion.get("hint_level"),
            "plugin_result": suggestion,
        }
    )
    return {
        "ok": True,
        "phase": "DT-P5",
        "domain": resolved_domain,
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
    domain: str | None = None,
    learner_id: str | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """DT-P5: plan next learning path via plugin skill_graph_runtime."""
    resolved_domain = _require_domain(domain)
    adapter = _adapter("skill_graph")
    mod = load_runtime_module(
        "skill_graph", domain=resolved_domain, root=root, client=client
    )
    plan = _call(mod, str(adapter["plan_path"]), learner_id=learner_id, **kwargs)
    if not isinstance(plan, dict):
        raise CognisphereIntegrationError(
            "export_envelope_invalid",
            message="plan_learning_path returned non-object",
        )

    evidence = {
        "source": "plugin_skill_graph",
        "learner_id": learner_id,
        "domain": resolved_domain,
        "path_id": plan.get("path_id") or plan.get("plan_id"),
        "skill_ids": list(plan.get("skill_ids") or plan.get("skills") or []),
        "recommended": plan.get("recommended") or plan.get("sequence") or plan.get("next"),
        "plugin_result": plan,
    }
    mastery = apply_mastery_update(evidence)
    return {
        "ok": True,
        "phase": "DT-P5",
        "domain": resolved_domain,
        "plan": plan,
        "mastery": mastery,
        "source": "plugin_skill_graph_runtime",
    }


def run_interview_session(
    *,
    domain: str | None = None,
    case_id: str | None = None,
    learner_id: str | None = None,
    responses: dict[str, dict[str, Any]] | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
    persist: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """DT-P6: drive offline interview via plugin expert_benchmark_runtime."""
    resolved_domain = _require_domain(domain)
    adapter = _adapter("benchmark")
    try:
        mod = load_runtime_module(
            "benchmark", domain=resolved_domain, root=root, client=client
        )
    except CognisphereIntegrationError as exc:
        raise CognisphereIntegrationError(
            "benchmark_unavailable",
            message=str(exc) or "benchmark runtime module unavailable",
            details={
                "phase": "DT-P6",
                "domain": resolved_domain,
                "case_id": case_id,
                "learner_id": learner_id,
                "cause": exc.code,
            },
        ) from exc

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
        raise CognisphereIntegrationError(
            "benchmark_unavailable",
            message="interview runtime returned non-object",
            details={
                "phase": "DT-P6",
                "domain": resolved_domain,
                "case_id": case_id,
                "type": type(result).__name__,
            },
        )

    status = str(result.get("status") or "ok")
    return {
        "ok": status == "ok",
        "phase": "DT-P6",
        "domain": resolved_domain,
        "status": "imported" if status == "ok" else status,
        "result": result,
        "source": "plugin_expert_benchmark_runtime",
        "live_llm": False,
        "note": "Offline deterministic interview only; live LLM interviewer remains gated",
    }


def list_benchmark_cases(
    *,
    domain: str | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    resolved_domain = _require_domain(domain)
    adapter = _adapter("benchmark")
    try:
        mod = load_runtime_module(
            "benchmark", domain=resolved_domain, root=root, client=client
        )
        cases = _call(mod, str(adapter["list_cases"]), **kwargs)
    except CognisphereIntegrationError as exc:
        return {
            "ok": False,
            "phase": "DT-P6",
            "domain": resolved_domain,
            "status": "stubbed",
            "code": "benchmark_unavailable",
            "issues": [exc.code],
        }
    return {
        "ok": True,
        "phase": "DT-P6",
        "domain": resolved_domain,
        "cases": cases,
        "source": "plugin_expert_benchmark_runtime",
    }
