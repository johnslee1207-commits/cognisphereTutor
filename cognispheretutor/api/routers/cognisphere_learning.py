"""Guided Learning ↔ Cognisphere Learning Plugins API (product binding)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
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
    return HTTPException(status_code=status, detail=exc.to_dict())


class ImportSeedRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=64)
    path_id: str | None = Field(
        default=None,
        description="Optional Mastery Path id; default csphere-{domain}",
    )
    seed_mastery_path: bool = True
    persist_import: bool = True


class TutorStartRequest(BaseModel):
    slug: str = Field(..., min_length=1, max_length=200)
    hint_level: int = Field(0, ge=0, le=4)
    path_id: str | None = None
    persist: bool = False


class SuggestFocusRequest(BaseModel):
    slug: str | None = None
    path_id: str | None = None


class PlanPathRequest(BaseModel):
    learner_id: str = "offline-learner"
    path_id: str | None = None


@router.get("/status")
async def cognisphere_learning_status():
    """Discovery + gate snapshot for the Guided Learning UI."""
    from cognispheretutor.integrations.cognisphere import gate_status, list_plugins
    from cognispheretutor.integrations.cognisphere.security_gates import is_sandbox_authorized

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
        },
        "plugins": plugins,
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
            "note": (
                "Bundle knowledge was sparse; seeded an overview path. "
                "Re-import after LC-003 ontology is available for full problems/skills."
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
    }


def _load_imported_knowledge(domain: str, receipt: dict[str, Any]) -> dict[str, Any]:
    """Load full bundle.knowledge from import cache when present."""
    import json
    from pathlib import Path

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


@router.post("/suggest-focus")
async def suggest_focus(body: SuggestFocusRequest):
    from cognispheretutor.integrations.cognisphere import suggest_tutor_focus

    try:
        result = suggest_tutor_focus(problem_slug=body.slug)
    except CognisphereIntegrationError as exc:
        raise _http_error(exc) from exc
    return result


@router.post("/plan-path")
async def plan_path(body: PlanPathRequest):
    from cognispheretutor.integrations.cognisphere import plan_skill_path

    try:
        result = plan_skill_path(learner_id=body.learner_id)
    except CognisphereIntegrationError as exc:
        raise _http_error(exc) from exc
    if body.path_id and result.get("ok"):
        result = dict(result)
        result["path_id"] = body.path_id
    return result


@router.post("/tutor/start")
async def tutor_start(body: TutorStartRequest):
    from cognispheretutor.integrations.cognisphere import start_tutor_session

    try:
        result = start_tutor_session(
            body.slug,
            hint_level=body.hint_level,
            persist=body.persist,
        )
    except CognisphereIntegrationError as exc:
        raise _http_error(exc) from exc
    payload = dict(result)
    if body.path_id:
        payload["path_id"] = body.path_id
        payload["continue_in_chat"] = f"/home/{body.path_id}"
    return payload
