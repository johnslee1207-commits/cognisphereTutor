"""DT-P2 — export bundle import into cognisphereTutor learning-loop surfaces."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cognispheretutor.integrations.cognisphere._contract import (
    load_learning_loop_mapping,
    load_plugin_contract,
)
from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError, format_issue
from cognispheretutor.integrations.cognisphere.registry_client import PluginRegistryClient


ALLOWED_TRUE_SAFETY = ("no_answer_keys", "no_full_solution_dump")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def validate_bundle_safety(bundle: dict[str, Any]) -> dict[str, Any]:
    """Reject unsafe / incomplete handoff bundles (asks-not-spoils)."""
    contract = load_plugin_contract()
    handoff = contract["handoff"]
    issues: list[str] = []

    # Accept legacy ``generated_at`` as exported_at for presence checks.
    normalized = dict(bundle)
    if "exported_at" not in normalized and normalized.get("generated_at"):
        normalized["exported_at"] = normalized["generated_at"]

    for key in list(handoff["required_top_level_keys"]):
        if key not in normalized:
            issues.append(format_issue("missing_top_level", key))

    safety = normalized.get("safety") if isinstance(normalized.get("safety"), dict) else {}
    for key in list(handoff["required_safety_keys"]):
        if key not in safety:
            issues.append(format_issue("missing_safety", key))

    for key in ALLOWED_TRUE_SAFETY:
        if key in safety and safety.get(key) is not True:
            issues.append(format_issue("missing_safety", key))

    sot = safety.get("source_of_truth")
    if sot is not None and sot not in set(contract["allowed_source_of_truth"]):
        issues.append("unexpected_source_of_truth")

    if safety.get("verified_code_solutions_included") is True:
        issues.append("forbidden_verified_code_solutions_included")
    if safety.get("full_official_problem_statements_included") is True:
        issues.append("forbidden_full_official_statements_included")
    if "tutor_asks_not_spoils" in safety and safety.get("tutor_asks_not_spoils") is not True:
        issues.append("tutor_must_ask_not_spoil")

    return {
        "ok": not issues,
        "issues": issues,
        "contract": handoff,
        "plugin_id": normalized.get("plugin_id"),
        "domain": normalized.get("domain"),
        "normalized_bundle": normalized,
    }


def map_learning_loop(learning_loop: Any) -> dict[str, Any]:
    """Map Cognisphere ``learning_loop`` stages → cognisphereTutor pipeline stages."""
    mapping = load_learning_loop_mapping()
    stage_map: dict[str, Any] = dict(mapping.get("stage_map") or {})
    aliases: dict[str, str] = {
        str(k).strip().lower(): str(v)
        for k, v in dict(mapping.get("alias_stage_map") or {}).items()
    }
    default_loop = list(mapping.get("default_learning_loop") or [])

    raw_stages = list(learning_loop) if isinstance(learning_loop, list) else []
    if not raw_stages:
        raw_stages = list(default_loop)

    stages: list[dict[str, Any]] = []
    unmapped: list[str] = []
    for raw in raw_stages:
        label = str(raw).strip()
        canonical = stage_map.get(label)
        if canonical is None:
            alias_target = aliases.get(label.lower())
            if alias_target and alias_target in stage_map:
                label = alias_target
                canonical = stage_map[label]
            else:
                unmapped.append(str(raw))
                continue
        stages.append(
            {
                "source": str(raw),
                "canonical": label,
                "pipeline_id": canonical.get("pipeline_id"),
                "surface": canonical.get("surface"),
                "mastery_stage": canonical.get("mastery_stage"),
                "description": canonical.get("description"),
            }
        )

    by_surface: dict[str, list[str]] = {"assessment": [], "plan": [], "mastery": []}
    for item in stages:
        surface = str(item.get("surface") or "")
        if surface in by_surface:
            by_surface[surface].append(str(item.get("pipeline_id")))

    return {
        "ok": not unmapped,
        "source_loop": [str(s) for s in raw_stages],
        "stages": stages,
        "unmapped": unmapped,
        "surfaces": by_surface,
        "contract_id": mapping.get("contract_id"),
    }


def _count_knowledge_list(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        for key in ("items", "classes", "nodes", "entries"):
            inner = value.get(key)
            if isinstance(inner, list):
                return len(inner)
        return len(value) if value else 0
    return 0 if value in (None, "", {}, []) else 1


def _resolve_expected_knowledge_keys(
    bundle: dict[str, Any],
    knowledge: dict[str, Any],
    mapping: dict[str, Any],
) -> list[str]:
    """Prefer plugin-declared keys; never fall back to a domain-shaped default list.

    Order:
    1. ``bundle.expected_knowledge_keys`` (plugin handoff)
    2. ``bundle.knowledge.expected_keys`` / ``meta.expected_knowledge_keys``
    3. mapping ``default_expected_knowledge_keys`` when non-empty
    4. Generic: union of ``surface_knowledge_keys`` values that appear in knowledge,
       else all top-level knowledge keys (report-only, no domain bias)
    """
    for candidate in (
        bundle.get("expected_knowledge_keys"),
        (knowledge.get("expected_keys") if isinstance(knowledge.get("expected_keys"), list) else None),
        ((bundle.get("meta") or {}).get("expected_knowledge_keys") if isinstance(bundle.get("meta"), dict) else None),
    ):
        if isinstance(candidate, list) and candidate:
            return [str(k) for k in candidate if str(k).strip()]

    defaults = list(mapping.get("default_expected_knowledge_keys") or [])
    if defaults:
        return [str(k) for k in defaults if str(k).strip()]

    surfaces = dict(mapping.get("surface_knowledge_keys") or {})
    surface_union: list[str] = []
    seen: set[str] = set()
    for keys in surfaces.values():
        for key in list(keys or []):
            text = str(key)
            if text in knowledge and text not in seen:
                seen.add(text)
                surface_union.append(text)
    if surface_union:
        return surface_union
    return sorted(str(k) for k in knowledge.keys())


def summarize_knowledge(bundle: dict[str, Any]) -> dict[str, Any]:
    """Summarize knowledge payload; expected keys are plugin-declared or generic."""
    mapping = load_learning_loop_mapping()
    knowledge = bundle.get("knowledge") if isinstance(bundle.get("knowledge"), dict) else {}
    domain = str(bundle.get("domain") or "")
    expected = _resolve_expected_knowledge_keys(bundle, knowledge, mapping)
    counts: dict[str, int] = {}
    empty_reasons: list[str] = []
    for key in sorted(set(list(knowledge.keys()) + expected)):
        counts[key] = _count_knowledge_list(knowledge.get(key))
        if key in expected and counts[key] == 0:
            if key not in knowledge:
                empty_reasons.append(f"knowledge.{key}_missing")
            else:
                empty_reasons.append(f"knowledge.{key}_empty")

    surfaces = dict(mapping.get("surface_knowledge_keys") or {})
    surface_payloads: dict[str, dict[str, Any]] = {}
    for surface, keys in surfaces.items():
        payload: dict[str, Any] = {}
        for key in list(keys or []):
            if key == "learning_loop" and key not in knowledge:
                payload[key] = list(bundle.get("learning_loop") or [])
            elif key in knowledge:
                payload[key] = knowledge.get(key)
        surface_payloads[surface] = payload

    # Domain-agnostic extras: any top-level *_graph plus common optional blobs.
    graph_flags = {
        key: bool(bundle.get(key))
        for key in bundle.keys()
        if str(key).endswith("_graph")
    }
    return {
        "domain": domain,
        "counts": counts,
        "expected_keys": expected,
        "empty_reasons": empty_reasons,
        "nonempty": any(counts.get(k, 0) > 0 for k in expected) or any(
            v > 0 for k, v in counts.items() if k not in expected
        ),
        "surfaces": surface_payloads,
        "extra_top_level": {
            **graph_flags,
            "tutor_scripts": _count_knowledge_list(bundle.get("tutor_scripts")),
            "forbidden_in_export": list(bundle.get("forbidden_in_export") or []),
        },
    }


def resolve_import_cache_dir(
    *,
    domain: str | None = None,
    cache_dir: str | Path | None = None,
) -> Path:
    mapping = load_learning_loop_mapping()
    cache_cfg = dict(mapping.get("import_cache") or {})
    env_name = str(cache_cfg.get("env_override") or load_plugin_contract().get("import_cache_env") or "")
    if cache_dir is not None:
        base = Path(cache_dir)
    else:
        env_val = (os.getenv(env_name) or "").strip() if env_name else ""
        if env_val:
            base = Path(env_val)
        else:
            try:
                from cognispheretutor.services.path_service import get_path_service

                rel = str(cache_cfg.get("relative_workspace_path") or "cognisphere_imports")
                base = get_path_service().get_workspace_dir() / rel
            except Exception:  # noqa: BLE001 — tests may lack full runtime
                base = Path.cwd() / "data" / "user" / "workspace" / "cognisphere_imports"
    if domain:
        return (base / domain).resolve()
    return base.resolve()


def _persist_import(
    bundle: dict[str, Any],
    receipt: dict[str, Any],
    *,
    cache_dir: str | Path | None = None,
) -> Path:
    mapping = load_learning_loop_mapping()
    cache_cfg = dict(mapping.get("import_cache") or {})
    domain = str(bundle.get("domain") or "unknown")
    target = resolve_import_cache_dir(domain=domain, cache_dir=cache_dir)
    target.mkdir(parents=True, exist_ok=True)
    bundle_name = str(cache_cfg.get("bundle_filename") or "bundle.json")
    receipt_name = str(cache_cfg.get("receipt_filename") or "import_receipt.json")
    (target / bundle_name).write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (target / receipt_name).write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def import_bundle_json(
    bundle: dict[str, Any],
    *,
    persist: bool = True,
    cache_dir: str | Path | None = None,
    export_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate safety, map learning loop, optionally cache, return ImportReceipt."""
    report = validate_bundle_safety(bundle)
    if not report["ok"]:
        raise CognisphereIntegrationError(
            report["issues"][0] if report["issues"] else "missing_top_level",
            details={"issues": report["issues"]},
        )

    normalized = report["normalized_bundle"]
    pipeline = map_learning_loop(normalized.get("learning_loop"))
    knowledge = summarize_knowledge(normalized)
    imported_at = _utc_now()

    assessment = {
        "pipeline_ids": list((pipeline.get("surfaces") or {}).get("assessment") or []),
        "knowledge": (knowledge.get("surfaces") or {}).get("assessment") or {},
        "counts": {
            k: knowledge["counts"].get(k, 0)
            for k in load_learning_loop_mapping()
            .get("surface_knowledge_keys", {})
            .get("assessment", [])
            if k in knowledge["counts"]
        },
    }
    plan = {
        "pipeline_ids": list((pipeline.get("surfaces") or {}).get("plan") or []),
        "knowledge": (knowledge.get("surfaces") or {}).get("plan") or {},
        "learning_loop": pipeline.get("source_loop") or [],
    }
    mastery = {
        "pipeline_ids": list((pipeline.get("surfaces") or {}).get("mastery") or []),
        "knowledge": (knowledge.get("surfaces") or {}).get("mastery") or {},
    }

    receipt_body: dict[str, Any] = {
        "bundle_id": normalized.get("bundle_id"),
        "domain": normalized.get("domain"),
        "plugin_id": normalized.get("plugin_id"),
        "exported_at": normalized.get("exported_at"),
        "imported_at": imported_at,
        "assessment": assessment,
        "plan": plan,
        "mastery": mastery,
        "knowledge_summary": {
            "counts": knowledge.get("counts"),
            "empty_reasons": knowledge.get("empty_reasons"),
            "nonempty": knowledge.get("nonempty"),
        },
        "pipeline": {
            "stages": pipeline.get("stages"),
            "unmapped": pipeline.get("unmapped"),
        },
        "forbidden_in_export": list(normalized.get("forbidden_in_export") or []),
    }

    artifact_path: str | None = None
    if persist:
        path = _persist_import(normalized, receipt_body, cache_dir=cache_dir)
        artifact_path = str(path)
        receipt_body["artifact_path"] = artifact_path

    result: dict[str, Any] = {
        "ok": True,
        "status": "imported",
        "phase": "DT-P2",
        "validation": report,
        "pipeline": pipeline,
        "knowledge_summary": knowledge,
        "receipt": receipt_body,
        "surfaces": {
            "assessment": assessment,
            "plan": plan,
            "mastery": mastery,
        },
    }
    if export_meta is not None:
        result["export"] = export_meta
    if artifact_path:
        result["artifact_path"] = artifact_path
    return result


def export_and_import(
    domain: str,
    options: dict[str, Any] | None = None,
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Call plugin ``export_deeptutor_package`` then import the bundle."""
    opts = dict(options or {})
    registry = client or PluginRegistryClient(root)
    record = registry.get_plugin(domain, root)
    mod = registry.load_deeptutor_entrypoint(domain, root=record.get("plugins_root"))
    export_fn = getattr(mod, "export_deeptutor_package", None)
    if not callable(export_fn):
        raise CognisphereIntegrationError(
            format_issue("missing_deeptutor_func", "export_deeptutor_package"),
            details={"domain": domain},
        )

    export_kwargs = dict(opts.get("export_kwargs") or {})
    try:
        exported = export_fn(**export_kwargs) if export_kwargs else export_fn()
    except TypeError:
        exported = export_fn()
    except Exception as exc:  # noqa: BLE001
        raise CognisphereIntegrationError(
            "export_failed",
            message=str(exc),
            details={"domain": domain},
        ) from exc

    if not isinstance(exported, dict):
        raise CognisphereIntegrationError(
            "export_envelope_invalid",
            details={"domain": domain, "type": type(exported).__name__},
        )
    if exported.get("ok") is False:
        raise CognisphereIntegrationError(
            "export_failed",
            details={
                "domain": domain,
                "error": exported.get("error"),
                "note": exported.get("note"),
                "validation": exported.get("validation"),
            },
        )

    bundle = exported.get("bundle")
    if not isinstance(bundle, dict):
        raise CognisphereIntegrationError(
            "export_envelope_invalid",
            details={"domain": domain, "keys": sorted(exported.keys())},
        )

    # Prefer plugin-normalized safety; do not invent non-Cognisphere source_of_truth.
    persist = bool(opts.get("persist", True))
    cache_dir = opts.get("cache_dir")
    receipt = import_bundle_json(
        bundle,
        persist=persist,
        cache_dir=cache_dir,
        export_meta={
            "ok": exported.get("ok", True),
            "domain": domain,
            "validation": exported.get("validation"),
            "note": exported.get("note"),
            "host_bridge_error": exported.get("host_bridge_error"),
            "plugins_root": record.get("plugins_root"),
        },
    )
    receipt["domain"] = domain
    receipt["plugins_root"] = record.get("plugins_root")
    return receipt
