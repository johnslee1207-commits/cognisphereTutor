"""Thin Tutor client for AWS CP Socratic tutor flows (CP-06).

Prefer LearningPlugins twin ``cp_socratic_tutor`` APIs. Contract/status only —
no Tutor UI, no CT-08 mastery write-back, no silent live LLM.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cognispheretutor.integrations.cognisphere.registry_client import PluginRegistryClient

CONTRACT_ID = "cognisphere.tutor.aws_cp_socratic_tutor.v1"
SOT_DOCS = (
    "CognisphereLearningPlugins/plugins/aws_certification_twin/"
    "manifests/ops/aws_twin_cp_socratic_tutor_profile.json"
    " + cognisphere_plugins.aws_certification_twin.cp_socratic_tutor"
)
TWIN_DOMAIN = "aws_certification_twin"
ROADMAP_ID = "CP-06"


def _fail_closed(
    *,
    reason: str,
    issues: list[str] | None = None,
    package_id: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "blocked",
        "error": reason,
        "issues": list(issues or [reason]),
        "package_id": package_id,
        "contract": CONTRACT_ID,
        "roadmap_id": ROADMAP_ID,
        "domain": TWIN_DOMAIN,
        "mastery_writeback": False,
        "ct08_write_back": False,
        "renders_ui": False,
        "source": "tutor_local_fallback",
        "sot_docs": SOT_DOCS,
        "note": (
            "Install CognisphereLearningPlugins twin pack to drive CP Socratic flows"
        ),
    }


def _import_cp_tutor(root: Path | None, client: PluginRegistryClient | None):
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    registry.ensure_import_paths(root=plugins_root)
    import cognisphere_plugins.aws_certification_twin.cp_socratic_tutor as mod  # type: ignore[import-not-found]

    return mod, plugins_root


def cp_socratic_tutor_status(
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer twin ``cp_socratic_tutor_status``; else fail-closed envelope."""
    try:
        mod, _ = _import_cp_tutor(root, client)
        payload = mod.cp_socratic_tutor_status()
        if not isinstance(payload, dict):
            raise TypeError("cp_socratic_tutor_status returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        out["mastery_writeback"] = False
        out["ct08_write_back"] = False
        return out
    except Exception as exc:  # noqa: BLE001 — optional twin pack
        return _fail_closed(
            reason="twin_cp_socratic_tutor_unavailable",
            issues=["twin_cp_socratic_tutor_unavailable", str(exc)],
        )


def start_cp_tutor_session(
    package_id: str | None = None,
    *,
    flow_id: str | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
    use_llm: bool = False,
    llm_caller: Any | None = None,
) -> dict[str, Any]:
    """Prefer twin ``start_cp_tutor_session``; else fail-closed envelope."""
    try:
        mod, _ = _import_cp_tutor(root, client)
        payload = mod.start_cp_tutor_session(
            package_id,
            flow_id=flow_id,
            use_llm=use_llm,
            llm_caller=llm_caller,
        )
        if not isinstance(payload, dict):
            raise TypeError("start_cp_tutor_session returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001
        return _fail_closed(
            reason="twin_cp_socratic_tutor_unavailable",
            issues=["twin_cp_socratic_tutor_unavailable", str(exc)],
            package_id=package_id,
        )


def advance_cp_tutor_turn(
    session: dict[str, Any],
    *,
    event: str = "manual_advance",
    learner_reply: str | None = None,
    choice_id: str | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer twin ``advance_cp_tutor_turn``; else fail-closed envelope."""
    try:
        mod, _ = _import_cp_tutor(root, client)
        payload = mod.advance_cp_tutor_turn(
            session,
            event=event,
            learner_reply=learner_reply,
            choice_id=choice_id,
        )
        if not isinstance(payload, dict):
            raise TypeError("advance_cp_tutor_turn returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001
        return _fail_closed(
            reason="twin_cp_socratic_tutor_unavailable",
            issues=["twin_cp_socratic_tutor_unavailable", str(exc)],
        )


def request_cp_tutor_llm_turn(
    session: dict[str, Any],
    *,
    use_llm: bool = False,
    llm_caller: Any | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer twin ``request_cp_tutor_llm_turn`` (N-02 fail-closed)."""
    try:
        mod, _ = _import_cp_tutor(root, client)
        payload = mod.request_cp_tutor_llm_turn(
            session,
            use_llm=use_llm,
            llm_caller=llm_caller,
        )
        if not isinstance(payload, dict):
            raise TypeError("request_cp_tutor_llm_turn returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        return out
    except Exception as exc:  # noqa: BLE001
        return _fail_closed(
            reason="twin_cp_socratic_tutor_unavailable",
            issues=["twin_cp_socratic_tutor_unavailable", str(exc)],
        )
