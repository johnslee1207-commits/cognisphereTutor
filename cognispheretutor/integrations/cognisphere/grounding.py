"""Local Cognisphere plugin knowledge grounding for Tutor mastery turns."""

from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
import re
from typing import Any

from cognispheretutor.integrations.cognisphere.plugin_importer import (
    resolve_import_cache_dir,
)
from cognispheretutor.integrations.cognisphere.registry_client import PluginRegistryClient

_TEXT_KEYS = (
    "id",
    "package_id",
    "unit_id",
    "skill_id",
    "concept_id",
    "topic_id",
    "topic_family_id",
    "objective_id",
    "class_id",
    "source_id",
    "name",
    "title",
    "label",
    "display_name",
    "summary",
    "description",
    "purpose",
    "body",
    "learner_contract",
    "teaching_purpose",
    "source_policy",
    "review_status",
)
_LIST_TEXT_KEYS = (
    "teaching_points",
    "target_learners",
    "learning_outcomes",
    "content_design_rationale",
    "learning_method",
    "recommended_sequence",
    "interface_principles",
    "assessment_pattern",
    "mastery_milestones",
    "claim_boundary_rules",
    "exit_evidence",
    "prerequisites",
    "related_concepts",
    "related_patterns",
    "recommended_problems",
    "certifications",
    "official_urls",
)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "aws",
    "certification",
    "cognisphere",
    "concept",
    "csphere",
    "learning",
    "of",
    "overview",
    "path",
    "the",
}


def build_plugin_grounding_seed(
    *,
    domain: str,
    objective: dict[str, Any] | None,
    learner_goal: str = "",
    max_items: int = 6,
) -> str:
    """Return a compact grounding block from local plugin pack/import knowledge."""
    domain = str(domain or "").strip()
    if not domain:
        return ""
    query = _objective_query(objective or {}, learner_goal=learner_goal)
    items = _rank_items(_load_domain_items(domain), query)[:max(1, max_items)]
    payload = {
        "status": "grounded" if items else "missing",
        "domain": domain,
        "query": query,
        "items": [_render_item(item) for item in items],
    }
    if not items:
        payload["message"] = (
            "No local plugin knowledge matched the current objective. The tutor "
            "should say the local graph/pack grounding is sparse instead of "
            "inventing factual teaching content."
        )
    return (
        "### Cognisphere Plugin Graph Grounding\n"
        "This block was loaded from local plugin/import knowledge before the LLM "
        "answered. Treat it as factual grounding for the current objective; use "
        "the LLM only for explanation style, scaffolding, and Socratic prompts.\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"
    )


def _load_domain_items(domain: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    client = PluginRegistryClient()
    try:
        record = client.get_plugin(domain)
    except Exception:
        record = {}
    plugin = record.get("plugin") if isinstance(record, dict) else {}
    plugin_path = Path(str((plugin or {}).get("path") or ""))
    if plugin_path.is_dir():
        items.extend(_load_plugin_domain_items(plugin_path))
        items.extend(_load_plugin_package_items(plugin_path))
    items.extend(_load_import_cache_items(domain))
    return items


def _load_plugin_domain_items(plugin_path: Path) -> list[dict[str, Any]]:
    domain_dir = plugin_path / "manifests" / "domain"
    if not domain_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for name in ("learning_surface.json", "pack_metadata.json", "composition_roles.json"):
        out.extend(_items_from_path(domain_dir / name, source="local plugin domain manifest"))
    return out


def _load_plugin_package_items(plugin_path: Path) -> list[dict[str, Any]]:
    packages_dir = plugin_path / "manifests" / "packages"
    if not packages_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for manifest_path in sorted(packages_dir.glob("*/package_manifest.json")):
        package_dir = manifest_path.parent
        manifest = _read_json(manifest_path)
        package_id = str(manifest.get("package_id") or package_dir.name)
        out.extend(
            _items_from_payload(
                manifest,
                source=f"local plugin package manifest:{package_id}",
                path=manifest_path,
            )
        )
        relpaths = _knowledge_relpaths(manifest)
        if not relpaths:
            relpaths = sorted((package_dir / "knowledge").glob("**/*"))
        for knowledge_path in relpaths:
            path = knowledge_path if knowledge_path.is_absolute() else package_dir / knowledge_path
            out.extend(_items_from_path(path, source=f"local plugin pack:{package_id}"))
    return out


def _load_import_cache_items(domain: str) -> list[dict[str, Any]]:
    try:
        cache_dir = resolve_import_cache_dir(domain=domain)
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for name in ("bundle.json", "import_receipt.json"):
        out.extend(_items_from_path(cache_dir / name, source="Cognisphere import cache"))
    return out


def _knowledge_relpaths(manifest: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for key, value in manifest.items():
        if not str(key).endswith("_relpath"):
            continue
        if isinstance(value, str) and value.strip():
            paths.append(Path(value.strip()))
    return paths


def _items_from_path(path: Path, *, source: str) -> list[dict[str, Any]]:
    if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".txt"}:
        return []
    if path.suffix.lower() == ".json":
        return _items_from_payload(_read_json(path), source=source, path=path)
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return []
    return [
        {
            "id": path.stem,
            "title": path.stem.replace("_", " ").replace("-", " ").strip(),
            "body": text[:2000],
            "_source": source,
            "_path": str(path),
        }
    ]


def _items_from_payload(payload: Any, *, source: str, path: Path) -> list[dict[str, Any]]:
    raw_items = list(_iter_candidate_objects(payload))
    out: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        text = _item_text(item)
        if not text:
            continue
        normalized = {key: item.get(key) for key in _TEXT_KEYS if key in item}
        for key in _LIST_TEXT_KEYS:
            if key in item:
                normalized[key] = item.get(key)
        normalized["_source"] = source
        normalized["_path"] = str(path)
        normalized["_text"] = text
        out.append(normalized)
    return out


def _iter_candidate_objects(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, dict):
        yielded = False
        for key in (
            "units",
            "concepts",
            "skills",
            "objectives",
            "learning_objectives",
            "topic_families",
            "patterns",
            "problems",
            "items",
            "classes",
            "nodes",
            "entries",
            "excerpts",
            "course_overview",
            "course_guide",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                yielded = True
                for item in value:
                    if isinstance(item, dict):
                        yield item
            elif isinstance(value, dict):
                yielded = True
                if key in {"course_overview", "course_guide"}:
                    yield value
                else:
                    for item in value.values():
                        if isinstance(item, dict):
                            yield item
        if not yielded:
            yield payload
            for value in payload.values():
                if isinstance(value, (dict, list)):
                    yield from _iter_candidate_objects(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_candidate_objects(item)


def _rank_items(items: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    query_tokens = _tokens(query)
    if not query_tokens:
        return items
    ranked: list[tuple[int, dict[str, Any]]] = []
    for item in items:
        item_tokens = _tokens(str(item.get("_text") or _item_text(item)))
        overlap = len(query_tokens & item_tokens)
        exact_bonus = 2 if query.lower() in str(item.get("_text") or "").lower() else 0
        score = overlap + exact_bonus
        if score:
            ranked.append((score, item))
    ranked.sort(key=lambda row: (-row[0], str(row[1].get("title") or row[1].get("id") or "")))
    return [item for _, item in ranked] or items


def _render_item(item: dict[str, Any]) -> dict[str, Any]:
    body = str(
        item.get("body")
        or item.get("teaching_purpose")
        or item.get("learner_contract")
        or item.get("description")
        or item.get("summary")
        or ""
    ).strip()
    rendered = {
        "id": item.get("unit_id")
        or item.get("package_id")
        or item.get("skill_id")
        or item.get("concept_id")
        or item.get("topic_id")
        or item.get("id"),
        "title": item.get("title")
        or item.get("name")
        or item.get("label")
        or item.get("package_id"),
        "source": item.get("_source"),
        "path": item.get("_path"),
    }
    if body:
        rendered["body"] = body[:1200]
    teaching_points = item.get("teaching_points") or item.get("learning_outcomes")
    if isinstance(teaching_points, list) and teaching_points:
        rendered["teaching_points"] = [str(point) for point in teaching_points[:6]]
    for key in (
        "target_learners",
        "content_design_rationale",
        "learning_method",
        "recommended_sequence",
        "interface_principles",
        "assessment_pattern",
        "mastery_milestones",
        "claim_boundary_rules",
        "exit_evidence",
        "prerequisites",
        "related_concepts",
        "related_patterns",
        "certifications",
    ):
        value = item.get(key)
        if isinstance(value, list) and value:
            rendered[key] = [_list_item_text(v) for v in value[:8]]
    for key in ("source_policy", "review_status"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            rendered[key] = value.strip()[:1200]
    return {k: v for k, v in rendered.items() if v not in (None, "", [])}


def _objective_query(objective: dict[str, Any], *, learner_goal: str = "") -> str:
    parts = [
        learner_goal,
        objective.get("knowledge_point_id"),
        objective.get("knowledge_point_name"),
        objective.get("knowledge_point_type"),
        objective.get("module_id"),
        objective.get("module_name"),
    ]
    return " ".join(str(part) for part in parts if part).strip()


def _list_item_text(value: Any) -> str:
    if not isinstance(value, dict):
        return str(value)
    label = (
        value.get("label")
        or value.get("title")
        or value.get("name")
        or value.get("milestone_id")
        or value.get("phase_id")
        or value.get("id")
    )
    details = []
    for key in ("purpose", "learner_can", "exit_evidence", "review_evidence"):
        nested = value.get(key)
        if isinstance(nested, list):
            details.extend(str(item) for item in nested[:3] if item not in (None, ""))
        elif isinstance(nested, str) and nested.strip():
            details.append(nested.strip())
    parts = [str(label)] if label else []
    parts.extend(details)
    return " — ".join(parts) if parts else str(value)


def _item_text(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in _TEXT_KEYS:
        value = item.get(key)
        if value not in (None, "", [], {}):
            parts.append(str(value))
    for key in _LIST_TEXT_KEYS:
        value = item.get(key)
        if isinstance(value, list):
            parts.extend(str(v) for v in value if v not in (None, ""))
    return " ".join(parts).strip()


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]{2,}", text.lower())
        if token not in _STOPWORDS
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


__all__ = ["build_plugin_grounding_seed"]
