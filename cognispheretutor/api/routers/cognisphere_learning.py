"""Guided Learning ↔ Cognisphere Learning Plugins API (product binding)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError
from cognispheretutor.learning.cognisphere_seed import (
    is_cognisphere_path_id,
    mastery_path_id_for_domain,
    modules_from_knowledge,
    seed_payload_from_import_receipt,
)
from cognispheretutor.learning.models import LearningStage
from cognispheretutor.learning.service import LearningService
from cognispheretutor.learning.storage import LearningStore

router = APIRouter()

_MASTERY_CAPABILITY = "mastery_path"


def _service() -> LearningService:
    return LearningService(LearningStore())


def _http_error(exc: CognisphereIntegrationError) -> HTTPException:
    status = 400
    if exc.code in {
        "plugins_root_missing",
        "install_registry_missing",
        "trusted_context_kit_unavailable",
        "sandbox_unauthorized",
        "benchmark_unavailable",
    }:
        status = 503
    elif exc.code == "domain_required":
        status = 422
    return HTTPException(status_code=status, detail=exc.to_dict())


def _chat_continue_url(path_id: str, *, tutor_session_id: str | None = None) -> str:
    """Deep-link into Chat with Mastery Path mode pre-selected."""
    from urllib.parse import quote, urlencode

    query = {"capability": _MASTERY_CAPABILITY}
    if tutor_session_id:
        query["tutor_session"] = tutor_session_id
    return f"/home/{quote(path_id, safe='')}?{urlencode(query)}"


class ImportSeedRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=64)
    path_id: str | None = Field(
        default=None,
        description="Optional Mastery Path id; default csphere-{domain}",
    )
    seed_mastery_path: bool = True
    persist_import: bool = True


class TutorStartRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=64)
    slug: str = Field(..., min_length=1, max_length=200)
    hint_level: int = Field(0, ge=0, le=4)
    path_id: str | None = None
    persist: bool = False


class SuggestFocusRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=64)
    slug: str | None = None
    path_id: str | None = None


class PlanPathRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=64)
    learner_id: str = "offline-learner"
    path_id: str | None = None


class TrustedContextImportRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=200)
    payload_kind: str = Field("knowledge_pack", min_length=1, max_length=64)
    package: dict[str, Any] | None = Field(
        default=None,
        description="Offline package body; omit to fetch from live kit when configured",
    )
    persist: bool = True


@router.get("/status")
async def cognisphere_learning_status():
    """Discovery + gate snapshot for the Guided Learning UI."""
    from cognispheretutor.integrations.cognisphere import gate_status, list_plugins
    from cognispheretutor.integrations.cognisphere.security_gates import is_sandbox_authorized
    from cognispheretutor.integrations.cognisphere.trusted_context_client import (
        trusted_context_status,
    )

    try:
        discovery = list_plugins()
    except CognisphereIntegrationError as exc:
        raise _http_error(exc) from exc

    plugins = []
    for item in discovery.get("plugins") or []:
        manifest = item.get("manifest") or {}
        domain = str(item.get("domain") or "")
        plugins.append(
            {
                "domain": domain,
                "plugin_id": manifest.get("plugin_id"),
                "lifecycle": item.get("lifecycle"),
                "capabilities": list(manifest.get("capabilities") or []),
                "path_id": mastery_path_id_for_domain(domain) if domain else None,
                "valid": bool((item.get("validation") or {}).get("ok")),
            }
        )

    return {
        "ok": bool(discovery.get("ok")),
        "plugins_root": discovery.get("plugins_root"),
        "plugin_count": discovery.get("plugin_count"),
        "issues": list(discovery.get("issues") or []),
        "gates": {
            **gate_status(),
            "sandbox_authorized": is_sandbox_authorized(),
            "trusted_context": trusted_context_status(),
        },
        "plugins": plugins,
        "defaults": {
            "chat_capability": _MASTERY_CAPABILITY,
        },
    }


@router.post("/import-and-seed")
async def import_and_seed(body: ImportSeedRequest):
    """Export domain pack, optionally seed a Mastery Path from its knowledge."""
    from cognispheretutor.integrations.cognisphere import export_and_import

    path_id = body.path_id or mastery_path_id_for_domain(body.domain)
    if "/" in path_id or "\\" in path_id or ".." in path_id or ":" in path_id:
        raise HTTPException(status_code=400, detail="Invalid path_id")

    try:
        receipt = export_and_import(
            body.domain,
            {"persist": body.persist_import},
        )
    except CognisphereIntegrationError as exc:
        raise _http_error(exc) from exc

    if not receipt.get("ok"):
        raise HTTPException(status_code=400, detail=receipt)

    seed_info: dict[str, Any] | None = None
    if body.seed_mastery_path:
        # Prefer knowledge from the cached bundle file when available.
        knowledge = _load_imported_knowledge(body.domain, receipt)
        modules = modules_from_knowledge(
            knowledge,
            domain=body.domain,
            path_id=path_id,
        )
        if not modules or not any(m.knowledge_points for m in modules):
            raise HTTPException(
                status_code=422,
                detail={
                    "ok": False,
                    "code": "empty_knowledge",
                    "message": "Import succeeded but knowledge was empty; cannot seed Mastery Path",
                    "knowledge_summary": receipt.get("knowledge_summary"),
                },
            )
        service = _service()
        progress = service.get_or_create(path_id)
        service.init_modules(progress, modules)
        progress.current_module_id = modules[0].id
        progress.current_kp_index = 0
        progress.current_stage = LearningStage.DIAGNOSTIC
        service.save(progress)
        non_overview = [m for m in modules if not m.id.endswith("-overview")]
        seed_info = {
            "path_id": path_id,
            "module_count": len(modules),
            "kp_count": sum(len(m.knowledge_points) for m in modules),
            "modules": [
                {"id": m.id, "name": m.name, "kp_count": len(m.knowledge_points)} for m in modules
            ],
            "knowledge_sparse": len(non_overview) == 0,
            "continue_in_chat": _chat_continue_url(path_id),
            "note": (
                "Bundle knowledge was sparse; seeded an overview path. "
                "Re-import after the domain plugin ontology/export is available "
                "for full knowledge items."
                if len(non_overview) == 0
                else None
            ),
        }

    return {
        "ok": True,
        "domain": body.domain,
        "import": {
            "status": receipt.get("status"),
            "phase": receipt.get("phase"),
            "knowledge_summary": receipt.get("knowledge_summary"),
            "artifact_path": receipt.get("artifact_path"),
        },
        "mastery_path": seed_info,
        "is_cognisphere_path": is_cognisphere_path_id(path_id),
        "continue_in_chat": _chat_continue_url(path_id) if seed_info else None,
    }


def _load_imported_knowledge(domain: str, receipt: dict[str, Any]) -> dict[str, Any]:
    """Load full bundle.knowledge from import cache when present."""
    artifact = receipt.get("artifact_path")
    if artifact:
        bundle_path = Path(artifact) / "bundle.json"
        if bundle_path.is_file():
            data = json.loads(bundle_path.read_text(encoding="utf-8"))
            kn = data.get("knowledge")
            if isinstance(kn, dict):
                return kn

    seeded = seed_payload_from_import_receipt(receipt)
    return dict(seeded.get("knowledge") or {})


@router.post("/trusted-context/import")
async def import_trusted_context(body: TrustedContextImportRequest):
    """DT-P3: offline package import, or live kit fetch+import when URL is set."""
    from cognispheretutor.integrations.cognisphere.trusted_context_client import (
        fetch_and_import_trusted_context,
        import_trusted_context_into_workspace,
        kit_configured,
    )

    try:
        if body.package is not None:
            receipt = import_trusted_context_into_workspace(
                body.package,
                persist=body.persist,
            )
            receipt["source"] = "offline_package"
        elif kit_configured():
            receipt = fetch_and_import_trusted_context(
                body.project_id,
                body.payload_kind,
                persist=body.persist,
            )
        else:
            raise CognisphereIntegrationError(
                "trusted_context_kit_unavailable",
                message=(
                    "No package body and COGNISPHERE_TRUSTED_CONTEXT_BASE_URL unset; "
                    "pass an offline package or configure the live kit"
                ),
                details={"project_id": body.project_id, "payload_kind": body.payload_kind},
            )
    except CognisphereIntegrationError as exc:
        raise _http_error(exc) from exc
    return receipt


@router.post("/suggest-focus")
async def suggest_focus(body: SuggestFocusRequest):
    from cognispheretutor.integrations.cognisphere import suggest_tutor_focus

    try:
        result = suggest_tutor_focus(domain=body.domain, problem_slug=body.slug)
    except CognisphereIntegrationError as exc:
        raise _http_error(exc) from exc
    return result


@router.post("/plan-path")
async def plan_path(body: PlanPathRequest):
    from cognispheretutor.integrations.cognisphere import plan_skill_path

    try:
        result = plan_skill_path(domain=body.domain, learner_id=body.learner_id)
    except CognisphereIntegrationError as exc:
        raise _http_error(exc) from exc
    if body.path_id and result.get("ok"):
        result = dict(result)
        result["path_id"] = body.path_id
        result["continue_in_chat"] = _chat_continue_url(body.path_id)
    return result


@router.post("/tutor/start")
async def tutor_start(body: TutorStartRequest):
    from cognispheretutor.integrations.cognisphere import start_tutor_session

    try:
        result = start_tutor_session(
            body.slug,
            domain=body.domain,
            hint_level=body.hint_level,
            persist=body.persist,
        )
    except CognisphereIntegrationError as exc:
        raise _http_error(exc) from exc
    payload = dict(result)
    session = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    tutor_session_id = str(session.get("session_id") or "")
    if body.path_id:
        payload["path_id"] = body.path_id
        payload["continue_in_chat"] = _chat_continue_url(
            body.path_id,
            tutor_session_id=tutor_session_id or None,
        )
        payload["chat_capability"] = _MASTERY_CAPABILITY
    if tutor_session_id:
        payload["tutor_session_id"] = tutor_session_id
        payload["events_url"] = (
            f"/api/v1/learning/cognisphere/tutor/events?session_id={tutor_session_id}"
        )
    return payload


@router.get("/tutor/events")
async def tutor_events_sse(
    session_id: str = Query(..., min_length=1, max_length=200),
    since: int = Query(0, ge=0),
):
    """SSE stream of persisted tutor session events (DT-P4 product push)."""
    from cognispheretutor.integrations.cognisphere.runtime_callbacks import (
        resolve_runtime_state_dir,
    )

    events_path = resolve_runtime_state_dir(session_id=session_id) / "events.jsonl"

    async def _generate() -> AsyncIterator[str]:
        cursor = since
        # Replay existing lines first, then poll for appends.
        while True:
            if events_path.is_file():
                lines = events_path.read_text(encoding="utf-8").splitlines()
                while cursor < len(lines):
                    line = lines[cursor].strip()
                    cursor += 1
                    if not line:
                        continue
                    yield f"id: {cursor}\ndata: {line}\n\n"
            yield f": ping {cursor}\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
