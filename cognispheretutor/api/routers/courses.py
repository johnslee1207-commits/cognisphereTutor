"""Course Experience Platform API contract.

This router starts the OpenMAIC course-runtime integration as an in-process
contract surface. Durable queues and the real external adapter can replace the
in-memory backend without changing request/response shapes.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from cognispheretutor.integrations.cognisphere.course_compiler import (
    compile_minimal_course_manifest,
)
from cognispheretutor.integrations.cognisphere.course_runtime import (
    CourseRef,
    CourseRuntimeAdapter,
    HttpOpenMaicCourseRuntimeAdapter,
    InMemoryCourseRuntimeAdapter,
    build_openmaic_scene_projection,
    build_openmaic_stage_projection,
    create_course_runtime_adapter,
    load_course_runtime_contract,
    validate_course_manifest,
)
from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError
from cognispheretutor.services.config.runtime_settings import load_integrations_settings
from cognispheretutor.services.path_service import get_path_service

router = APIRouter()

_IN_MEMORY_ADAPTER = InMemoryCourseRuntimeAdapter()
_HTTP_ADAPTERS: dict[
    tuple[str, tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]], CourseRuntimeAdapter
] = {}
_JOBS: dict[str, dict[str, Any]] = {}


class CoursePlanRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=2000)
    locale: str = Field("zh-CN", min_length=2, max_length=32)
    audience_profile: str = Field("adult_beginner", min_length=1, max_length=128)
    constraints: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    idempotency_key: str | None = Field(default=None, max_length=200)


class CourseManifestRequest(BaseModel):
    manifest: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)


class CourseRevisionRequest(BaseModel):
    manifest: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(..., min_length=1, max_length=2000)
    idempotency_key: str | None = Field(default=None, max_length=200)


class CourseExportRequest(BaseModel):
    version: str = Field(..., min_length=1, max_length=128)
    profile: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)


class CoursePrepublishRequest(BaseModel):
    manifest: dict[str, Any] = Field(default_factory=dict)
    formats: list[str] = Field(default_factory=lambda: ["html", "pptx", "maic-zip"])
    classroom_url: str | None = Field(default=None, max_length=2000)
    idempotency_key: str | None = Field(default=None, max_length=200)


class CourseLaunchRequest(BaseModel):
    learner: dict[str, Any] = Field(default_factory=dict)


class CourseEventRequest(BaseModel):
    event: dict[str, Any] = Field(default_factory=dict)


def _http_error(exc: CognisphereIntegrationError) -> HTTPException:
    status = 400
    if exc.code in {"course_not_found"}:
        status = 404
    elif exc.code in {"invalid_course_manifest", "invalid_learning_scene"}:
        status = 422
    elif exc.code == "openmaic_export_route_unconfigured":
        status = 501
    elif exc.code.startswith("openmaic_"):
        status = 502
    return HTTPException(status_code=status, detail=exc.to_dict())


@router.get("/courses/runtime/status")
async def course_runtime_status() -> dict[str, Any]:
    """Return the configured course-runtime contract surface."""
    contract = load_course_runtime_contract()
    adapter = _course_runtime_adapter()
    configured_routes = getattr(adapter, "export_routes", {})
    return {
        "ok": True,
        "contract_id": contract.get("contract_id"),
        "runtime": _runtime_label(adapter),
        "external_runtime": "openmaic",
        "export_formats": contract.get("export_formats") or [],
        "export_routes_configured": sorted(configured_routes),
        "scene_kinds": contract.get("scene_kinds") or [],
        "openmaic_scene_types": contract.get("openmaic_scene_types") or [],
        "pipeline_stages": contract.get("pipeline_stages") or [],
        "event_types": contract.get("event_types") or [],
    }


@router.post("/courses/plan")
async def plan_course(request: CoursePlanRequest) -> dict[str, Any]:
    """Create an idempotent planning job with a runnable MVP course manifest."""
    payload = request.model_dump()
    job = _upsert_job(
        "course.plan",
        payload,
        idempotency_key=request.idempotency_key,
        stage="lesson_plan",
    )
    manifest = compile_minimal_course_manifest(
        topic=request.topic,
        locale=request.locale,
        audience_profile=request.audience_profile,
        constraints=request.constraints,
        source_refs=request.source_refs,
    )
    job["result"] = {
        "topic": request.topic,
        "locale": request.locale,
        "audience_profile": request.audience_profile,
        "source_refs": request.source_refs,
        "manifest": manifest,
        "validation": validate_course_manifest(manifest),
        "next": f"submit result.manifest to /api/v1/courses/{manifest['course_id']}/compile",
    }
    return job


@router.post("/courses/{course_id}/validate")
async def validate_course(course_id: str, request: CourseManifestRequest) -> dict[str, Any]:
    """Validate a DeepTutor course manifest and show OpenMAIC projections."""
    manifest = _manifest_for_course(course_id, request.manifest)
    report = validate_course_manifest(manifest)
    projections: dict[str, Any] = {}
    if report["ok"]:
        projections["stage"] = build_openmaic_stage_projection(manifest)
        projections["scenes"] = [
            build_openmaic_scene_projection(
                {
                    **scene,
                    "course_id": course_id,
                }
            )
            for lesson in manifest.get("lessons") or []
            if isinstance(lesson, dict)
            for scene in lesson.get("scenes") or []
            if isinstance(scene, dict)
        ]
    return {
        "ok": report["ok"],
        "course_id": course_id,
        "validation": report,
        "openmaic_projection": projections,
    }


@router.post("/courses/{course_id}/compile")
async def compile_course(course_id: str, request: CourseManifestRequest) -> dict[str, Any]:
    """Compile a manifest into the current course runtime adapter."""
    manifest = _manifest_for_course(course_id, request.manifest)
    job = _upsert_job(
        "course.compile",
        manifest,
        idempotency_key=request.idempotency_key,
        stage="scene_generate",
    )
    try:
        adapter = _course_runtime_adapter()
        course = await adapter.create_draft(manifest)
        scenes = []
        for lesson in manifest.get("lessons") or []:
            if not isinstance(lesson, dict):
                continue
            for scene in lesson.get("scenes") or []:
                if not isinstance(scene, dict):
                    continue
                scenes.append(
                    await adapter.upsert_scene(
                        {
                            **scene,
                            "course_id": course.course_id,
                        }
                    )
                )
    except CognisphereIntegrationError as exc:
        job["status"] = "failed"
        job["error"] = exc.to_dict()
        raise _http_error(exc) from exc
    job["status"] = "completed"
    job["result"] = {
        "course": course.__dict__,
        "scene_count": len(scenes),
        "runtime": _runtime_label(adapter),
    }
    return job


@router.post("/courses/{course_id}/publish")
async def publish_course(course_id: str, request: CourseManifestRequest) -> dict[str, Any]:
    """Publish only manifests that clear the DeepTutor quality gates."""
    manifest = _manifest_for_course(course_id, request.manifest)
    report = validate_course_manifest(manifest)
    job = _upsert_job(
        "course.publish",
        manifest,
        idempotency_key=request.idempotency_key,
        stage="publish",
    )
    if not report["ok"]:
        job["status"] = "blocked"
        job["result"] = {"validation": report}
        return job
    course = CourseRef(course_id=course_id, version=str(manifest.get("version") or ""))
    adapter = _course_runtime_adapter()
    try:
        artifact = await adapter.export(course, "maic-zip")
    except CognisphereIntegrationError as exc:
        if exc.code != "course_not_found":
            job["status"] = "failed"
            job["error"] = exc.to_dict()
            raise _http_error(exc) from exc
        course = await adapter.create_draft(manifest)
        try:
            artifact = await adapter.export(course, "maic-zip")
        except CognisphereIntegrationError as retry_exc:
            job["status"] = "failed"
            job["error"] = retry_exc.to_dict()
            raise _http_error(retry_exc) from retry_exc
    job["status"] = "completed"
    job["result"] = {
        "approval_status": manifest.get("approval_status"),
        "artifact": artifact.__dict__,
        "validation": report,
    }
    return job


@router.post("/courses/{course_id}/prepublish")
async def prepublish_course(course_id: str, request: CoursePrepublishRequest) -> dict[str, Any]:
    """Prepare a course once so learner opens only read available artifacts."""
    manifest = _manifest_for_course(course_id, request.manifest)
    report = validate_course_manifest(manifest)
    job = _upsert_job(
        "course.prepublish",
        {
            "course_id": course_id,
            "version": manifest.get("version"),
            "formats": request.formats,
            "manifest": manifest,
        },
        idempotency_key=request.idempotency_key,
        stage="publish",
    )
    if not report["ok"]:
        job["status"] = "blocked"
        job["result"] = {"validation": report}
        return job

    adapter = _course_runtime_adapter()
    try:
        course = await adapter.create_draft(manifest)
        scenes = await _upsert_manifest_scenes(adapter, course, manifest)
        classroom_publish = await _publish_openmaic_classroom(adapter, course)
        artifacts = [
            (await adapter.export(course, format)).__dict__ for format in _unique_formats(request.formats)
        ]
    except CognisphereIntegrationError as exc:
        job["status"] = "failed"
        job["error"] = exc.to_dict()
        raise _http_error(exc) from exc

    published = _published_course_record(
        manifest,
        course=course,
        adapter=adapter,
        scene_count=len(scenes),
        artifacts=artifacts,
        classroom_url=request.classroom_url or _classroom_publish_url(classroom_publish),
        validation=report,
    )
    _save_published_course(published)
    job["status"] = "completed"
    job["result"] = {
        "course": course.__dict__,
        "scene_count": len(scenes),
        "classroom_publish": classroom_publish,
        "artifacts": artifacts,
        "published": published,
        "runtime": _runtime_label(adapter),
        "validation": report,
    }
    return job


@router.post("/courses/{course_id}/exports/{format}")
async def export_course(
    course_id: str,
    format: str,
    request: CourseExportRequest,
) -> dict[str, Any]:
    """Export one course artifact format through the configured runtime adapter."""
    payload = {
        "course_id": course_id,
        "version": request.version,
        "format": format,
        "profile": request.profile,
    }
    job = _upsert_job(
        "course.export",
        payload,
        idempotency_key=request.idempotency_key,
        stage="publish",
    )
    adapter = _course_runtime_adapter()
    try:
        artifact = await adapter.export(CourseRef(course_id=course_id, version=request.version), format)
    except CognisphereIntegrationError as exc:
        job["status"] = "failed"
        job["error"] = exc.to_dict()
        raise _http_error(exc) from exc
    job["status"] = "completed"
    job["result"] = {
        "course_id": course_id,
        "version": request.version,
        "artifact": artifact.__dict__,
        "runtime": _runtime_label(adapter),
    }
    return job


@router.get("/courses/published")
async def list_published_courses() -> dict[str, Any]:
    """List courses prepared ahead of learner access."""
    return {
        "ok": True,
        "courses": _load_published_courses(),
    }


@router.post("/courses/{course_id}/launch")
async def launch_course(course_id: str, request: CourseLaunchRequest) -> dict[str, Any]:
    """Launch an anonymized learner session in the configured course runtime."""
    course = CourseRef(
        course_id=course_id,
        version=str(request.learner.get("course_version") or request.learner.get("version") or ""),
    )
    try:
        session = await _course_runtime_adapter().launch(course, request.learner)
    except CognisphereIntegrationError as exc:
        raise _http_error(exc) from exc
    return {
        "ok": True,
        "course_id": course_id,
        "session": session.__dict__,
    }


@router.post("/courses/{course_id}/events")
async def record_course_event(course_id: str, request: CourseEventRequest) -> dict[str, Any]:
    """Record a traceable learning event emitted by the course runtime."""
    event = _event_for_course(course_id, request.event)
    try:
        result = await _course_runtime_adapter().record_event(event)
    except CognisphereIntegrationError as exc:
        raise _http_error(exc) from exc
    return {
        "ok": True,
        "course_id": course_id,
        "result": result,
    }


@router.post("/courses/{course_id}/revisions")
async def revise_course(course_id: str, request: CourseRevisionRequest) -> dict[str, Any]:
    """Record an immutable revision request without overwriting the course."""
    manifest = _manifest_for_course(course_id, request.manifest)
    job = _upsert_job(
        "course.revision",
        {"manifest": manifest, "reason": request.reason},
        idempotency_key=request.idempotency_key,
        stage="observe_and_improve",
    )
    job["result"] = {
        "course_id": course_id,
        "version": manifest.get("version"),
        "reason": request.reason,
        "next": "compile the revised manifest as a new immutable version",
    }
    return job


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    """Return a course generation job envelope."""
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"ok": False, "code": "job_not_found"})
    return job


def _course_runtime_adapter() -> CourseRuntimeAdapter:
    settings = load_integrations_settings()
    base_url = str(settings.get("openmaic_course_runtime_base_url") or "").strip()
    if not base_url:
        return _IN_MEMORY_ADAPTER
    headers = settings.get("openmaic_course_runtime_headers") or {}
    export_routes = settings.get("openmaic_course_export_routes") or {}
    key = (
        base_url,
        tuple(sorted((str(name), str(value)) for name, value in headers.items())),
        tuple(sorted((str(format), str(route)) for format, route in export_routes.items())),
    )
    if key not in _HTTP_ADAPTERS:
        _HTTP_ADAPTERS[key] = create_course_runtime_adapter(
            base_url=base_url,
            headers=headers,
            export_routes=export_routes,
        )
    return _HTTP_ADAPTERS[key]


async def _upsert_manifest_scenes(
    adapter: CourseRuntimeAdapter,
    course: CourseRef,
    manifest: dict[str, Any],
) -> list[Any]:
    scenes = []
    for lesson in manifest.get("lessons") or []:
        if not isinstance(lesson, dict):
            continue
        for scene in lesson.get("scenes") or []:
            if not isinstance(scene, dict):
                continue
            scenes.append(await adapter.upsert_scene({**scene, "course_id": course.course_id}))
    return scenes


def _runtime_label(adapter: CourseRuntimeAdapter) -> str:
    if isinstance(adapter, HttpOpenMaicCourseRuntimeAdapter):
        return "openmaic_http_adapter"
    return "in_memory_contract_adapter"


async def _publish_openmaic_classroom(
    adapter: CourseRuntimeAdapter,
    course: CourseRef,
) -> dict[str, Any] | None:
    if isinstance(adapter, HttpOpenMaicCourseRuntimeAdapter):
        return await adapter.publish_classroom(course)
    return None


def _classroom_publish_url(classroom_publish: dict[str, Any] | None) -> str | None:
    if not classroom_publish:
        return None
    value = classroom_publish.get("classroom_url")
    return str(value) if value else None


def _manifest_for_course(course_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    out = dict(manifest)
    out.setdefault("course_id", course_id)
    if str(out.get("course_id") or "") != course_id:
        raise HTTPException(
            status_code=422,
            detail={
                "ok": False,
                "code": "course_id_mismatch",
                "message": "path course_id must match manifest.course_id",
            },
        )
    return out


def _unique_formats(formats: list[str]) -> list[str]:
    allowed = set(load_course_runtime_contract().get("export_formats") or [])
    out: list[str] = []
    for format in formats:
        value = str(format).strip()
        if not value:
            continue
        if value not in allowed:
            raise HTTPException(
                status_code=422,
                detail={
                    "ok": False,
                    "code": "unsupported_course_export_format",
                    "message": f"unsupported export format: {value}",
                    "allowed": sorted(allowed),
                },
            )
        if value not in out:
            out.append(value)
    return out


def _catalog_path() -> Path:
    return get_path_service().user_data_dir / "course_catalog" / "published_courses.json"


def _load_published_courses() -> list[dict[str, Any]]:
    path = _catalog_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    courses = payload.get("courses") if isinstance(payload, dict) else None
    return courses if isinstance(courses, list) else []


def _save_published_course(record: dict[str, Any]) -> None:
    path = _catalog_path()
    courses = [
        item
        for item in _load_published_courses()
        if not (
            isinstance(item, dict)
            and item.get("course_id") == record["course_id"]
            and item.get("version") == record["version"]
        )
    ]
    courses.append(record)
    courses.sort(key=lambda item: str(item.get("published_at") or ""), reverse=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "courses": courses}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _published_course_record(
    manifest: dict[str, Any],
    *,
    course: CourseRef,
    adapter: CourseRuntimeAdapter,
    scene_count: int,
    artifacts: list[dict[str, Any]],
    classroom_url: str | None,
    validation: dict[str, Any],
) -> dict[str, Any]:
    title = str(manifest.get("title") or manifest.get("name") or course.course_id)
    return {
        "course_id": course.course_id,
        "version": course.version,
        "title": title,
        "status": "available",
        "runtime": _runtime_label(adapter),
        "classroom_url": classroom_url or _default_classroom_url(course.course_id, adapter),
        "scene_count": scene_count,
        "artifact_formats": [artifact.get("format") for artifact in artifacts],
        "artifacts": artifacts,
        "validation_ok": bool(validation.get("ok")),
        "published_at": datetime.now(UTC).isoformat(),
    }


def _default_classroom_url(course_id: str, adapter: CourseRuntimeAdapter) -> str | None:
    if isinstance(adapter, HttpOpenMaicCourseRuntimeAdapter):
        base = adapter.base_url
        marker = "/api/persistence"
        origin = base[: -len(marker)] if base.endswith(marker) else base
        return f"{origin.rstrip('/')}/classroom/{course_id}"
    return None


def _event_for_course(course_id: str, event: dict[str, Any]) -> dict[str, Any]:
    out = dict(event)
    out.setdefault("course_id", course_id)
    out.setdefault("server_time", datetime.now(UTC).isoformat().replace("+00:00", "Z"))
    if str(out.get("course_id") or "") != course_id:
        raise HTTPException(
            status_code=422,
            detail={
                "ok": False,
                "code": "course_id_mismatch",
                "message": "path course_id must match event.course_id",
            },
        )
    return out


def _upsert_job(
    operation: str,
    payload: dict[str, Any],
    *,
    idempotency_key: str | None,
    stage: str,
) -> dict[str, Any]:
    job_id = _job_id(operation, payload, idempotency_key)
    if job_id in _JOBS:
        return _JOBS[job_id]
    now = datetime.now(UTC).isoformat()
    job = {
        "ok": True,
        "job_id": job_id,
        "operation": operation,
        "status": "accepted",
        "stage": stage,
        "created_at": now,
        "updated_at": now,
        "idempotent": bool(idempotency_key),
    }
    _JOBS[job_id] = job
    return job


def _job_id(operation: str, payload: dict[str, Any], idempotency_key: str | None) -> str:
    seed = idempotency_key or json.dumps(
        {"operation": operation, "payload": payload},
        ensure_ascii=True,
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"{operation.replace('.', '-')}-{digest}"
