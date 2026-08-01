"""Thin client for LearningPlugins learning mastery paths catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cognispheretutor.integrations.cognisphere.handshake_client import require_packs_root
from cognispheretutor.integrations.cognisphere.registry_client import PluginRegistryClient

_CATALOG_REL = Path("manifests") / "ops" / "learning_mastery_paths.json"


def _read_catalog_fallback(packs_root: Path) -> dict[str, Any]:
    catalog_path = packs_root / _CATALOG_REL
    if not catalog_path.is_file():
        return {
            "ok": False,
            "plugins_root": str(packs_root),
            "catalog_path": str(catalog_path),
            "path_count": 0,
            "paths": [],
            "path_ids": [],
            "learning_entry_points": [],
            "entry_count": 0,
            "issues": ["learning_mastery_paths_catalog_missing"],
            "source": "tutor_local_fallback",
        }
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {
            "ok": False,
            "plugins_root": str(packs_root),
            "catalog_path": str(catalog_path),
            "path_count": 0,
            "paths": [],
            "path_ids": [],
            "learning_entry_points": [],
            "entry_count": 0,
            "issues": [f"learning_mastery_paths_catalog_invalid:{exc}"],
            "source": "tutor_local_fallback",
        }
    paths = [p for p in list(catalog.get("paths") or []) if isinstance(p, dict)]
    entries = []
    for item in paths:
        start = item.get("start") if isinstance(item.get("start"), dict) else {}
        entries.append(
            {
                "path_id": item.get("path_id"),
                "display_name": item.get("display_name") or item.get("path_id"),
                "kind": item.get("kind"),
                "domain": item.get("domain"),
                "twin_domain": item.get("twin_domain"),
                "in_learning_discover_plugins": item.get("in_learning_discover_plugins"),
                "discovery_channel": item.get("discovery_channel"),
                "start_cli": start.get("cognisphere_cli") or start.get("alias_cli"),
                "load_cli": start.get("load_cli"),
                "tutor_cli": start.get("tutor_cli"),
                "tutor_api": start.get("tutor_api") or start.get("tutor_paths_api"),
                "guided_learning_url": start.get("guided_learning_url"),
                "fail_closed_composition_roles": item.get(
                    "fail_closed_composition_roles"
                )
                or [],
            }
        )
    return {
        "ok": True,
        "plugins_root": str(packs_root),
        "catalog_path": str(catalog_path),
        "catalog_id": catalog.get("catalog_id"),
        "path_count": len(paths),
        "paths": paths,
        "path_ids": [str(p.get("path_id")) for p in paths if p.get("path_id")],
        "learning_entry_points": entries,
        "entry_count": len(entries),
        "host_cli": catalog.get("host_cli") or {},
        "tutor_cli": catalog.get("tutor_cli") or {},
        "issues": [],
        "source": "tutor_local_fallback",
        "note": catalog.get("note"),
    }


def list_learning_mastery_paths(
    root: str | Path | None = None,
    *,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """List learning entry points (3 domains + AWS DT mastery). Fail-closed without root."""
    packs_root = require_packs_root(root)
    registry = client or PluginRegistryClient()
    try:
        registry.ensure_import_paths(packs_root)
    except Exception:  # noqa: BLE001 — catalog read does not need imports
        pass

    try:
        from cognisphere_plugin_sdk.learning_mastery_paths import (  # type: ignore[import-not-found]
            describe_learning_entry_points,
            list_learning_mastery_paths as _sdk_list,
        )

        listing = _sdk_list(packs_root)
        described = describe_learning_entry_points(packs_root)
        out = {
            **described,
            "paths": listing.get("paths") or [],
            "path_count": listing.get("path_count") or described.get("entry_count") or 0,
            "catalog_id": listing.get("catalog_id") or described.get("catalog_id"),
            "host_cli": listing.get("host_cli") or {},
            "tutor_cli": listing.get("tutor_cli") or {},
            "source": "cognisphere_plugin_sdk",
        }
    except Exception:  # noqa: BLE001
        out = _read_catalog_fallback(packs_root)

    out.setdefault(
        "guided_learning",
        {
            "handshake_api": "GET|POST /api/v1/learning/cognisphere/handshake",
            "paths_api": "GET /api/v1/learning/cognisphere/paths",
            "aws_twin_api": "GET|POST /api/v1/learning/cognisphere/aws-twin-mastery",
            "ui": "/space/learning",
            "aws_twin_ui": "/space/learning?panel=aws-twin",
        },
    )
    return out


def start_learning_mastery_path(
    path_id: str,
    *,
    root: str | Path | None = None,
    status_only: bool = False,
    skip_tutor: bool = False,
    skip_acceptance: bool = False,
    include_mvp: bool = False,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Start a mastery path; AWS DT aliases aws-twin-mastery."""
    packs_root = require_packs_root(root)
    registry = client or PluginRegistryClient()
    try:
        registry.ensure_import_paths(packs_root)
    except Exception:  # noqa: BLE001
        pass
    key = (path_id or "").strip()
    path: dict[str, Any] | None = None
    try:
        from cognisphere_plugin_sdk.learning_mastery_paths import (  # type: ignore[import-not-found]
            get_learning_mastery_path,
        )

        path = get_learning_mastery_path(key, packs_root)
    except Exception:  # noqa: BLE001
        listing = _read_catalog_fallback(packs_root)
        for item in listing.get("paths") or []:
            if item.get("path_id") == key or key in list(item.get("aliases") or []):
                path = item
                break

    if path is None:
        listing = list_learning_mastery_paths(root=packs_root, client=registry)
        return {
            "ok": False,
            "status": "blocked",
            "error": "learning_mastery_path_not_found",
            "path_id": key,
            "known_path_ids": listing.get("path_ids") or [],
            "issues": ["learning_mastery_path_not_found"],
        }

    resolved = str(path.get("path_id") or key)
    kind = str(path.get("kind") or "")
    if kind == "digital_twin_mastery" or resolved == "aws_digital_twin_mastery":
        from cognispheretutor.integrations.cognisphere.aws_digital_twin_mastery_client import (
            aws_digital_twin_mastery_status,
            run_aws_digital_twin_mastery,
        )

        if status_only:
            payload = aws_digital_twin_mastery_status(root=packs_root, client=registry)
        else:
            payload = run_aws_digital_twin_mastery(
                include_tutor=not skip_tutor,
                include_acceptance=not skip_acceptance,
                include_mvp_product=include_mvp,
                root=packs_root,
                client=registry,
            )
        if isinstance(payload, dict):
            payload = {
                **payload,
                "path_id": resolved,
                "started_via": "cognisphere paths/start",
                "alias_of": "aws-twin-mastery",
            }
        return payload

    from cognispheretutor.integrations.cognisphere.handshake_client import handshake

    domain = str(path.get("domain") or resolved)
    hs = handshake(domain, root=packs_root)
    start = path.get("start") if isinstance(path.get("start"), dict) else {}
    return {
        "ok": bool(hs.get("ok")),
        "status": "ready" if hs.get("ok") else "blocked",
        "path_id": resolved,
        "kind": kind or "learning_domain",
        "domain": domain,
        "handshake": hs,
        "next": {
            "tutor_cli": start.get("tutor_cli"),
            "tutor_api": start.get("tutor_api"),
            "guided_learning_url": start.get("guided_learning_url") or "/space/learning",
        },
        "source": hs.get("source") or "tutor_local_fallback",
    }
