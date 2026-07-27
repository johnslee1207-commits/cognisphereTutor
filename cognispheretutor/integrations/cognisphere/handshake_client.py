"""Thin Tutor client for LearningPlugins HP-003 handshake (SDK SoT).

Prefer ``cognisphere_plugin_sdk.handshake`` when the plugins monorepo / wheel is
importable. Fall back to local discovery + export when SDK is unavailable so
bundled-pack demos keep working offline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError
from cognispheretutor.integrations.cognisphere.registry_client import PluginRegistryClient


CONTRACT_ID = "cognisphere.tutor.learning_plugin_handshake.v1"
# Canonical protocol lives in CognisphereLearningPlugins (not duplicated here).
SOT_DOCS = (
    "CognisphereLearningPlugins/docs/"
    "CognisphereTutor_Learning_Plugin_Contract_Handshake_Protocol_v1.0.md"
)


def _try_sdk_handshake(
    domain: str,
    *,
    root: str | Path | None,
    required_capabilities: list[str],
    goal: str | None,
    topic: str | None,
    check_mode: str,
    client: PluginRegistryClient,
) -> dict[str, Any] | None:
    plugins_root = client.resolve_plugins_root(root)
    try:
        client.ensure_import_paths(domain=domain, root=plugins_root)
        from cognisphere_plugin_sdk.handshake import (  # type: ignore[import-not-found]
            handshake_plugin,
        )
    except Exception:  # noqa: BLE001 — optional SDK
        return None
    try:
        payload = handshake_plugin(
            domain,
            root=plugins_root,
            required_capabilities=required_capabilities,
            goal=goal,
            topic=topic,
            check_mode=check_mode,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "domain": domain,
            "source": "cognisphere_plugin_sdk",
            "issues": [f"sdk_handshake_error:{exc}"],
            "contract": CONTRACT_ID,
            "sot_docs": SOT_DOCS,
        }
    if not isinstance(payload, dict):
        return None
    out = dict(payload)
    out.setdefault("source", "cognisphere_plugin_sdk")
    out.setdefault("contract", CONTRACT_ID)
    out["sot_docs"] = SOT_DOCS
    return out


def _fallback_local_handshake(
    domain: str,
    *,
    root: str | Path | None,
    required_capabilities: list[str],
    client: PluginRegistryClient,
) -> dict[str, Any]:
    """Local thin path when SDK handshake is not importable."""
    from cognispheretutor.integrations.cognisphere.capability_negotiator import negotiate
    from cognispheretutor.integrations.cognisphere.plugin_importer import export_and_import

    issues: list[str] = []
    try:
        record = client.get_plugin(domain, root)
    except CognisphereIntegrationError as exc:
        return {
            "ok": False,
            "domain": domain,
            "source": "tutor_local_fallback",
            "failed_step": "discovery",
            "issues": [exc.code],
            "contract": CONTRACT_ID,
            "sot_docs": SOT_DOCS,
        }

    negotiation = negotiate(
        domain,
        {"required_capabilities": required_capabilities},
        root=root,
        client=client,
    )
    if not negotiation.get("matched"):
        issues.append(
            "capabilities_missing:" + ",".join(str(c) for c in negotiation.get("missing") or [])
        )

    adapter = client.validate_adapter(domain, root=root)
    if not adapter.get("ok"):
        issues.extend(list(adapter.get("issues") or []) or ["adapter_not_ok"])

    export_meta: dict[str, Any] = {}
    try:
        receipt = export_and_import(domain, {"persist": False}, root=root, client=client)
        export_meta = {
            "ok": bool(receipt.get("ok")),
            "bundle_id": (receipt.get("receipt") or {}).get("bundle_id"),
            "bundle": None,
        }
        if not receipt.get("ok"):
            issues.append("export_not_ok")
    except CognisphereIntegrationError as exc:
        issues.append(exc.code)
        export_meta = {"ok": False, "bundle_id": None, "bundle": None}

    ok = not issues and bool(negotiation.get("matched", True)) and bool(adapter.get("ok"))
    return {
        "ok": ok,
        "domain": domain,
        "plugin_id": ((record.get("plugin") or {}).get("manifest") or {}).get("plugin_id"),
        "source": "tutor_local_fallback",
        "steps": {
            "discovery": {"ok": True},
            "capability_query": negotiation,
            "validation": {"adapter": adapter},
        },
        "export": export_meta,
        "issues": issues,
        "contract": CONTRACT_ID,
        "sot_docs": SOT_DOCS,
        "note": "Install/import CognisphereLearningPlugins SDK for full HP-003 reports",
    }


def handshake(
    domain: str,
    *,
    root: str | Path | None = None,
    required_capabilities: list[str] | None = None,
    goal: str | None = None,
    topic: str | None = None,
    check_mode: str = "full",
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Run LearningPlugins handshake; prefer SDK SoT, else local fallback."""
    registry = client or PluginRegistryClient(root)
    caps = list(required_capabilities or ["deeptutor_export"])
    sdk = _try_sdk_handshake(
        domain,
        root=root,
        required_capabilities=caps,
        goal=goal,
        topic=topic,
        check_mode=check_mode,
        client=registry,
    )
    if sdk is not None:
        return sdk
    return _fallback_local_handshake(
        domain,
        root=root,
        required_capabilities=caps,
        client=registry,
    )


def list_domains(*, root: str | Path | None = None, client: PluginRegistryClient | None = None) -> dict[str, Any]:
    """Prefer SDK ``list_handshake_domains``; else Tutor ``list_plugins``."""
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    try:
        registry.ensure_import_paths(root=plugins_root)
        from cognisphere_plugin_sdk.handshake import (  # type: ignore[import-not-found]
            list_handshake_domains,
        )

        payload = list_handshake_domains(root=plugins_root)
        if isinstance(payload, dict):
            out = dict(payload)
            out.setdefault("source", "cognisphere_plugin_sdk")
            out["sot_docs"] = SOT_DOCS
            return out
    except Exception:  # noqa: BLE001
        pass

    discovery = registry.list_plugins(root)
    plugins = []
    for item in discovery.get("plugins") or []:
        manifest = item.get("manifest") or {}
        plugins.append(
            {
                "domain": item.get("domain"),
                "plugin_id": manifest.get("plugin_id"),
                "version": manifest.get("version"),
                "capabilities": list(manifest.get("capabilities") or []),
                "deeptutor_entrypoint": manifest.get("deeptutor_entrypoint"),
                "lifecycle": item.get("lifecycle"),
            }
        )
    return {
        "ok": bool(discovery.get("ok")),
        "plugins_root": discovery.get("plugins_root"),
        "plugin_count": len(plugins),
        "plugins": plugins,
        "issues": list(discovery.get("issues") or []),
        "source": "tutor_local_fallback",
        "contract": CONTRACT_ID,
        "sot_docs": SOT_DOCS,
    }


COMBINED_FLOW_CONTRACT = "cognisphere.tutor.learning_twin_combined.v1"
COMBINED_SOT_DOCS = (
    "CognisphereLearningPlugins/docs/DIGITAL_TWIN_PLUGIN_ARCHITECTURE_GAP.md"
    " + Tutor docs/LEARNING_PLUGINS_HANDSHAKE_SOT.md (combined flow pointer)"
)


def list_learning_twin_pairs(
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Prefer SDK ``list_learning_twin_pairs``; else learning list only."""
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    try:
        registry.ensure_import_paths(root=plugins_root)
        from cognisphere_plugin_sdk.learning_twin_flow import (  # type: ignore[import-not-found]
            list_learning_twin_pairs as sdk_list,
        )

        payload = sdk_list(root=plugins_root)
        if isinstance(payload, dict):
            out = dict(payload)
            out.setdefault("source", "cognisphere_plugin_sdk")
            out["sot_docs"] = COMBINED_SOT_DOCS
            return out
    except Exception:  # noqa: BLE001
        pass

    learning = list_domains(root=plugins_root, client=registry)
    return {
        "ok": bool(learning.get("ok")),
        "plugins_root": learning.get("plugins_root"),
        "flow": "learning_then_twin",
        "contract": COMBINED_FLOW_CONTRACT,
        "learning": learning,
        "twin_discovery": {
            "ok": False,
            "plugin_count": 0,
            "domains": [],
            "issues": ["sdk_learning_twin_flow_unavailable"],
        },
        "pairs": [],
        "source": "tutor_local_fallback",
        "sot_docs": COMBINED_SOT_DOCS,
        "note": "Install CognisphereLearningPlugins SDK for twin discover/handshake",
    }


def learning_twin_flow(
    learning_domain: str,
    *,
    root: str | Path | None = None,
    goal: str | None = None,
    topic: str | None = None,
    accept_twin_stubs: bool = True,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Combined DX: list → learning handshake → discover_twin → handshake_twin.

    Prefers SDK ``run_learning_twin_flow``. Twin DT-1/DT-2 stubs are fail-closed
    but tolerated when ``accept_twin_stubs`` is true (default).
    """
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    try:
        registry.ensure_import_paths(domain=learning_domain, root=plugins_root)
        from cognisphere_plugin_sdk.learning_twin_flow import (  # type: ignore[import-not-found]
            run_learning_twin_flow,
        )

        payload = run_learning_twin_flow(
            learning_domain,
            root=plugins_root,
            goal=goal,
            topic=topic,
            accept_twin_stubs=accept_twin_stubs,
        )
        if not isinstance(payload, dict):
            raise TypeError("run_learning_twin_flow returned non-dict")
        out = dict(payload)
        out.setdefault("source", "cognisphere_plugin_sdk")
        out["sot_docs"] = COMBINED_SOT_DOCS
        return out
    except Exception as exc:  # noqa: BLE001
        learning = handshake(
            learning_domain,
            root=plugins_root,
            goal=goal,
            topic=topic,
            client=registry,
        )
        return {
            "ok": bool(learning.get("ok")),
            "flow": "learning_then_twin",
            "contract": COMBINED_FLOW_CONTRACT,
            "learning_domain": learning_domain,
            "twin_domain": None,
            "learning": {"handshake": learning},
            "twin": {
                "discovery": None,
                "handshake": None,
                "skipped": {
                    "reason": "sdk_learning_twin_flow_unavailable",
                    "error": str(exc),
                },
                "stubs_ok": False,
                "negotiation_ok": False,
            },
            "issues": ["sdk_learning_twin_flow_unavailable", str(exc)],
            "summary": {
                "ok": bool(learning.get("ok")),
                "learning_ready": bool(learning.get("ok")),
                "twin_negotiated": False,
                "twin_runtime_ready": False,
                "twin_skipped": True,
                "accept_twin_stubs": accept_twin_stubs,
                "primary_issue": "sdk_learning_twin_flow_unavailable",
            },
            "source": "tutor_local_fallback",
            "sot_docs": COMBINED_SOT_DOCS,
        }
