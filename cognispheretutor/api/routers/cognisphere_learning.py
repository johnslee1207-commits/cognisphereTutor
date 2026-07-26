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
from cognispheretutor.learning.models import (
    KnowledgePoint,
    KnowledgeType,
    LearningModule,
    LearningStage,
)
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


class CrossDomainRequest(BaseModel):
    required_capabilities: list[str] = Field(default_factory=list)
    goal: str | None = Field(
        default=None,
        description="Natural-language learning goal (optional; used by negotiator/SDK)",
        max_length=2000,
    )


class ComposeRequest(BaseModel):
    domains: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)


class ComposeAndSeedRequest(BaseModel):
    domains: list[str] = Field(
        default_factory=list,
        description="Domains to compose; empty + capabilities → discover via cross-domain",
    )
    required_capabilities: list[str] = Field(default_factory=list)
    seed_mastery_path: bool = True
    persist_import: bool = True
    stop_on_error: bool = False


class RecommendFromGoalRequest(BaseModel):
    goal: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural-language learning goal (domain-agnostic)",
    )
    required_capabilities: list[str] = Field(
        default_factory=lambda: ["deeptutor_export"],
        description="Capability filter for recommendations (default: Tutor handoff export)",
    )
    compose_and_seed: bool = Field(
        False,
        description="When true, immediately compose+seed all recommended domains",
    )
    stop_on_error: bool = False


def _validate_path_id(path_id: str) -> None:
    if "/" in path_id or "\\" in path_id or ".." in path_id or ":" in path_id:
        raise HTTPException(status_code=400, detail="Invalid path_id")


async def _import_and_seed_domain(
    domain: str,
    *,
    path_id: str | None = None,
    seed_mastery_path: bool = True,
    persist_import: bool = True,
) -> dict[str, Any]:
    """Shared import+seed used by single-domain and compose-and-seed endpoints."""
    from cognispheretutor.integrations.cognisphere import export_and_import
    from cognispheretutor.integrations.cognisphere.pack_distribution import import_bundled_pack

    resolved_path = path_id or mastery_path_id_for_domain(domain)
    _validate_path_id(resolved_path)

    try:
        receipt = export_and_import(
            domain,
            {"persist": persist_import},
        )
    except CognisphereIntegrationError as exc:
        receipt = import_bundled_pack(domain, persist=persist_import)
        if receipt is None:
            raise _http_error(exc) from exc

    if not receipt.get("ok"):
        raise HTTPException(status_code=400, detail=receipt)

    seed_info: dict[str, Any] | None = None
    if seed_mastery_path:
        knowledge = _load_imported_knowledge(domain, receipt)
        modules = modules_from_knowledge(
            knowledge,
            domain=domain,
            path_id=resolved_path,
        )
        fallback_used = False
        if len([m for m in modules if not m.id.endswith("-overview")]) == 0:
            fallback_modules = _modules_from_runtime_plan(domain, resolved_path)
            if fallback_modules:
                modules = modules + fallback_modules
                fallback_used = True
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
        progress = service.get_or_create(resolved_path)
        service.init_modules(progress, modules)
        progress.current_module_id = modules[0].id
        progress.current_kp_index = 0
        progress.current_stage = LearningStage.DIAGNOSTIC
        service.save(progress)
        non_overview = [m for m in modules if not m.id.endswith("-overview")]
        seed_info = {
            "path_id": resolved_path,
            "module_count": len(modules),
            "kp_count": sum(len(m.knowledge_points) for m in modules),
            "modules": [
                {"id": m.id, "name": m.name, "kp_count": len(m.knowledge_points)} for m in modules
            ],
            "knowledge_sparse": len(non_overview) == 0,
            "runtime_plan_fallback": fallback_used,
            "continue_in_chat": _chat_continue_url(resolved_path),
            "note": (
                (
                    "Bundle knowledge was sparse; seeded a plugin runtime plan. "
                    "Re-import after the domain plugin ontology/export is available "
                    "for full knowledge items."
                )
                if fallback_used
                else (
                    "Bundle knowledge was sparse; seeded an overview path. "
                    "Re-import after the domain plugin ontology/export is available "
                    "for full knowledge items."
                )
                if len(non_overview) == 0
                else None
            ),
        }

    return {
        "ok": True,
        "domain": domain,
        "import": {
            "status": receipt.get("status"),
            "phase": receipt.get("phase"),
            "knowledge_summary": receipt.get("knowledge_summary"),
            "artifact_path": receipt.get("artifact_path"),
            "distribution_source": receipt.get("distribution_source") or "external_plugin",
        },
        "mastery_path": seed_info,
        "is_cognisphere_path": is_cognisphere_path_id(resolved_path),
        "continue_in_chat": _chat_continue_url(resolved_path) if seed_info else None,
    }


@router.get("/ability-radar")
async def ability_radar(
    path_id: str | None = Query(
        default=None,
        description="Optional Mastery Path id to expand axes / weak areas",
        max_length=200,
    ),
    weak_limit: int = Query(8, ge=1, le=40),
    include_skill_graph: bool = Query(
        True,
        description="When path is Cognisphere-seeded, attach skill_graph plan hint if available",
    ),
):
    """Domain-level mastery % + weak areas (User Manual §6 style).

    Aggregates LearningService mastery maps; optionally enriches Cognisphere
    paths with plugin skill_graph planning (fail-soft when unavailable).
    """
    from cognispheretutor.learning.ability_radar import build_ability_radar

    if path_id:
        _validate_path_id(path_id)
    return build_ability_radar(
        _service(),
        path_id=path_id,
        weak_limit=weak_limit,
        include_skill_graph=include_skill_graph,
    )


@router.get("/status")
async def cognisphere_learning_status():
    """Discovery + gate snapshot for the Guided Learning UI."""
    from cognispheretutor.integrations.cognisphere import gate_status, list_plugins
    from cognispheretutor.integrations.cognisphere.pack_distribution import (
        merge_external_and_bundled_discovery,
    )
    from cognispheretutor.integrations.cognisphere.security_gates import is_sandbox_authorized
    from cognispheretutor.integrations.cognisphere.trusted_context_client import (
        trusted_context_status,
    )

    try:
        discovery = list_plugins()
    except CognisphereIntegrationError as exc:
        raise _http_error(exc) from exc
    discovery = merge_external_and_bundled_discovery(discovery)

    plugins = []
    for item in discovery.get("plugins") or []:
        manifest = item.get("manifest") or {}
        domain = str(item.get("domain") or "")
        plugins.append(
            {
                "domain": domain,
                "plugin_id": manifest.get("plugin_id"),
                "display_name": manifest.get("display_name") or manifest.get("name"),
                "description": manifest.get("description"),
                "version": manifest.get("version"),
                "lifecycle": item.get("lifecycle"),
                "capabilities": list(manifest.get("capabilities") or []),
                "distribution": item.get("distribution") or {},
                "tutor_pack": item.get("tutor_pack") or {},
                "path_id": mastery_path_id_for_domain(domain) if domain else None,
                "valid": bool((item.get("validation") or {}).get("ok")),
                "source": (item.get("distribution") or {}).get("source") or "external_plugin",
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
        "tutor_pack": discovery.get("tutor_pack") or {},
        "distribution_catalog": discovery.get("distribution_catalog") or {},
        "bundled_distribution": discovery.get("bundled_distribution") or {},
        "defaults": {
            "chat_capability": _MASTERY_CAPABILITY,
        },
    }


@router.post("/import-and-seed")
async def import_and_seed(body: ImportSeedRequest):
    """Export domain pack, optionally seed a Mastery Path from its knowledge."""
    return await _import_and_seed_domain(
        body.domain,
        path_id=body.path_id,
        seed_mastery_path=body.seed_mastery_path,
        persist_import=body.persist_import,
    )


@router.post("/cross-domain")
async def cross_domain(body: CrossDomainRequest):
    """DT-P6: query plugins matching required capabilities / optional NL goal."""
    from cognispheretutor.integrations.cognisphere import query_cross_domain

    result = query_cross_domain(
        {
            "required_capabilities": list(body.required_capabilities),
            "goal": body.goal,
        }
    )
    return result


@router.post("/compose")
async def compose(body: ComposeRequest):
    """DT-P6: compose multi-domain learning contexts (no seed)."""
    from cognispheretutor.integrations.cognisphere import compose_contexts

    result = compose_contexts(
        list(body.domains) or None,
        required_capabilities=list(body.required_capabilities) or None,
    )
    return result


@router.post("/compose-and-seed")
async def compose_and_seed(body: ComposeAndSeedRequest):
    """Compose selected domains, then import-and-seed each matched domain.

    Fail-closed per domain: when ``stop_on_error`` is true the first failure
    aborts; otherwise each domain gets an ok/error entry in ``seeds``.
    """
    from cognispheretutor.integrations.cognisphere import compose_contexts

    composition = compose_contexts(
        list(body.domains) or None,
        required_capabilities=list(body.required_capabilities) or None,
    )
    contexts = list(composition.get("contexts") or [])
    domain_list = [
        str(ctx.get("domain"))
        for ctx in contexts
        if ctx.get("domain") and (ctx.get("matched") is not False)
    ]
    if not domain_list and body.domains:
        # Compose returned no contexts; still try explicit domains the client selected.
        domain_list = [d.strip() for d in body.domains if str(d).strip()]

    seeds: list[dict[str, Any]] = []
    for domain in domain_list:
        try:
            seeded = await _import_and_seed_domain(
                domain,
                seed_mastery_path=body.seed_mastery_path,
                persist_import=body.persist_import,
            )
            seeds.append(seeded)
        except HTTPException as exc:
            entry = {
                "ok": False,
                "domain": domain,
                "error": exc.detail,
                "status_code": exc.status_code,
            }
            seeds.append(entry)
            if body.stop_on_error:
                break

    ok_count = sum(1 for s in seeds if s.get("ok"))
    return {
        "ok": ok_count > 0 and ok_count == len(seeds),
        "phase": "DT-P6",
        "compose": composition,
        "seeded_count": ok_count,
        "failed_count": len(seeds) - ok_count,
        "seeds": seeds,
        "continue_in_chat": next(
            (s.get("continue_in_chat") for s in seeds if s.get("continue_in_chat")),
            None,
        ),
    }


@router.post("/recommend-from-goal")
async def recommend_from_goal(body: RecommendFromGoalRequest):
    """NL learning goal → cross-domain plugin matches → optional one-click seed.

    Domain-agnostic: Tutor never hardcodes which domains to recommend; the
    negotiator/registry (and Cognisphere SDK when present) decide matches.
    """
    from cognispheretutor.integrations.cognisphere import query_cross_domain

    goal = body.goal.strip()
    if not goal:
        raise HTTPException(status_code=422, detail="goal is required")

    cross = query_cross_domain(
        {
            "required_capabilities": list(body.required_capabilities),
            "goal": goal,
        }
    )
    domains = [
        str(m.get("domain"))
        for m in (cross.get("matches") or [])
        if m.get("domain")
    ]
    # De-dupe while preserving order
    seen: set[str] = set()
    recommended: list[str] = []
    for domain in domains:
        if domain not in seen:
            seen.add(domain)
            recommended.append(domain)

    payload: dict[str, Any] = {
        "ok": bool(recommended),
        "phase": "DT-P6",
        "goal": goal,
        "required_capabilities": list(body.required_capabilities),
        "recommended_domains": recommended,
        "match_count": len(recommended),
        "matches": list(cross.get("matches") or []),
        "cross_domain": cross,
        "compose_seed": None,
        "continue_in_chat": None,
    }

    if body.compose_and_seed:
        if not recommended:
            raise HTTPException(
                status_code=422,
                detail={
                    "ok": False,
                    "code": "no_plugin_matches",
                    "message": "No plugins matched this goal; adjust the goal or install plugins",
                    "goal": goal,
                },
            )
        seeded = await compose_and_seed(
            ComposeAndSeedRequest(
                domains=recommended,
                required_capabilities=list(body.required_capabilities),
                seed_mastery_path=True,
                persist_import=True,
                stop_on_error=body.stop_on_error,
            )
        )
        payload["compose_seed"] = seeded
        payload["ok"] = bool(seeded.get("ok"))
        payload["continue_in_chat"] = seeded.get("continue_in_chat")
        payload["seeded_count"] = seeded.get("seeded_count")
        payload["failed_count"] = seeded.get("failed_count")

    return payload


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


def _modules_from_runtime_plan(domain: str, path_id: str) -> list[LearningModule]:
    """Build a minimal Mastery module from a plugin-provided runtime plan."""
    from cognispheretutor.integrations.cognisphere import plan_skill_path

    try:
        result = plan_skill_path(domain=domain)
    except CognisphereIntegrationError:
        return []
    if not result.get("ok"):
        return []
    plan = result.get("plan") if isinstance(result.get("plan"), dict) else {}
    raw_items = plan.get("next_sequence") or plan.get("gaps") or plan.get("steps") or []
    if not isinstance(raw_items, list) or not raw_items:
        return []

    kps: list[KnowledgePoint] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_items):
        if isinstance(item, dict):
            raw_id = item.get("skill_id") or item.get("id") or item.get("name") or index
            name = str(item.get("name") or item.get("skill_id") or raw_id).strip()
        else:
            raw_id = item
            name = str(item).strip()
        if not name:
            continue
        safe_id = str(raw_id).replace(":", "-").strip() or str(index)
        kp_id = f"rt-{safe_id}"[:120]
        if kp_id in seen:
            continue
        seen.add(kp_id)
        kps.append(
            KnowledgePoint(
                id=kp_id,
                name=name[:200],
                type=KnowledgeType.PROCEDURE,
                module_id=f"{path_id}-runtime-plan",
            )
        )

    if not kps:
        return []
    return [
        LearningModule(
            id=f"{path_id}-runtime-plan",
            name="Plugin runtime plan",
            order=1,
            pass_threshold=0.7,
            knowledge_points=kps,
        )
    ]


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
