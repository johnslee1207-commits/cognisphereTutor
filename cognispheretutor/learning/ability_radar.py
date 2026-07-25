"""Ability radar aggregation from Mastery Path / Cognisphere KP data.

Domain-agnostic: axes come from seeded modules and optional skill_graph
hints; Tutor never hardcodes domain labels.
"""

from __future__ import annotations

from typing import Any

from cognispheretutor.learning.cognisphere_seed import (
    domain_from_path_id,
    is_cognisphere_path_id,
)
from cognispheretutor.learning.policy import map_summary
from cognispheretutor.learning.service import LearningService
from cognispheretutor.learning.storage import LearningStore

# Weak-area budget (User Manual §6 style): lowest-mastery open objectives.
_DEFAULT_WEAK_LIMIT = 8
_WEAK_MASTERED_STATUSES = frozenset({"mastered"})


def _weak_areas_from_map(map_payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
    weak: list[dict[str, Any]] = []
    for module in map_payload.get("modules") or []:
        for kp in module.get("knowledge_points") or []:
            status = str(kp.get("status") or "")
            if status in _WEAK_MASTERED_STATUSES:
                continue
            weak.append(
                {
                    "module_id": module.get("id"),
                    "module_name": module.get("name"),
                    "kp_id": kp.get("id"),
                    "kp_name": kp.get("name"),
                    "type": kp.get("type"),
                    "status": status,
                    "mastery": float(kp.get("mastery") or 0.0),
                    "mastery_pct": round(float(kp.get("mastery") or 0.0) * 100),
                }
            )
    weak.sort(key=lambda row: (row["mastery"], row.get("kp_name") or ""))
    return weak[: max(0, limit)]


def _axes_from_map(map_payload: dict[str, Any]) -> list[dict[str, Any]]:
    axes: list[dict[str, Any]] = []
    for module in map_payload.get("modules") or []:
        total = int(module.get("total") or 0)
        mastered = int(module.get("mastered") or 0)
        pct = round(mastered / total * 100) if total else 0
        axes.append(
            {
                "id": module.get("id"),
                "label": module.get("name") or module.get("id"),
                "mastered": mastered,
                "total": total,
                "pct": pct,
            }
        )
    return axes


def build_path_radar(
    service: LearningService,
    book_id: str,
    *,
    weak_limit: int = _DEFAULT_WEAK_LIMIT,
    include_skill_graph: bool = True,
) -> dict[str, Any] | None:
    """Build one path's radar snapshot; ``None`` when the path has no KPs."""
    progress = service.load(book_id)
    if progress is None:
        return None
    summary_map = map_summary(progress)
    counts = summary_map.get("counts") or {}
    total = int(counts.get("total") or 0)
    if total <= 0:
        return None
    mastered = int(counts.get("mastered") or 0)
    mastered_pct = round(mastered / total * 100) if total else 0
    current_kp_ids = {kp.id for m in progress.modules for kp in m.knowledge_points}
    avg_mastery = (
        sum(progress.mastery_levels.get(kp_id, 0.0) for kp_id in current_kp_ids) / total
        if total
        else 0.0
    )
    domain = domain_from_path_id(book_id)
    skill_graph: dict[str, Any] | None = None
    if include_skill_graph and domain:
        try:
            from cognispheretutor.integrations.cognisphere import plan_skill_path

            planned = plan_skill_path(domain=domain, learner_id="offline-learner")
            if isinstance(planned, dict) and planned.get("ok") is not False:
                skill_graph = {
                    "source": planned.get("source") or "plugin_skill_graph",
                    "path_preview": planned.get("path")
                    or planned.get("plan")
                    or planned.get("nodes")
                    or planned.get("skills"),
                    "raw_keys": sorted(k for k in planned.keys() if k != "ok")[:12],
                }
        except Exception:  # noqa: BLE001 — radar stays available without skill_graph
            skill_graph = None

    return {
        "path_id": book_id,
        "name": (progress.modules[0].name if progress.modules else "") or book_id,
        "domain": domain,
        "is_cognisphere": is_cognisphere_path_id(book_id),
        "mastered_pct": mastered_pct,
        "avg_mastery_pct": round(avg_mastery * 100),
        "counts": counts,
        "due_reviews": summary_map.get("due_reviews", 0),
        "complete": bool(summary_map.get("complete")),
        "axes": _axes_from_map(summary_map),
        "weak_areas": _weak_areas_from_map(summary_map, limit=weak_limit),
        "skill_graph": skill_graph,
    }


def build_ability_radar(
    service: LearningService | None = None,
    *,
    path_id: str | None = None,
    weak_limit: int = _DEFAULT_WEAK_LIMIT,
    include_skill_graph: bool = True,
) -> dict[str, Any]:
    """Aggregate domain-level ability radar across Mastery Paths.

    When ``path_id`` is set, returns that path detail plus the domain list.
    """
    svc = service or LearningService(LearningStore())
    listed = svc.list_progress()
    summaries = list(listed.get("summaries") or [])
    domains: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None

    for row in summaries:
        book_id = str(row.get("book_id") or "")
        if not book_id or int(row.get("kp_count") or 0) <= 0:
            continue
        radar = build_path_radar(
            svc,
            book_id,
            weak_limit=weak_limit,
            include_skill_graph=include_skill_graph
            and (path_id is None or path_id == book_id),
        )
        if not radar:
            continue
        domains.append(
            {
                "path_id": radar["path_id"],
                "name": radar["name"],
                "domain": radar["domain"],
                "is_cognisphere": radar["is_cognisphere"],
                "mastered_pct": radar["mastered_pct"],
                "avg_mastery_pct": radar["avg_mastery_pct"],
                "kp_count": int((radar.get("counts") or {}).get("total") or 0),
                "weak_count": len(radar.get("weak_areas") or []),
                "axes": radar["axes"],
            }
        )
        if path_id and book_id == path_id:
            selected = radar

    domains.sort(key=lambda d: (-int(d.get("weak_count") or 0), d.get("name") or ""))

    if path_id and selected is None:
        selected = build_path_radar(
            svc,
            path_id,
            weak_limit=weak_limit,
            include_skill_graph=include_skill_graph,
        )

    weak_domains = sorted(
        [d for d in domains if int(d.get("mastered_pct") or 0) < 100],
        key=lambda d: (
            int(d.get("mastered_pct") or 0),
            -(int(d.get("weak_count") or 0)),
        ),
    )[:weak_limit]

    return {
        "ok": True,
        "contract": "deeptutor.learning.ability_radar.v1",
        "domain_count": len(domains),
        "domains": domains,
        "weak_domains": weak_domains,
        "selected": selected,
        "path_id": path_id,
    }


__all__ = ["build_ability_radar", "build_path_radar"]
