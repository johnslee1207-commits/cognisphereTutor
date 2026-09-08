"""Minimal course manifest compiler for the OpenMAIC runtime boundary."""

from __future__ import annotations

from datetime import UTC, date, datetime
import hashlib
from typing import Any, Mapping


def compile_minimal_course_manifest(
    *,
    topic: str,
    locale: str,
    audience_profile: str,
    constraints: Mapping[str, Any] | None = None,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Create a small but runnable DeepTutor course manifest."""
    clean_topic = " ".join(topic.split()).strip()
    if not clean_topic:
        raise ValueError("topic must be non-empty")
    course_id = _slug(clean_topic)
    source_pack_version = date.today().isoformat()
    source_ids = source_refs or [f"source:{course_id}:seed"]
    objective_id = f"obj-{course_id}-apply"
    assessment_id = f"assess-{course_id}-checkpoint"
    lab_id = f"lab-{course_id}-evidence"

    scenes = _scenes(
        course_id=course_id,
        topic=clean_topic,
        objective_id=objective_id,
        source_refs=source_ids,
        lab_id=lab_id,
    )
    return {
        "course_id": course_id,
        "version": "1.0.0",
        "title": clean_topic,
        "description": f"A short evidence-driven course about {clean_topic}.",
        "locale": locale,
        "audience_profile": audience_profile,
        "source_pack_version": source_pack_version,
        "competency_graph_version": "mvp-1",
        "risk_level": str((constraints or {}).get("risk_level") or "general_learning"),
        "approval_status": str((constraints or {}).get("approval_status") or "draft"),
        "learning_objectives": [
            {
                "objective_id": objective_id,
                "statement": f"Explain and apply {clean_topic} using source-backed evidence.",
                "domain": str((constraints or {}).get("domain") or "general"),
                "level": str((constraints or {}).get("level") or "foundation"),
                "prerequisites": [],
                "source_refs": source_ids,
                "assessment_refs": [assessment_id],
                "lab_refs": [lab_id],
                "mastery_threshold": 0.8,
                "requires_lab": True,
            }
        ],
        "lessons": [
            {
                "lesson_id": f"lesson-{course_id}-foundation",
                "title": f"{clean_topic} foundation",
                "scenes": scenes,
            }
        ],
        "assessments": [
            {
                "assessment_id": assessment_id,
                "objective_ids": [objective_id],
                "type": "checkpoint_quiz",
                "source_refs": source_ids,
            }
        ],
        "labs": [
            {
                "lab_id": lab_id,
                "objective_ids": [objective_id],
                "evidence_required": ["observation", "decision", "reflection"],
            }
        ],
        "high_risk_claims": [],
        "generation_inputs_ref": f"generated://course-compiler/{course_id}/{_utc_stamp()}",
    }


def _scenes(
    *,
    course_id: str,
    topic: str,
    objective_id: str,
    source_refs: list[str],
    lab_id: str,
) -> list[dict[str, Any]]:
    return [
        _slide_scene(course_id, "orient", 1, "Why this matters", topic, objective_id, source_refs),
        _slide_scene(course_id, "concept", 2, "Core idea", topic, objective_id, source_refs),
        _interactive_scene(course_id, 3, topic, objective_id, source_refs),
        _quiz_scene(course_id, "diagnose", 4, "Checkpoint", topic, objective_id, source_refs),
        _pbl_scene(course_id, 5, topic, objective_id, source_refs, lab_id),
        _quiz_scene(course_id, "reflect_evidence", 6, "Evidence reflection", topic, objective_id, source_refs),
    ]


def _slide_scene(
    course_id: str,
    kind: str,
    order: int,
    title: str,
    topic: str,
    objective_id: str,
    source_refs: list[str],
) -> dict[str, Any]:
    return {
        "course_id": course_id,
        "scene_id": f"scene-{order}-{kind}",
        "kind": kind,
        "title": title,
        "order": order,
        "objective_ids": [objective_id],
        "source_refs": source_refs,
        "openmaic_content": {
            "type": "slide",
            "canvas": {
                "id": f"canvas-{order}",
                "elements": [
                    {"type": "text", "text": title},
                    {"type": "text", "text": f"Topic: {topic}"},
                    {"type": "text", "text": "Use evidence before moving to practice."},
                ],
                "background": {"type": "solid", "color": "#FFFFFF"},
            },
        },
    }


def _interactive_scene(
    course_id: str,
    order: int,
    topic: str,
    objective_id: str,
    source_refs: list[str],
) -> dict[str, Any]:
    return {
        "course_id": course_id,
        "scene_id": f"scene-{order}-observe",
        "kind": "observe",
        "title": "Observe the pattern",
        "order": order,
        "objective_ids": [objective_id],
        "source_refs": source_refs,
        "sandbox_profile": "openmaic-contained-html",
        "openmaic_content": {
            "type": "interactive",
            "html": (
                "<!doctype html><html><body>"
                f"<h1>{topic}</h1><p>Change one variable and record what evidence changes.</p>"
                "</body></html>"
            ),
            "assets": [],
        },
    }


def _quiz_scene(
    course_id: str,
    kind: str,
    order: int,
    title: str,
    topic: str,
    objective_id: str,
    source_refs: list[str],
) -> dict[str, Any]:
    return {
        "course_id": course_id,
        "scene_id": f"scene-{order}-{kind}",
        "kind": kind,
        "title": title,
        "order": order,
        "objective_ids": [objective_id],
        "source_refs": source_refs,
        "assessment_refs": [f"assess-{course_id}-checkpoint"],
        "openmaic_content": {
            "type": "quiz",
            "questions": [
                {
                    "prompt": f"Which evidence best supports applying {topic}?",
                    "choices": ["A source-backed observation", "A guess", "An unrelated example"],
                    "answer": "A source-backed observation",
                    "objective_ids": [objective_id],
                }
            ],
        },
    }


def _pbl_scene(
    course_id: str,
    order: int,
    topic: str,
    objective_id: str,
    source_refs: list[str],
    lab_id: str,
) -> dict[str, Any]:
    return {
        "course_id": course_id,
        "scene_id": f"scene-{order}-execute-lab",
        "kind": "execute_lab",
        "title": "Evidence lab",
        "order": order,
        "objective_ids": [objective_id],
        "source_refs": source_refs,
        "lab_refs": [lab_id],
        "openmaic_content": {
            "type": "pbl",
            "project": {
                "title": f"Apply {topic}",
                "tasks": [
                    "State the decision to make.",
                    "Collect one observation from the source material.",
                    "Submit the evidence and explain the decision.",
                ],
            },
        },
    }


def _slug(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    collapsed = "-".join(part for part in normalized.split("-") if part)
    if collapsed:
        return collapsed[:80]
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
