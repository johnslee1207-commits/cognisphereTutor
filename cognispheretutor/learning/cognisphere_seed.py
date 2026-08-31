"""Seed Guided Learning (mastery_path) modules from Cognisphere import knowledge."""

from __future__ import annotations

import re
from typing import Any

from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError
from cognispheretutor.learning.models import KnowledgePoint, KnowledgeType, LearningModule

_PATH_PREFIX = "csphere-"


def mastery_path_id_for_domain(domain: str) -> str:
    """Stable LearningStore book_id for a Cognisphere domain pack."""
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(domain or "").strip()).strip("-").lower()
    if not safe:
        safe = "unknown"
    return f"{_PATH_PREFIX}{safe}"


def is_cognisphere_path_id(book_id: str) -> bool:
    return str(book_id or "").startswith(_PATH_PREFIX)


def domain_from_path_id(book_id: str) -> str | None:
    """Extract domain from ``csphere-{domain}`` path ids; else ``None``."""
    text = str(book_id or "")
    if not text.startswith(_PATH_PREFIX):
        return None
    domain = text[len(_PATH_PREFIX) :].strip()
    return domain or None


def _item_id(prefix: str, raw: Any, index: int) -> str:
    if isinstance(raw, dict):
        for key in (
            "id",
            "skill_id",
            "pattern_id",
            "slug",
            "concept_id",
            "assessment_id",
            "theorem_id",
            "topic_id",
            "objective_id",
            "unit_id",
            "class_id",
            "service_id",
            "track_id",
            "topic_family_id",
            "excerpt_id",
            "document_id",
        ):
            value = raw.get(key)
            if value:
                text = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value)).strip("-")
                if text:
                    return f"{prefix}-{text}"[:120]
    return f"{prefix}-{index}"


def _item_name(raw: Any, fallback: str) -> str:
    if isinstance(raw, dict):
        for key in (
            "name",
            "title",
            "display_name",
            "label",
            "slug",
            "title_en",
            "pattern_hint",
            "summary",
            "description",
            "purpose",
        ):
            value = raw.get(key)
            if value:
                return str(value).strip()[:200]
    if isinstance(raw, str) and raw.strip():
        return raw.strip()[:200]
    return fallback


def _as_list(knowledge: dict[str, Any], *keys: str) -> list[Any]:
    for key in keys:
        value = knowledge.get(key)
        if isinstance(value, list) and value:
            return _learning_order(value)
        if isinstance(value, dict) and value:
            # catalog-style: {"items": [...]} or id→obj map
            if isinstance(value.get("items"), list):
                return _learning_order(list(value["items"]))
            return _learning_order(list(value.values()))
    return []


def _nested_list(knowledge: dict[str, Any], key: str, child_key: str) -> list[Any]:
    value = knowledge.get(key)
    if isinstance(value, dict) and isinstance(value.get(child_key), list):
        return _learning_order(list(value[child_key]))
    return []


def _learning_order(items: list[Any]) -> list[Any]:
    """Respect declarative learning levels when a domain pack provides them."""
    level_rank = {
        "intro": 0,
        "introduction": 0,
        "foundational": 0,
        "foundation": 0,
        "fundamentals": 0,
        "beginner": 0,
        "basic": 1,
        "core": 1,
        "intermediate": 2,
        "associate": 3,
        "advanced": 4,
        "professional": 5,
        "expert": 6,
        "specialty": 6,
    }

    def _rank(row: tuple[int, Any]) -> tuple[int, int]:
        index, item = row
        if not isinstance(item, dict):
            return 99, index
        level = str(item.get("level") or item.get("difficulty") or "").strip().lower()
        return level_rank.get(level, 50), index

    return [item for _, item in sorted(enumerate(items), key=_rank)]


def modules_from_knowledge(
    knowledge: dict[str, Any] | None,
    *,
    domain: str,
    path_id: str | None = None,
) -> list[LearningModule]:
    """Map Cognisphere bundle.knowledge → LearningModule list for Mastery Path."""
    data = knowledge if isinstance(knowledge, dict) else {}
    bid = path_id or mastery_path_id_for_domain(domain)
    ready_modules = _modules_from_ready_payload(data.get("mastery_modules"), bid=bid)
    if ready_modules:
        return ready_modules
    modules: list[LearningModule] = []
    order = 0

    def _add_module(
        module_key: str,
        title: str,
        items: list[Any],
        kp_type: KnowledgeType,
        *,
        id_prefix: str,
    ) -> None:
        nonlocal order
        if not items:
            return
        module_id = f"{bid}-{module_key}"
        kps: list[KnowledgePoint] = []
        for i, item in enumerate(items):
            kps.append(
                KnowledgePoint(
                    id=_item_id(id_prefix, item, i),
                    name=_item_name(item, f"{title} {i + 1}"),
                    type=kp_type,
                    module_id=module_id,
                )
            )
        modules.append(
            LearningModule(
                id=module_id,
                name=title,
                order=order,
                pass_threshold=0.7,
                knowledge_points=kps,
            )
        )
        order += 1

    # Display name for the Learning Space sidebar comes from the first module.
    patterns = _as_list(data, "patterns", "problem_patterns")
    skills = _as_list(data, "skills", "procedures", "certification_tracks")
    problems = _as_list(data, "problems", "practice_problems", "assessments")
    concepts = (
        _as_list(data, "concepts", "catalog", "ontology_classes")
        + _nested_list(data, "learning_fixture", "excerpts")
    )
    objectives = _as_list(
        data,
        "objectives",
        "learning_objectives",
        "topics",
        "topic_families",
    )
    references = (
        _as_list(data, "theorems", "rules", "principles")
        + _nested_list(data, "original_knowledge", "units")
    )
    learning_loop = _as_list(data, "learning_loop", "sample_learning_path")
    surface = data.get("learning_surface") if isinstance(data.get("learning_surface"), dict) else {}
    course_overview = data.get("course_overview") or surface.get("course_overview")
    if not isinstance(course_overview, dict):
        course_overview = {}
    overview_name = _item_name(course_overview, f"Cognisphere · {domain}")
    overview_id = course_overview.get("overview_id") or course_overview.get("id") or "overview"

    overview_items: list[dict[str, Any]] = [
        {
            "id": overview_id,
            "name": overview_name,
        }
    ]
    _add_module("overview", overview_name, overview_items, KnowledgeType.CONCEPT, id_prefix="ov")

    _add_module("patterns", "Patterns", patterns, KnowledgeType.CONCEPT, id_prefix="pat")
    _add_module("skills", "Skills", skills, KnowledgeType.PROCEDURE, id_prefix="sk")
    _add_module("objectives", "Learning objectives", objectives, KnowledgeType.CONCEPT, id_prefix="obj")
    _add_module("concepts", "Concepts", concepts, KnowledgeType.CONCEPT, id_prefix="con")
    _add_module("references", "Reference rules", references, KnowledgeType.CONCEPT, id_prefix="ref")
    _add_module("problems", "Practice problems", problems, KnowledgeType.PROCEDURE, id_prefix="prob")
    _add_module("learning-loop", "Learning loop", learning_loop, KnowledgeType.PROCEDURE, id_prefix="loop")

    # If the pack was empty, keep a single overview module so the path is visible.
    if len(modules) == 1:
        return modules
    return modules


def _modules_from_ready_payload(raw: Any, *, bid: str) -> list[LearningModule]:
    """Parse Tutor-ready module data from a distributed pack.

    Domain packs may ship precomputed Mastery Path modules when their runnable
    learning surface is richer than the generic knowledge-key mapping. This is
    still data-driven: Tutor validates and normalizes the module envelope, but
    the domain decides the objective list.
    """
    if not isinstance(raw, list) or not raw:
        return []
    modules: list[LearningModule] = []
    replace_from = ""
    for item in raw:
        if isinstance(item, dict) and str(item.get("id") or "").startswith(_PATH_PREFIX):
            parts = str(item["id"]).split("-", 2)
            if len(parts) >= 2:
                replace_from = "-".join(parts[:2])
            break
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        payload = dict(item)
        if replace_from and bid != replace_from:
            module_id = str(payload.get("id") or "")
            if module_id.startswith(replace_from):
                payload["id"] = bid + module_id[len(replace_from) :]
            points = []
            for kp in list(payload.get("knowledge_points") or []):
                if not isinstance(kp, dict):
                    continue
                point = dict(kp)
                point_module = str(point.get("module_id") or "")
                if point_module.startswith(replace_from):
                    point["module_id"] = bid + point_module[len(replace_from) :]
                points.append(point)
            payload["knowledge_points"] = points
        payload.setdefault("order", index)
        try:
            module = LearningModule(**payload)
        except Exception:
            continue
        if module.knowledge_points:
            modules.append(module)
    modules.sort(key=lambda module: module.order)
    return modules


def seed_payload_from_import_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Extract domain + knowledge dict from an export_and_import receipt."""
    domain = str(
        receipt.get("domain") or (receipt.get("receipt") or {}).get("domain") or ""
    ).strip()
    if not domain:
        raise CognisphereIntegrationError(
            "domain_required",
            message="import receipt missing domain; cognisphereTutor has no default domain",
        )
    knowledge: dict[str, Any] = {}
    # Prefer full bundle knowledge when present on the receipt envelope.
    for key in ("knowledge", "bundle_knowledge"):
        if isinstance(receipt.get(key), dict):
            knowledge = dict(receipt[key])
            break
    if not knowledge:
        # Surfaces hold sliced views; merge assessment/plan/mastery knowledge blobs.
        for surface in ("assessment", "plan", "mastery"):
            block = (receipt.get("surfaces") or {}).get(surface) or {}
            kn = block.get("knowledge") if isinstance(block, dict) else None
            if isinstance(kn, dict):
                for k, v in kn.items():
                    if k not in knowledge:
                        knowledge[k] = v
    summary = receipt.get("knowledge_summary") if isinstance(receipt.get("knowledge_summary"), dict) else {}
    if not knowledge and isinstance(summary.get("surfaces"), dict):
        for kn in (summary.get("surfaces") or {}).values():
            if isinstance(kn, dict):
                for k, v in kn.items():
                    if k not in knowledge:
                        knowledge[k] = v
    return {"domain": domain, "knowledge": knowledge, "summary": summary}
