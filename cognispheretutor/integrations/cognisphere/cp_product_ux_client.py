"""Thin Tutor client for AWS CP Product UX contracts (CP-08).

Prefer LearningPlugins twin ``cp_product_ux`` APIs + N-15 viz advert compose.
Contract/status/smoke only — no Tutor or LP twin UI / marketplace.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cognispheretutor.integrations.cognisphere.registry_client import PluginRegistryClient

CONTRACT_ID = "cognisphere.tutor.aws_cp_product_ux.v1"
SOT_DOCS = (
    "CognisphereLearningPlugins/plugins/aws_certification_twin/"
    "manifests/ops/aws_twin_cp_product_ux_profile.json"
    " + product/practitioner/* + cognisphere_plugins.aws_certification_twin.cp_product_ux"
    " (reuses N-15 consume_visualization_advert)"
)
TWIN_DOMAIN = "aws_certification_twin"
ROADMAP_ID = "CP-08"


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
        "marketplace_ui": False,
        "lp_ui": False,
        "visualization_ui": False,
        "renders_ui": False,
        "source": "tutor_local_fallback",
        "sot_docs": SOT_DOCS,
        "note": (
            "Install CognisphereLearningPlugins twin pack for CP Product UX contracts"
        ),
    }


def _import_cp_product_ux(root: Path | None, client: PluginRegistryClient | None):
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    registry.ensure_import_paths(root=plugins_root)
    import cognisphere_plugins.aws_certification_twin.cp_product_ux as mod  # type: ignore[import-not-found]

    return mod, plugins_root


def cp_product_ux_status(
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer twin ``cp_product_ux_status``; else fail-closed envelope."""
    try:
        mod, _ = _import_cp_product_ux(root, client)
        payload = mod.cp_product_ux_status()
        if not isinstance(payload, dict):
            raise TypeError("cp_product_ux_status returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        out["lp_ui"] = False
        out["marketplace_ui"] = False
        out["visualization_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001 — optional twin pack
        return _fail_closed(
            reason="twin_cp_product_ux_unavailable",
            issues=["twin_cp_product_ux_unavailable", str(exc)],
        )


def get_cp_ux_contract_bundle(
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer twin ``get_cp_ux_contract_bundle``."""
    try:
        mod, _ = _import_cp_product_ux(root, client)
        payload = mod.get_cp_ux_contract_bundle()
        if not isinstance(payload, dict):
            raise TypeError("get_cp_ux_contract_bundle returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001
        return _fail_closed(
            reason="twin_cp_product_ux_unavailable",
            issues=["twin_cp_product_ux_unavailable", str(exc)],
        )


def consume_cp_visualization_advert(
    package_id: str | None = None,
    *,
    payload_id: str | None = None,
    experience_id: str | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer twin ``consume_cp_visualization_advert`` (N-15 + CP payloads)."""
    try:
        mod, _ = _import_cp_product_ux(root, client)
        payload = mod.consume_cp_visualization_advert(
            package_id,
            payload_id=payload_id,
            experience_id=experience_id,
        )
        if not isinstance(payload, dict):
            raise TypeError("consume_cp_visualization_advert returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        out["visualization_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001
        return _fail_closed(
            reason="twin_cp_product_ux_unavailable",
            issues=["twin_cp_product_ux_unavailable", str(exc)],
            package_id=package_id,
        )


def run_cp_product_ux_smoke(
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer twin ``run_cp_product_ux_smoke``."""
    try:
        mod, _ = _import_cp_product_ux(root, client)
        payload = mod.run_cp_product_ux_smoke()
        if not isinstance(payload, dict):
            raise TypeError("run_cp_product_ux_smoke returned non-dict")
        out = dict(payload)
        out.setdefault("source", "aws_certification_twin")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001
        return _fail_closed(
            reason="twin_cp_product_ux_unavailable",
            issues=["twin_cp_product_ux_unavailable", str(exc)],
        )
