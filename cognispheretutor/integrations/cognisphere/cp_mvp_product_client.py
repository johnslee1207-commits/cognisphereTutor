"""Thin Tutor client for AWS twin MVP product flow (MVP-2).

Prefer LearningPlugins twin ``product_mvp`` APIs. Fixture-only by default —
no Tutor UI, no live AWS/LLM.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cognispheretutor.integrations.cognisphere.registry_client import PluginRegistryClient

CONTRACT_ID = "cognisphere.tutor.aws_twin_mvp_product.v1"
SOT_DOCS = (
    "CognisphereLearningPlugins/plugins/aws_certification_twin/"
    "manifests/ops/aws_twin_mvp_product_profile.json"
    " + cognisphere_plugins.aws_certification_twin.product_mvp"
)
TWIN_DOMAIN = "aws_certification_twin"
ROADMAP_ID = "MVP-2"


def _fail_closed(
    *,
    reason: str,
    issues: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "blocked",
        "error": reason,
        "issues": list(issues or [reason]),
        "contract": CONTRACT_ID,
        "roadmap_id": ROADMAP_ID,
        "domain": TWIN_DOMAIN,
        "live_aws_api": False,
        "renders_ui": False,
        "marketplace_ui": False,
        "source": "tutor_local_fallback",
        "sot_docs": SOT_DOCS,
        "note": (
            "Install CognisphereLearningPlugins twin pack for MVP-2 product flow"
        ),
    }


def _import_mvp(root: Path | None, client: PluginRegistryClient | None):
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    registry.ensure_import_paths(domain=TWIN_DOMAIN, root=plugins_root)
    import cognisphere_plugins.aws_certification_twin.product_mvp as mod  # type: ignore[import-not-found]

    return mod, plugins_root


def mvp_product_status(
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer twin ``mvp_product_status``; else fail-closed envelope."""
    try:
        mod, _ = _import_mvp(root, client)
        payload = mod.mvp_product_status()
        if not isinstance(payload, dict):
            raise TypeError("mvp_product_status returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001
        return _fail_closed(
            reason="twin_mvp_product_unavailable",
            issues=["twin_mvp_product_unavailable", str(exc)],
        )


def run_mvp_product_flow(
    requirement: dict[str, Any] | str | None = None,
    *,
    mode: str = "fixture",
    ux_scenario: str = "architecture_design",
    run_failure_drill: bool = True,
    composition_intent: str | None = None,
    use_llm: bool = False,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer twin ``run_mvp_product_flow`` (fixture default)."""
    try:
        mod, _ = _import_mvp(root, client)
        payload = mod.run_mvp_product_flow(
            requirement,
            mode=mode,
            ux_scenario=ux_scenario,
            run_failure_drill=run_failure_drill,
            composition_intent=composition_intent,
            use_llm=use_llm,
        )
        if not isinstance(payload, dict):
            raise TypeError("run_mvp_product_flow returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001
        return _fail_closed(
            reason="twin_mvp_product_unavailable",
            issues=["twin_mvp_product_unavailable", str(exc)],
        )
