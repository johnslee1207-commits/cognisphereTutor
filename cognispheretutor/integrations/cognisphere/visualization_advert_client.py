"""Thin Tutor client for twin ``visualization`` capability advert (N-15).

Prefer LearningPlugins SDK ``consume_visualization_advert`` /
``list_visualization_adverts`` / ``run_visualization_advert_smoke``.
Reads advert status only — no twin UI / render pipeline in Tutor or LP.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cognispheretutor.integrations.cognisphere.registry_client import PluginRegistryClient

CONTRACT_ID = "cognisphere.tutor.twin_visualization_advert.v1"
SOT_DOCS = (
    "CognisphereLearningPlugins/manifests/composition/digital_twin_evaluation_model.json"
    " + CognisphereLearningPlugins/packages/cognisphere_plugin_sdk/digital_twin.py"
    " (consume_visualization_advert / list_visualization_adverts / "
    "run_visualization_advert_smoke)"
)


def _fail_closed(
    *,
    reason: str,
    issues: list[str] | None = None,
    twin_domain: str | None = None,
    learning_domain: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "advertised": False,
        "advertisement_only": True,
        "visualization_ui": False,
        "renders_ui": False,
        "mode": "advert_only",
        "capability_token": "visualization",
        "twin_domain": twin_domain,
        "learning_domain": learning_domain,
        "contract": CONTRACT_ID,
        "roadmap_id": "N-15",
        "reason": reason,
        "issues": list(issues or [reason]),
        "source": "tutor_local_fallback",
        "sot_docs": SOT_DOCS,
        "note": "Install CognisphereLearningPlugins SDK to consume twin visualization advert",
    }


def consume_visualization_advert(
    twin_domain: str | None = None,
    *,
    root: str | Path | None = None,
    learning_domain: str | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer SDK ``consume_visualization_advert``; else fail-closed envelope."""
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    try:
        registry.ensure_import_paths(root=plugins_root)
        from cognisphere_plugin_sdk.digital_twin import (  # type: ignore[import-not-found]
            consume_visualization_advert as sdk_consume,
        )

        payload = sdk_consume(
            twin_domain,
            root=plugins_root,
            learning_domain=learning_domain,
        )
        if not isinstance(payload, dict):
            raise TypeError("consume_visualization_advert returned non-dict")
        out = dict(payload)
        out.setdefault("source", "cognisphere_plugin_sdk")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001 — optional SDK
        return _fail_closed(
            reason="sdk_visualization_advert_unavailable",
            issues=["sdk_visualization_advert_unavailable", str(exc)],
            twin_domain=twin_domain,
            learning_domain=learning_domain,
        )


def list_visualization_adverts(
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer SDK ``list_visualization_adverts``; else fail-closed envelope."""
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    try:
        registry.ensure_import_paths(root=plugins_root)
        from cognisphere_plugin_sdk.digital_twin import (  # type: ignore[import-not-found]
            list_visualization_adverts as sdk_list,
        )

        payload = sdk_list(root=plugins_root)
        if not isinstance(payload, dict):
            raise TypeError("list_visualization_adverts returned non-dict")
        out = dict(payload)
        out.setdefault("source", "cognisphere_plugin_sdk")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "plugin_count": 0,
            "advertised_domains": [],
            "adverts": [],
            "issues": ["sdk_visualization_advert_unavailable", str(exc)],
            "contract": CONTRACT_ID,
            "mode": "advert_only",
            "renders_ui": False,
            "roadmap_id": "N-15",
            "source": "tutor_local_fallback",
            "sot_docs": SOT_DOCS,
        }


def visualization_advert_status(
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Thin status alias — same as ``list_visualization_adverts``."""
    return list_visualization_adverts(root=root, client=client)


def run_visualization_advert_smoke(
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer SDK ``run_visualization_advert_smoke``; else fail-closed envelope."""
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    try:
        registry.ensure_import_paths(root=plugins_root)
        from cognisphere_plugin_sdk.digital_twin import (  # type: ignore[import-not-found]
            run_visualization_advert_smoke as sdk_smoke,
        )

        payload = sdk_smoke(root=plugins_root)
        if not isinstance(payload, dict):
            raise TypeError("run_visualization_advert_smoke returned non-dict")
        out = dict(payload)
        out.setdefault("source", "cognisphere_plugin_sdk")
        out.setdefault("contract", CONTRACT_ID)
        out["sot_docs"] = SOT_DOCS
        out["renders_ui"] = False
        return out
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "smoke": "visualization_advert",
            "checks": [],
            "issues": ["sdk_visualization_advert_unavailable", str(exc)],
            "contract": CONTRACT_ID,
            "mode": "advert_only",
            "renders_ui": False,
            "roadmap_id": "N-15",
            "source": "tutor_local_fallback",
            "sot_docs": SOT_DOCS,
        }
