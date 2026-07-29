"""Thin Tutor client for AWS CP Runtime Interaction (CP-04).

Prefer LearningPlugins twin ``runtime_interaction`` APIs. Contract/status only —
no Tutor UI, no live AWS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cognispheretutor.integrations.cognisphere.registry_client import PluginRegistryClient

CONTRACT_ID = "cognisphere.tutor.aws_cp_runtime_interaction.v1"
SOT_DOCS = (
    "CognisphereLearningPlugins/plugins/aws_certification_twin/"
    "manifests/ops/aws_twin_runtime_interaction_profile.json"
    " + cognisphere_plugins.aws_certification_twin.runtime_interaction"
)
TWIN_DOMAIN = "aws_certification_twin"
ROADMAP_ID = "CP-04"


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
        "live_aws_api": False,
        "renders_ui": False,
        "source": "tutor_local_fallback",
        "sot_docs": SOT_DOCS,
        "note": (
            "Install CognisphereLearningPlugins twin pack for CP-04 runtime interaction"
        ),
    }


def _import_runtime(root: Path | None, client: PluginRegistryClient | None):
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    registry.ensure_import_paths(domain=TWIN_DOMAIN, root=plugins_root)
    import cognisphere_plugins.aws_certification_twin.runtime_interaction as mod  # type: ignore[import-not-found]

    return mod, plugins_root


def runtime_interaction_status(
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer twin ``runtime_interaction_status``; else fail-closed envelope."""
    try:
        mod, _ = _import_runtime(root, client)
        payload = mod.runtime_interaction_status()
        if not isinstance(payload, dict):
            raise TypeError("runtime_interaction_status returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001 — optional twin pack
        return _fail_closed(
            reason="twin_runtime_interaction_unavailable",
            issues=["twin_runtime_interaction_unavailable", str(exc)],
        )


def start_package_experience(
    package_id: str | None = None,
    *,
    composition_intent: str | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer twin ``start_package_experience``."""
    try:
        mod, _ = _import_runtime(root, client)
        payload = mod.start_package_experience(
            package_id,
            composition_intent=composition_intent,
        )
        if not isinstance(payload, dict):
            raise TypeError("start_package_experience returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001
        return _fail_closed(
            reason="twin_runtime_interaction_unavailable",
            issues=["twin_runtime_interaction_unavailable", str(exc)],
            package_id=package_id,
        )


def step_package_experience(
    session: dict[str, Any],
    step: str,
    *,
    choice_id: str | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer twin ``step_package_experience``."""
    try:
        mod, _ = _import_runtime(root, client)
        payload = mod.step_package_experience(
            session,
            step,
            choice_id=choice_id,
        )
        if not isinstance(payload, dict):
            raise TypeError("step_package_experience returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001
        return _fail_closed(
            reason="twin_runtime_interaction_unavailable",
            issues=["twin_runtime_interaction_unavailable", str(exc)],
        )


def run_package_experience(
    package_id: str | None = None,
    *,
    choice_id: str | None = None,
    composition_intent: str | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer twin ``run_package_experience`` (Explore→Why)."""
    try:
        mod, _ = _import_runtime(root, client)
        payload = mod.run_package_experience(
            package_id,
            choice_id=choice_id,
            composition_intent=composition_intent,
        )
        if not isinstance(payload, dict):
            raise TypeError("run_package_experience returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001
        return _fail_closed(
            reason="twin_runtime_interaction_unavailable",
            issues=["twin_runtime_interaction_unavailable", str(exc)],
            package_id=package_id,
        )
