"""Thin Tutor client for Cognisphere Context API bind (LearningPlugins SDK SoT).

Prefer ``cognisphere_plugin_sdk.context_api`` when the plugins monorepo / wheel is
importable. Without SDK or host base URL, stay fail-closed (no invented GraphQL).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cognispheretutor.integrations.cognisphere.registry_client import PluginRegistryClient

CONTRACT_ID = "cognisphere.ops.context_api_boundary.v1"
HOST_ENDPOINTS_CONTRACT = "cognisphere.ops.context_api_host_endpoints.v1"
SOT_DOCS = (
    "CognisphereLearningPlugins/manifests/ops/context_api_boundary.json"
    " + CognisphereLearningPlugins/packages/cognisphere_plugin_sdk/context_api.py"
)
BASE_URL_ENV = "COGNISPHERE_CONTEXT_API_BASE_URL"


def _fail_closed_status(*, reason: str, issues: list[str] | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "bound": False,
        "client_mode": "fail_closed",
        "stub_mode": "fail_closed",
        "live_graphql": False,
        "reason": reason,
        "base_url_env": BASE_URL_ENV,
        "contract": CONTRACT_ID,
        "host_endpoint_contract_id": HOST_ENDPOINTS_CONTRACT,
        "issues": list(issues or []),
        "source": "tutor_local_fallback",
        "sot_docs": SOT_DOCS,
        "note": "Install CognisphereLearningPlugins SDK; set "
        f"{BASE_URL_ENV} to bind Cognisphere host Context API",
    }


def context_api_status(
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer SDK ``context_api_status``; else fail-closed local envelope."""
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    try:
        registry.ensure_import_paths(root=plugins_root)
        from cognisphere_plugin_sdk.context_api import (  # type: ignore[import-not-found]
            context_api_status as sdk_status,
        )

        payload = sdk_status(root=plugins_root)
        if not isinstance(payload, dict):
            raise TypeError("context_api_status returned non-dict")
        out = dict(payload)
        out.setdefault("source", "cognisphere_plugin_sdk")
        if not out.get("contract"):
            out["contract"] = CONTRACT_ID
        if not out.get("host_endpoint_contract_id"):
            out["host_endpoint_contract_id"] = HOST_ENDPOINTS_CONTRACT
        out["sot_docs"] = SOT_DOCS
        return out
    except Exception as exc:  # noqa: BLE001 — optional SDK
        status = _fail_closed_status(
            reason="sdk_context_api_unavailable",
            issues=["sdk_context_api_unavailable", str(exc)],
        )
        status["ok"] = False
        return status


def bind_context_api(
    *,
    base_url: str | None = None,
    transport: Any | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
    probe: bool = True,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Optional host bind via SDK ``try_bind_cognisphere_context_api_client``.

    Absent base URL / SDK → fail-closed (``bound=False``, ``ok=True`` when
    intentionally unbound). Probe failure returns ``ok=False`` and stays unbound.
    """
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    try:
        registry.ensure_import_paths(root=plugins_root)
        from cognisphere_plugin_sdk.context_api import (  # type: ignore[import-not-found]
            try_bind_cognisphere_context_api_client,
        )

        payload = try_bind_cognisphere_context_api_client(
            base_url=base_url,
            transport=transport,
            headers=headers,
            timeout=timeout,
            probe=probe,
            root=plugins_root,
        )
        if not isinstance(payload, dict):
            raise TypeError("try_bind_cognisphere_context_api_client returned non-dict")
        out = dict(payload)
        out.setdefault("source", "cognisphere_plugin_sdk")
        if not out.get("contract"):
            out["contract"] = CONTRACT_ID
        if not out.get("host_endpoint_contract_id"):
            out["host_endpoint_contract_id"] = HOST_ENDPOINTS_CONTRACT
        out["sot_docs"] = SOT_DOCS
        return out
    except Exception as exc:  # noqa: BLE001
        return _fail_closed_status(
            reason="sdk_context_api_unavailable",
            issues=["sdk_context_api_unavailable", str(exc)],
        )


def reset_context_api(
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Restore SDK fail-closed default when available (test / teardown helper)."""
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    try:
        registry.ensure_import_paths(root=plugins_root)
        from cognisphere_plugin_sdk.context_api import (  # type: ignore[import-not-found]
            reset_context_api_client,
        )

        reset_context_api_client()
        return {
            "ok": True,
            "bound": False,
            "client_mode": "fail_closed",
            "source": "cognisphere_plugin_sdk",
            "contract": CONTRACT_ID,
            "sot_docs": SOT_DOCS,
        }
    except Exception as exc:  # noqa: BLE001
        return _fail_closed_status(
            reason="sdk_context_api_unavailable",
            issues=["sdk_context_api_unavailable", str(exc)],
        )
