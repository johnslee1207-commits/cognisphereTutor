"""Bundled Cognisphere learning pack distribution.

This module is the offline distribution layer for public Tutor installs:
external Cognisphere Learning Plugins are preferred when present, while
packaged JSON handoff bundles let a plain ``pip install cognispheretutor`` seed
Mastery Path without cloning Cognisphere or CognisphereLearningPlugins.
"""

from __future__ import annotations

from importlib import resources
import json
from typing import Any

from cognispheretutor.integrations.cognisphere.plugin_importer import (
    import_bundle_json,
    resolve_import_cache_dir,
    validate_bundle_safety,
)

_PACK_DIR = "bundled_packs"
_PACK_SUFFIX = "_bundle.json"


def _bundle_files() -> list[Any]:
    try:
        root = resources.files(__package__).joinpath(_PACK_DIR)
    except Exception:
        return []
    if not root.is_dir():
        return []
    return sorted(root.iterdir(), key=lambda item: item.name)


def _load_json_resource(path: Any) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def list_bundled_packs() -> dict[str, Any]:
    """Return bundled pack records shaped like plugin discovery entries."""
    packs: list[dict[str, Any]] = []
    issues: list[str] = []
    for path in _bundle_files():
        name = str(getattr(path, "name", ""))
        if not name.endswith(_PACK_SUFFIX):
            continue
        bundle = _load_json_resource(path)
        domain = str(bundle.get("domain") or name.removesuffix(_PACK_SUFFIX)).strip()
        if not domain:
            issues.append(f"bundled_pack_domain_missing:{name}")
            continue
        validation = validate_bundle_safety(bundle)
        knowledge = bundle.get("knowledge") if isinstance(bundle.get("knowledge"), dict) else {}
        sparse = _knowledge_is_sparse(knowledge)
        import_status = _bundled_pack_import_status(domain, bundle)
        manifest = {
            "plugin_id": bundle.get("plugin_id") or f"cognisphere.domain.{domain}.bundled_pack",
            "domain": domain,
            "display_name": _display_name(domain),
            "name": _display_name(domain),
            "description": (
                "Bundled Cognisphere learning pack shipped with cognisphereTutor."
            ),
            "version": str(bundle.get("bundle_schema_version") or "1"),
            "capabilities": ["deeptutor_export", "mastery_path_seed"],
            "keywords": _keywords_for_bundle(domain, knowledge),
            "aliases": [domain.replace("_", " "), domain.replace("_", "-")],
        }
        packs.append(
            {
                "domain": domain,
                "path": f"package://cognispheretutor.integrations.cognisphere/{_PACK_DIR}/{name}",
                "manifest_path": None,
                "manifest": manifest,
                "validation": validation,
                "in_registry": False,
                "lifecycle": "bundled",
                "distribution": {
                    "source": "bundled_pack",
                    "package": "cognispheretutor",
                    "bundle_id": bundle.get("bundle_id"),
                    "sparse": sparse,
                    "import_status": import_status,
                },
                "tutor_pack": {
                    "check_command": f"cognispheretutor cognisphere import-seed {domain}",
                    "source_label": "bundled plugin pack",
                },
                "bundle": bundle,
            }
        )
        if not validation.get("ok"):
            issues.extend(f"{domain}:{issue}" for issue in validation.get("issues") or [])
    return {
        "ok": not issues,
        "plugin_count": len(packs),
        "plugins": packs,
        "issues": issues,
        "source": "bundled_pack_distribution",
    }


def get_bundled_pack(domain: str) -> dict[str, Any] | None:
    wanted = str(domain or "").strip()
    if not wanted:
        return None
    for item in list_bundled_packs().get("plugins") or []:
        if item.get("domain") == wanted:
            return item
    return None


def import_bundled_pack(
    domain: str,
    *,
    persist: bool = True,
) -> dict[str, Any] | None:
    """Import a packaged bundle for ``domain`` when available."""
    item = get_bundled_pack(domain)
    if not item:
        return None
    bundle = item.get("bundle")
    if not isinstance(bundle, dict):
        return None
    receipt = import_bundle_json(
        bundle,
        persist=persist,
        export_meta={
            "ok": True,
            "domain": domain,
            "source": "bundled_pack",
            "package": "cognispheretutor",
            "note": "Imported from a bundled Tutor learning pack.",
        },
    )
    receipt["domain"] = domain
    receipt["distribution_source"] = "bundled_pack"
    receipt["bundled_pack"] = {
        "bundle_id": bundle.get("bundle_id"),
        "sparse": _knowledge_is_sparse(
            bundle.get("knowledge") if isinstance(bundle.get("knowledge"), dict) else {}
        ),
    }
    return receipt


def merge_external_and_bundled_discovery(discovery: dict[str, Any]) -> dict[str, Any]:
    """Add bundled packs for domains not discovered from an external plugin root."""
    merged = dict(discovery)
    external = list(merged.get("plugins") or [])
    seen = {str(item.get("domain") or "") for item in external if item.get("domain")}
    bundled = [
        item
        for item in list_bundled_packs().get("plugins") or []
        if item.get("domain") and item.get("domain") not in seen
    ]
    merged["plugins"] = external + bundled
    merged["plugin_count"] = len(merged["plugins"])
    merged["bundled_plugin_count"] = len(bundled)
    merged["bundled_distribution"] = {
        "available": len(bundled),
        "domains": [item.get("domain") for item in bundled],
    }
    if bundled and not merged.get("ok") and not external:
        merged["ok"] = True
    return merged


def _display_name(domain: str) -> str:
    return f"{domain.replace('_', ' ').title()} Learning Pack"


def _keywords_for_bundle(domain: str, knowledge: dict[str, Any]) -> list[str]:
    words = {domain, domain.replace("_", " "), domain.replace("_", "-")}
    for key in ("certification_tracks", "topic_families", "concepts", "skills"):
        value = knowledge.get(key)
        if not isinstance(value, list):
            continue
        for item in value[:12]:
            if isinstance(item, dict):
                label = item.get("label") or item.get("name") or item.get("title")
                if label:
                    words.add(str(label))
    return sorted(words)


def _knowledge_is_sparse(knowledge: dict[str, Any]) -> bool:
    meaningful = 0
    for key, value in knowledge.items():
        if key in {"export_result", "status", "pack_metadata", "surface_evaluability"}:
            continue
        if isinstance(value, list):
            meaningful += len(value)
        elif isinstance(value, dict):
            if isinstance(value.get("items"), list):
                meaningful += len(value["items"])
            elif isinstance(value.get("units"), list):
                meaningful += len(value["units"])
            elif isinstance(value.get("excerpts"), list):
                meaningful += len(value["excerpts"])
            elif value:
                meaningful += 1
    return meaningful <= 1


def _bundled_pack_import_status(domain: str, bundle: dict[str, Any]) -> dict[str, Any]:
    imported_bundle = _load_imported_bundle(domain)
    imported_receipt = _load_import_receipt(domain)
    bundled_counts = _bundle_content_counts(bundle)
    imported_counts = _bundle_content_counts(imported_bundle) if imported_bundle else {}
    imported_at = imported_receipt.get("imported_at") if imported_receipt else None
    installed = bool(imported_bundle or imported_receipt)
    reasons: list[str] = []

    if not installed:
        status = "not_installed"
    else:
        bundled_exported = str(bundle.get("exported_at") or "")
        imported_exported = str(
            (imported_bundle or {}).get("exported_at")
            or (imported_receipt or {}).get("exported_at")
            or ""
        )
        if bundled_exported and imported_exported and bundled_exported > imported_exported:
            reasons.append("newer_exported_at")
        for key, bundled_count in bundled_counts.items():
            imported_count = int(imported_counts.get(key) or 0)
            if bundled_count > imported_count:
                reasons.append(f"more_{key}")
        status = "update_available" if reasons else "current"

    return {
        "installed": installed,
        "status": status,
        "update_available": status == "update_available",
        "reasons": reasons,
        "bundled": {
            "bundle_id": bundle.get("bundle_id"),
            "exported_at": bundle.get("exported_at"),
            "counts": bundled_counts,
        },
        "imported": {
            "bundle_id": (imported_bundle or imported_receipt or {}).get("bundle_id"),
            "exported_at": (
                (imported_bundle or {}).get("exported_at")
                or (imported_receipt or {}).get("exported_at")
            ),
            "imported_at": imported_at,
            "counts": imported_counts,
        },
    }


def _load_imported_bundle(domain: str) -> dict[str, Any] | None:
    try:
        path = resolve_import_cache_dir(domain=domain) / "bundle.json"
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _load_import_receipt(domain: str) -> dict[str, Any] | None:
    try:
        path = resolve_import_cache_dir(domain=domain) / "import_receipt.json"
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _bundle_content_counts(bundle: dict[str, Any] | None) -> dict[str, int]:
    if not isinstance(bundle, dict):
        return {}
    knowledge = bundle.get("knowledge")
    if not isinstance(knowledge, dict):
        return {}
    counts: dict[str, int] = {}
    keys = (
        "mastery_modules",
        "lesson_cards",
        "practice_blueprints",
        "learning_activity_templates",
        "study_sequences",
        "scenario_cards",
        "flashcard_decks",
        "readiness_checkpoints",
        "visual_prompts",
        "cognisphere_provenance_refs",
    )
    for key in keys:
        value = knowledge.get(key)
        if isinstance(value, list):
            counts[key] = len(value)
    return counts


__all__ = [
    "get_bundled_pack",
    "import_bundled_pack",
    "list_bundled_packs",
    "merge_external_and_bundled_discovery",
]
