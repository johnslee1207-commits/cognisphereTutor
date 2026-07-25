"""Capability negotiation against Cognisphere domain learning plugins."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cognispheretutor.integrations.cognisphere._contract import load_plugin_contract
from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError
from cognispheretutor.integrations.cognisphere.registry_client import PluginRegistryClient


def negotiate(
    domain: str,
    request: dict[str, Any] | None = None,
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Negotiate required capabilities for one domain.

    Prefers the plugin ``negotiate_capabilities`` entrypoint; falls back to
    manifest-local matching when the entrypoint is unavailable.
    """
    registry = client or PluginRegistryClient(root)
    req = dict(request or {})
    try:
        record = registry.get_plugin(domain, root)
    except CognisphereIntegrationError as exc:
        return {
            "plugin": None,
            "domain": domain,
            "available": [],
            "required": list(req.get("required_capabilities") or []),
            "missing": list(req.get("required_capabilities") or []),
            "matched": False,
            "forbidden_in_plugin": list(load_plugin_contract()["forbidden_in_plugin"]),
            "ok": False,
            "issues": [exc.code],
        }

    manifest = (record.get("plugin") or {}).get("manifest") or {}
    try:
        mod = registry.load_deeptutor_entrypoint(domain, root=record.get("plugins_root"))
        if callable(getattr(mod, "negotiate_capabilities", None)):
            result = mod.negotiate_capabilities(req)
            if isinstance(result, dict):
                payload = dict(result)
                payload.setdefault("plugin", manifest.get("plugin_id"))
                payload.setdefault("domain", manifest.get("domain") or domain)
                payload.setdefault(
                    "forbidden_in_plugin",
                    list(manifest.get("forbidden_in_plugin") or load_plugin_contract()["forbidden_in_plugin"]),
                )
                payload["ok"] = True
                return payload
    except CognisphereIntegrationError:
        pass

    return negotiate_from_manifest(manifest, req)


def negotiate_from_manifest(
    manifest: dict[str, Any],
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    req = request or {}
    required = list(req.get("required_capabilities") or [])
    available = list(manifest.get("capabilities") or [])
    missing = [cap for cap in required if cap not in available]
    return {
        "plugin": manifest.get("plugin_id"),
        "domain": manifest.get("domain"),
        "available": available,
        "required": required,
        "missing": missing,
        "matched": not missing,
        "forbidden_in_plugin": list(
            manifest.get("forbidden_in_plugin") or load_plugin_contract()["forbidden_in_plugin"]
        ),
        "ok": True,
        "goal": req.get("goal"),
    }


def query_cross_domain(
    request: dict[str, Any] | None = None,
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """DT-P6 cross-domain capability query (local discovery + optional SDK)."""
    registry = client or PluginRegistryClient(root)
    req = request or {}
    required = list(req.get("required_capabilities") or [])
    goal = str(req.get("goal") or "")
    plugins_root = registry.resolve_plugins_root(root)

    # Prefer Cognisphere SDK when importable from the plugins monorepo.
    try:
        registry.ensure_import_paths(root=plugins_root)
        from cognisphere_plugin_sdk.entrypoint_surface import (  # type: ignore[import-not-found]
            query_cross_domain_capabilities,
        )

        sdk_result = query_cross_domain_capabilities(req, root=plugins_root)
        if isinstance(sdk_result, dict):
            payload = dict(sdk_result)
            payload.setdefault("source", "cognisphere_plugin_sdk")
            payload.setdefault("phase", "DT-P6")
            return payload
    except Exception:  # noqa: BLE001 — fall back to local discovery
        pass

    discovery = registry.list_plugins(root)
    matches: list[dict[str, Any]] = []
    for item in discovery.get("plugins") or []:
        manifest = item.get("manifest") or {}
        negotiation = negotiate_from_manifest(manifest, req)
        if required and not negotiation.get("matched"):
            continue
        matches.append(
            {
                "domain": item.get("domain"),
                "plugin_id": manifest.get("plugin_id"),
                "lifecycle": item.get("lifecycle"),
                "available": negotiation.get("available"),
                "matched": negotiation.get("matched"),
                "in_registry": bool(item.get("in_registry")),
                "deeptutor_entrypoint": manifest.get("deeptutor_entrypoint"),
                "cognisphere_entrypoint": manifest.get("cognisphere_entrypoint"),
            }
        )
    return {
        "ok": bool(discovery.get("ok")),
        "goal": goal,
        "required_capabilities": required,
        "plugins_root": discovery.get("plugins_root"),
        "match_count": len(matches),
        "matches": matches,
        "discovery_issues": list(discovery.get("issues") or []),
        "contract": "deeptutor.cognisphere.cross_domain_capability_query.v1",
        "source": "local_registry",
        "phase": "DT-P6",
    }


def compose_contexts(
    domains: list[str] | None = None,
    *,
    required_capabilities: list[str] | None = None,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """DT-P6 compose multi-domain learning contexts (SDK when available)."""
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    domain_list = list(domains or [])
    caps = list(required_capabilities or [])

    try:
        registry.ensure_import_paths(root=plugins_root)
        from cognisphere_plugin_sdk.entrypoint_surface import (  # type: ignore[import-not-found]
            compose_plugin_contexts,
        )

        sdk = compose_plugin_contexts(
            domain_list or None,
            root=plugins_root,
            required_capabilities=caps or None,
        )
        if isinstance(sdk, dict):
            payload = dict(sdk)
            payload.setdefault("source", "cognisphere_plugin_sdk")
            payload.setdefault("phase", "DT-P6")
            return payload
    except Exception as exc:  # noqa: BLE001
        sdk_error = str(exc)
    else:
        sdk_error = None

    # Local composition: negotiate each domain and assemble a thin context envelope.
    selected: list[dict[str, Any]] = []
    issues: list[str] = []
    if not domain_list and caps:
        cross = query_cross_domain({"required_capabilities": caps}, root=root, client=registry)
        domain_list = [m["domain"] for m in cross.get("matches") or [] if m.get("domain")]

    for domain in domain_list:
        try:
            negotiation = negotiate(
                domain,
                {"required_capabilities": caps} if caps else {},
                root=root,
                client=registry,
            )
            info = registry.get_plugin(domain, root)
            selected.append(
                {
                    "domain": domain,
                    "plugin_id": (info.get("plugin") or {}).get("manifest", {}).get("plugin_id"),
                    "negotiation": negotiation,
                    "matched": bool(negotiation.get("matched")),
                }
            )
            if caps and not negotiation.get("matched"):
                issues.append(f"capability_mismatch:{domain}")
        except CognisphereIntegrationError as exc:
            issues.append(f"{domain}:{exc.code}")

    return {
        "ok": not issues and bool(selected),
        "phase": "DT-P6",
        "source": "local_compose",
        "domains": domain_list,
        "required_capabilities": caps,
        "contexts": selected,
        "issues": issues,
        "sdk_error": sdk_error,
        "plugins_root": str(plugins_root),
        "blocker": None
        if selected
        else {
            "code": "benchmark_unavailable",
            "note": "No domains composed; interview/benchmark import remains optional deepening",
        },
    }


def import_benchmark_case(
    domain: str,
    case: dict[str, Any] | None = None,
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """DT-P6 benchmark/interview import — domain-agnostic bridge then entrypoint.

    Never returns a silent ``stubbed`` success envelope: when the runtime or
    entrypoint is missing, raises ``CognisphereIntegrationError`` so CLI/API
    surfaces a hard failure instead of a soft stub.
    """
    from cognispheretutor.integrations.cognisphere.runtime_bridge import run_interview_session

    resolved = str(domain or "").strip()
    if not resolved:
        raise CognisphereIntegrationError(
            "domain_required",
            message="domain is required for benchmark import; no default domain",
        )

    case_payload = case if isinstance(case, dict) else {}
    case_id = case_payload.get("case_id") or case_payload.get("id")
    learner_id = case_payload.get("learner_id")

    # Prefer expert_benchmark_runtime via domain-resolved adapters (all domains).
    try:
        started = run_interview_session(
            domain=resolved,
            case_id=case_id,
            learner_id=learner_id,
            responses=case_payload.get("responses") if case_payload.get("run_flow") else None,
            root=root,
            client=client,
            persist=bool(case_payload.get("persist", False)),
        )
        started = dict(started)
        started.setdefault("domain", resolved)
        return started
    except CognisphereIntegrationError as bridge_exc:
        # Fall back to deeptutor entrypoint only when the bridge module is unavailable.
        if bridge_exc.code not in {
            "benchmark_unavailable",
            "plugins_root_missing",
            "entrypoint_import_failed",
        }:
            raise

    registry = client or PluginRegistryClient(root)
    try:
        mod = registry.load_deeptutor_entrypoint(resolved, root=root)
    except CognisphereIntegrationError as exc:
        raise CognisphereIntegrationError(
            "benchmark_unavailable",
            message=f"No benchmark runtime or deeptutor entrypoint for domain {resolved!r}",
            details={"domain": resolved, "phase": "DT-P6", "cause": exc.code},
        ) from exc

    for name in ("import_benchmark_case", "run_interview_session", "export_interview_package"):
        fn = getattr(mod, name, None)
        if callable(fn):
            try:
                result = fn(case) if case is not None else fn()
            except TypeError:
                result = fn()
            return {
                "ok": True,
                "phase": "DT-P6",
                "status": "imported",
                "domain": resolved,
                "entrypoint": name,
                "result": result,
            }

    raise CognisphereIntegrationError(
        "benchmark_unavailable",
        message=(
            "Plugin does not expose benchmark/interview import "
            "(runtime adapter or import_benchmark_case / run_interview_session / "
            "export_interview_package)"
        ),
        details={"domain": resolved, "phase": "DT-P6"},
    )
