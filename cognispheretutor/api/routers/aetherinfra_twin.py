"""AI Infra Twin integration API for Learning Space."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from cognispheretutor.integrations.aetherinfra_twin import (
    AetherInfraTwinError,
    default_client,
)

router = APIRouter()


class DiagnosisRequest(BaseModel):
    selected_diagnosis: str = Field(..., min_length=1, max_length=200)
    evidence_refs: list[str] = Field(default_factory=list)
    notes: str = Field("", max_length=2000)


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
