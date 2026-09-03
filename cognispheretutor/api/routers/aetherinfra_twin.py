"""AI Infra Twin integration API for Learning Space."""

from __future__ import annotations

import asyncio
import json
import time
from collections import Counter
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from cognispheretutor.integrations.aetherinfra_twin import (
    AetherInfraTwinError,
    default_client,
)
from cognispheretutor.services.file_io import atomic_write_text
from cognispheretutor.services.path_service import get_path_service

router = APIRouter()

CONTENT_ONLY_MESSAGE = (
    "AI Infra course content is available through CognisphereLearningPlugins. "
    "Start AetherAI-Infra-Twin to run labs, open the Twin console, and generate "
    "evidence bundles."
)


class DiagnosisRequest(BaseModel):
    selected_diagnosis: str = Field(..., min_length=1, max_length=200)
    evidence_refs: list[str] = Field(default_factory=list)
    notes: str = Field("", max_length=2000)


class LearningWorkspaceState(BaseModel):
    selected_course_id: str | None = Field(default=None, max_length=200)
    selected_unit_id: str | None = Field(default=None, max_length=300)
    assessment_mode: str = Field(default="learn", max_length=40)
    quiz_answers: dict[str, str] = Field(default_factory=dict)
    completed_units: dict[str, bool] = Field(default_factory=dict)
    reflection_notes: dict[str, str] = Field(default_factory=dict)
    diagnosis_notes: dict[str, str] = Field(default_factory=dict)
    source_document_notes: dict[str, str] = Field(default_factory=dict)
    evidence_bundles: dict[str, list[str]] = Field(default_factory=dict)
    review_ledger: dict[str, dict[str, str]] = Field(default_factory=dict)
    learning_events: list[dict[str, Any]] = Field(default_factory=list)


class LearningWorkspaceSaveRequest(BaseModel):
    state: LearningWorkspaceState


class LearningEventRequest(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=80)
    unit_id: str | None = Field(default=None, max_length=300)
    course_id: str | None = Field(default=None, max_length=200)
    score: float | None = Field(default=None, ge=0, le=1)
    error_types: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=2000)


TRANSFER_EVENT_TYPES = {"transfer_challenge", "capstone_transfer"}
EXPERT_EVENT_TYPES = {"expert_agreement", "expert_review"}
PRE_EVENT_TYPES = {"pre_check", "pretest"}
POST_EVENT_TYPES = {"post_check", "posttest"}


def _validate_workspace_id(workspace_id: str) -> None:
    if (
        not workspace_id
        or ".." in workspace_id
        or "/" in workspace_id
        or "\\" in workspace_id
        or ":" in workspace_id
    ):
        raise HTTPException(status_code=400, detail="Invalid workspace_id")


def _workspace_state_path(workspace_id: str):
    _validate_workspace_id(workspace_id)
    root = get_path_service().get_workspace_dir() / "ai_infra_learning_workspaces"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{workspace_id}.json"


def _empty_workspace_state() -> dict[str, Any]:
    return LearningWorkspaceState().model_dump(mode="json")


def _load_workspace_state(workspace_id: str) -> tuple[dict[str, Any], float | None]:
    path = _workspace_state_path(workspace_id)
    if not path.exists():
        return _empty_workspace_state(), None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = LearningWorkspaceState.model_validate(data.get("state") or {})
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid workspace state") from exc
    return state.model_dump(mode="json"), data.get("updated_at")


def _summarize_learning_workspace(state: dict[str, Any]) -> dict[str, Any]:
    events = [event for event in state.get("learning_events", []) if isinstance(event, dict)]
    event_types = Counter(str(event.get("event_type") or "") for event in events)
    error_types = Counter(
        str(error)
        for event in events
        for error in event.get("error_types", [])
        if str(error)
    )
    evidence_refs = [
        str(ref)
        for event in events
        for ref in event.get("evidence_refs", [])
        if str(ref)
    ]
    scored_events = [event for event in events if isinstance(event.get("score"), (int, float))]
    scores = [float(event["score"]) for event in scored_events]
    completed_units = state.get("completed_units", {}) or {}
    evidence_bundles = state.get("evidence_bundles", {}) or {}
    covered_units = {
        str(event.get("unit_id"))
        for event in events
        if event.get("unit_id") and (event.get("evidence_refs") or event.get("score") is not None)
    }
    covered_units.update(
        str(unit_id)
        for unit_id, refs in evidence_bundles.items()
        if refs
    )
    stage_counts = {
        "preCheck": sum(event_types[event_type] for event_type in PRE_EVENT_TYPES),
        "postCheck": sum(event_types[event_type] for event_type in POST_EVENT_TYPES),
        "transferChallenge": sum(event_types[event_type] for event_type in TRANSFER_EVENT_TYPES),
        "expertAgreement": sum(event_types[event_type] for event_type in EXPERT_EVENT_TYPES),
    }
    return {
        "event_count": len(events),
        "scored_event_count": len(scored_events),
        "average_score": round(sum(scores) / len(scores), 3) if scores else None,
        "completed_unit_count": sum(1 for value in completed_units.values() if value is True),
        "evidence_ref_count": len(set(evidence_refs)),
        "evidence_covered_unit_count": len(covered_units),
        "required_stage_counts": stage_counts,
        "event_type_counts": dict(sorted(event_types.items())),
        "error_type_counts": dict(sorted(error_types.items())),
        "weakest_error_types": [name for name, _count in error_types.most_common(5)],
        "latest_events": sorted(
            events,
            key=lambda event: float(event.get("created_at") or 0),
            reverse=True,
        )[:10],
    }


async def _call(method: str, path: str, payload: dict[str, Any] | None = None):
    client = default_client()
    try:
        if method == "GET":
            return await asyncio.to_thread(client.get_json, path)
        if method == "POST":
            return await asyncio.to_thread(client.post_json, path, payload or {})
    except AetherInfraTwinError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "code": "aetherinfra_twin_unavailable",
                "runtime_mode": "content_only",
                "lab_runtime_available": False,
                "content_runtime_available": True,
                "message": "AI Infra Twin lab engine is unavailable",
                "learner_message": CONTENT_ONLY_MESSAGE,
                "detail": str(exc),
                "base_url": client.base_url,
            },
        ) from exc
    raise HTTPException(status_code=405, detail="unsupported method")


@router.get("/status")
async def status() -> dict[str, Any]:
    client = default_client()
    issues: list[str] = []
    summary: dict[str, Any] = {}
    curriculum: dict[str, Any] = {}
    maturity: dict[str, Any] = {}
    capstone_flows: dict[str, Any] = {}
    maturity_roadmap: dict[str, Any] = {}
    try:
        summary = await asyncio.to_thread(client.get_json, "/api/summary")  # type: ignore[assignment]
        curriculum = await asyncio.to_thread(client.get_json, "/api/curriculum")  # type: ignore[assignment]
        maturity = await asyncio.to_thread(client.get_json, "/api/lab-maturity")  # type: ignore[assignment]
        capstone_flows = await asyncio.to_thread(client.get_json, "/api/capstone-flows")  # type: ignore[assignment]
        maturity_roadmap = await asyncio.to_thread(client.get_json, "/api/maturity-roadmap")  # type: ignore[assignment]
    except AetherInfraTwinError as exc:
        issues.append(str(exc))
    ok = not issues
    return {
        "ok": ok,
        "runtime_mode": "full_twin" if ok else "content_only",
        "lab_runtime_available": ok,
        "content_runtime_available": True,
        "learner_message": (
            "AI Infra Twin is connected. Labs, evidence bundles, and diagnosis scoring are available."
            if ok
            else CONTENT_ONLY_MESSAGE
        ),
        "unavailable_features": []
        if ok
        else [
            "run_lab",
            "evidence_bundle_generation",
            "diagnosis_scoring",
            "twin_webui",
        ],
        "base_url": client.base_url,
        "embed_url": client.embed_url(),
        "summary": summary,
        "curriculum": curriculum,
        "maturity": maturity,
        "capstone_flows": capstone_flows,
        "maturity_roadmap": maturity_roadmap,
        "issues": issues,
    }


@router.get("/labs")
async def labs():
    return await _call("GET", "/api/tutor/labs")


@router.get("/curriculum")
async def curriculum():
    return await _call("GET", "/api/curriculum")


@router.get("/maturity")
async def maturity():
    return await _call("GET", "/api/lab-maturity")


@router.get("/capstone-flows")
async def capstone_flows():
    return await _call("GET", "/api/capstone-flows")


@router.get("/maturity-roadmap")
async def maturity_roadmap():
    return await _call("GET", "/api/maturity-roadmap")


@router.get("/evidence")
async def evidence():
    return await _call("GET", "/api/evidence")


@router.get("/labs/{lab_id}")
async def lab(lab_id: str) -> dict[str, Any]:
    client = default_client()
    result = await _call("GET", f"/api/tutor/labs/{lab_id}")
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="unexpected lab payload")
    result["embed_url"] = client.embed_url(lab_id)
    return result


@router.post("/labs/{lab_id}/run")
async def run_lab(lab_id: str) -> dict[str, Any]:
    return await _call("POST", f"/api/tutor/labs/{lab_id}/run", {})


@router.post("/labs/{lab_id}/diagnosis")
async def submit_diagnosis(lab_id: str, payload: DiagnosisRequest) -> dict[str, Any]:
    return await _call(
        "POST",
        f"/api/tutor/labs/{lab_id}/diagnosis",
        {
            "selectedDiagnosis": payload.selected_diagnosis,
            "evidenceRefs": payload.evidence_refs,
            "notes": payload.notes,
        },
    )


@router.get("/workspace/{workspace_id}")
async def get_learning_workspace(workspace_id: str) -> dict[str, Any]:
    state, updated_at = _load_workspace_state(workspace_id)
    return {
        "ok": True,
        "workspace_id": workspace_id,
        "state": state,
        "updated_at": updated_at,
    }


@router.put("/workspace/{workspace_id}")
async def save_learning_workspace(
    workspace_id: str,
    payload: LearningWorkspaceSaveRequest,
) -> dict[str, Any]:
    path = _workspace_state_path(workspace_id)
    updated_at = time.time()
    data = {
        "workspace_id": workspace_id,
        "updated_at": updated_at,
        "state": payload.state.model_dump(mode="json"),
    }
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))
    return {
        "ok": True,
        "workspace_id": workspace_id,
        "state": data["state"],
        "updated_at": updated_at,
    }


@router.post("/workspace/{workspace_id}/learning-events")
async def append_learning_event(
    workspace_id: str,
    payload: LearningEventRequest,
) -> dict[str, Any]:
    state, _updated_at = _load_workspace_state(workspace_id)
    event = {
        "event_type": payload.event_type,
        "unit_id": payload.unit_id,
        "course_id": payload.course_id,
        "score": payload.score,
        "error_types": payload.error_types,
        "evidence_refs": payload.evidence_refs,
        "notes": payload.notes,
        "created_at": time.time(),
    }
    state.setdefault("learning_events", []).append(event)
    path = _workspace_state_path(workspace_id)
    updated_at = time.time()
    atomic_write_text(
        path,
        json.dumps(
            {
                "workspace_id": workspace_id,
                "updated_at": updated_at,
                "state": state,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    return {
        "ok": True,
        "workspace_id": workspace_id,
        "event": event,
        "state": state,
        "updated_at": updated_at,
    }


@router.get("/workspace/{workspace_id}/learning-evaluation")
async def learning_evaluation(workspace_id: str) -> dict[str, Any]:
    state, updated_at = _load_workspace_state(workspace_id)
    return {
        "ok": True,
        "workspace_id": workspace_id,
        "updated_at": updated_at,
        "summary": _summarize_learning_workspace(state),
    }


@router.delete("/workspace/{workspace_id}")
async def delete_learning_workspace(workspace_id: str) -> dict[str, Any]:
    path = _workspace_state_path(workspace_id)
    if path.exists():
        path.unlink()
    return {
        "ok": True,
        "workspace_id": workspace_id,
        "state": _empty_workspace_state(),
        "updated_at": None,
    }
