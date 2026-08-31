"""AI Infra Twin integration API for Learning Space."""

from __future__ import annotations

import asyncio
import json
import time
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


class LearningWorkspaceSaveRequest(BaseModel):
    state: LearningWorkspaceState


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
                "message": "AI Infra Twin lab engine is unavailable",
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
    try:
        summary = await asyncio.to_thread(client.get_json, "/api/summary")  # type: ignore[assignment]
        curriculum = await asyncio.to_thread(client.get_json, "/api/curriculum")  # type: ignore[assignment]
        maturity = await asyncio.to_thread(client.get_json, "/api/lab-maturity")  # type: ignore[assignment]
    except AetherInfraTwinError as exc:
        issues.append(str(exc))
    return {
        "ok": not issues,
        "base_url": client.base_url,
        "embed_url": client.embed_url(),
        "summary": summary,
        "curriculum": curriculum,
        "maturity": maturity,
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
    path = _workspace_state_path(workspace_id)
    if not path.exists():
        return {
            "ok": True,
            "workspace_id": workspace_id,
            "state": _empty_workspace_state(),
            "updated_at": None,
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = LearningWorkspaceState.model_validate(data.get("state") or {})
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid workspace state") from exc
    return {
        "ok": True,
        "workspace_id": workspace_id,
        "state": state.model_dump(mode="json"),
        "updated_at": data.get("updated_at"),
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
