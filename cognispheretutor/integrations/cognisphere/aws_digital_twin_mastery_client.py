"""Unified offline façade: AWS Digital Twin Practitioner mastery path.

Discovers/binds ``aws_certification_twin`` and runs profile-driven mastery
(CP-04 → optional CP-06/CP-12/MVP-2). Stable envelope for Cognisphere/Tutor.
No Tutor UI ceremony, no live AWS/LLM on the default path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cognispheretutor.integrations.cognisphere.registry_client import PluginRegistryClient

CONTRACT_ID = "cognisphere.tutor.aws_digital_twin_mastery.v1"
SOT_DOCS = (
    "CognisphereLearningPlugins/plugins/aws_certification_twin/"
    "manifests/ops/aws_twin_digital_twin_mastery_profile.json"
    " + cognisphere_plugins.aws_certification_twin.practitioner_mastery_path"
)
TWIN_DOMAIN = "aws_certification_twin"
PATH_ID = "aws_digital_twin_mastery"


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
        "path": PATH_ID,
        "package_id": package_id,
        "contract": CONTRACT_ID,
        "domain": TWIN_DOMAIN,
        "live_aws_api": False,
        "use_llm": False,
        "mastery_writeback": False,
        "ct08_write_back": False,
        "renders_ui": False,
        "marketplace_ui": False,
        "twin_ui": False,
        "source": "tutor_local_fallback",
        "sot_docs": SOT_DOCS,
        "note": (
            "Install CognisphereLearningPlugins twin pack to run AWS digital twin mastery"
        ),
    }


def _import_mastery(root: Path | None, client: PluginRegistryClient | None):
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    registry.ensure_import_paths(domain=TWIN_DOMAIN, root=plugins_root)
    import cognisphere_plugins.aws_certification_twin.practitioner_mastery_path as mod  # type: ignore[import-not-found]

    return mod, plugins_root


def aws_digital_twin_mastery_status(
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer twin ``aws_digital_twin_mastery_status``; else fail-closed."""
    try:
        mod, _ = _import_mastery(root, client)
        payload = mod.aws_digital_twin_mastery_status()
        if not isinstance(payload, dict):
            raise TypeError("aws_digital_twin_mastery_status returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["path"] = PATH_ID
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        out["mastery_writeback"] = False
        out["ct08_write_back"] = False
        return out
    except Exception as exc:  # noqa: BLE001
        return _fail_closed(
            reason="twin_digital_twin_mastery_unavailable",
            issues=["twin_digital_twin_mastery_unavailable", str(exc)],
        )


def run_aws_digital_twin_mastery(
    *,
    package_id: str | None = None,
    choice_id: str | None = None,
    include_tutor: bool = True,
    include_acceptance: bool = True,
    include_mvp_product: bool = False,
    use_llm: bool = False,
    mastery_writeback: bool = False,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Run offline Practitioner mastery path via twin pack API."""
    try:
        mod, _ = _import_mastery(root, client)
        payload = mod.run_aws_digital_twin_mastery(
            package_id=package_id,
            choice_id=choice_id,
            include_tutor=include_tutor,
            include_acceptance=include_acceptance,
            include_mvp_product=include_mvp_product,
            use_llm=use_llm,
            mastery_writeback=mastery_writeback,
        )
        if not isinstance(payload, dict):
            raise TypeError("run_aws_digital_twin_mastery returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["path"] = PATH_ID
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001
        return _fail_closed(
            reason="twin_digital_twin_mastery_unavailable",
            issues=["twin_digital_twin_mastery_unavailable", str(exc)],
            package_id=package_id,
        )
