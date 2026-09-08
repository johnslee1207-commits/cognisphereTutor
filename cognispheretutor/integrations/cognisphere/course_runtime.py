"""Course runtime contract and adapters for external course experiences.

DeepTutor owns objectives, evidence, mastery, and quality gates. External
runtimes such as OpenMAIC own course experience rendering behind this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
import hashlib
from http.cookies import SimpleCookie
import json
from typing import Any, Awaitable, Callable, Mapping, Protocol, runtime_checkable
from urllib.parse import quote, urlsplit

import httpx

from cognispheretutor.integrations.cognisphere._contract import manifests_dir
from cognispheretutor.integrations.cognisphere.course_export import export_course_artifact
from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError


@dataclass(frozen=True)
class CourseRef:
    """Opaque course reference returned by a runtime adapter."""

    course_id: str
    version: str
    status: str = "draft"


@dataclass(frozen=True)
class SceneRef:
    """Opaque scene reference returned by a runtime adapter."""

    course_id: str
    scene_id: str
    kind: str


@dataclass(frozen=True)
class ArtifactRef:
    """Opaque artifact reference returned by render/export operations."""

    artifact_id: str
    course_id: str
    artifact_type: str
    format: str
    uri: str | None = None
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class SessionRef:
    """Opaque launch session reference for a learner."""

    session_id: str
    course_id: str
    learner_hash: str


@runtime_checkable
class CourseRuntimeAdapter(Protocol):
    """Adapter boundary matching the OpenMAIC-facing course runtime contract."""

    async def create_draft(self, manifest: Mapping[str, Any]) -> CourseRef:
        """Create a draft course from a DeepTutor course manifest."""

    async def upsert_scene(self, scene: Mapping[str, Any]) -> SceneRef:
        """Create or update a scene without exposing runtime-internal storage."""

    async def render(
        self,
        course: CourseRef,
        profile: Mapping[str, Any],
    ) -> ArtifactRef:
        """Render a course artifact for a runtime profile."""

    async def launch(
        self,
        course: CourseRef,
        learner: Mapping[str, Any],
    ) -> SessionRef:
        """Launch a learner session using an anonymized learner identity."""

    async def export(self, course: CourseRef, format: str) -> ArtifactRef:
        """Export an immutable course artifact."""

    async def record_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """Record a DeepTutor learning event emitted by the course experience."""


@lru_cache(maxsize=1)
def load_course_runtime_contract() -> dict[str, Any]:
    """Load the course runtime contract from manifests, not code constants."""
    path = manifests_dir() / "course_runtime_contract.json"
    return json.loads(path.read_text(encoding="utf-8"))


def validate_course_manifest(
    manifest: Mapping[str, Any],
    *,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the DeepTutor-owned part of a course package."""
    cfg = contract or load_course_runtime_contract()
    issues: list[str] = []
    warnings: list[str] = []
    gates: dict[str, dict[str, Any]] = {}

    required = _as_str_list(cfg.get("required_manifest_fields"))
    for field in required:
        if field not in manifest:
            issues.append(f"missing_manifest_field:{field}")

    if "lessons" in manifest and not isinstance(manifest.get("lessons"), list):
        issues.append("invalid_manifest_field:lessons")

    objectives = _as_mapping_list(manifest.get("learning_objectives"))
    objective_issues = _validate_learning_objectives(objectives, cfg)
    issues.extend(objective_issues)

    gates["G0 Source"] = _gate(
        "G0 Source",
        _validate_source_gate(manifest, objectives),
    )
    gates["G1 Objective"] = _gate(
        "G1 Objective",
        _validate_objective_gate(manifest, objectives, cfg),
    )
    gates["G4 Lab"] = _gate(
        "G4 Lab",
        _validate_lab_gate(manifest, objectives),
    )
    gates["G3 Assessment"] = _gate(
        "G3 Assessment",
        _validate_assessment_gate(manifest, objectives),
    )
    gates["G6 Security"] = _gate(
        "G6 Security",
        _validate_security_gate(manifest),
    )
    gates["G8 Reproducibility"] = _gate(
        "G8 Reproducibility",
        _validate_reproducibility_gate(manifest),
    )

    for gate in gates.values():
        issues.extend(gate["issues"])

    if not objectives:
        warnings.append("missing_learning_objectives")

    return {
        "ok": not issues,
        "contract_id": cfg.get("contract_id"),
        "issues": _dedupe(issues),
        "warnings": _dedupe(warnings),
        "gates": gates,
    }


def build_openmaic_stage_projection(
    manifest: Mapping[str, Any],
    *,
    now_ms: int = 0,
) -> dict[str, Any]:
    """Project a DeepTutor course manifest into OpenMAIC's Stage skeleton."""
    report = validate_course_manifest(manifest)
    if not report["ok"]:
        raise CognisphereIntegrationError(
            "invalid_course_manifest",
            message="course manifest failed validation",
            details=report,
        )
    course_id = str(manifest["course_id"])
    return {
        "id": course_id,
        "name": str(manifest.get("title") or course_id),
        "description": str(manifest.get("description") or ""),
        "createdAt": now_ms,
        "updatedAt": now_ms,
        "languageDirective": str(manifest.get("locale") or ""),
        "style": "deeptutor-evidence-driven",
    }


def build_openmaic_scene_projection(
    scene: Mapping[str, Any],
    *,
    contract: Mapping[str, Any] | None = None,
    now_ms: int = 0,
) -> dict[str, Any]:
    """Project a DeepTutor learning scene into OpenMAIC's Scene skeleton."""
    cfg = contract or load_course_runtime_contract()
    kind = _required_str(scene, "kind", "invalid_learning_scene")
    course_id = _required_str(scene, "course_id", "invalid_learning_scene")
    scene_id = _required_str(scene, "scene_id", "invalid_learning_scene")
    scene_type = _openmaic_scene_type(kind, scene, cfg)
    title = str(scene.get("title") or scene_id)
    order = int(scene.get("order") or 0)
    return {
        "id": scene_id,
        "stageId": course_id,
        "title": title,
        "order": order,
        "type": scene_type,
        "content": _scene_content(scene_type, scene, title),
        "createdAt": now_ms,
        "updatedAt": now_ms,
        "metadata": {
            "deeptutor_learning_kind": kind,
            "objective_ids": _as_str_list(scene.get("objective_ids")),
            "source_refs": _as_str_list(scene.get("source_refs")),
            "lab_refs": _as_str_list(scene.get("lab_refs")),
        },
    }


def validate_learning_event(
    event: Mapping[str, Any],
    *,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a simplified xAPI-style learning event envelope."""
    cfg = contract or load_course_runtime_contract()
    issues: list[str] = []

    for field in _as_str_list(cfg.get("required_learning_event_fields")):
        if field not in event:
            issues.append(f"missing_learning_event_field:{field}")

    event_type = str(event.get("event_type") or "")
    if event_type and event_type not in set(_as_str_list(cfg.get("event_types"))):
        issues.append(f"unsupported_learning_event_type:{event_type}")

    if not _as_str_list(event.get("objective_ids")):
        issues.append("invalid_learning_event_field:objective_ids")

    learner_hash = str(event.get("learner_hash") or "")
    if learner_hash and len(learner_hash) < 16:
        issues.append("invalid_learning_event_field:learner_hash")

    for field in ("client_time", "server_time"):
        value = str(event.get(field) or "")
        if value and not _looks_like_iso_timestamp(value):
            issues.append(f"invalid_learning_event_field:{field}")

    return {
        "ok": not issues,
        "contract_id": cfg.get("contract_id"),
        "issues": _dedupe(issues),
    }


class InMemoryCourseRuntimeAdapter:
    """Small test adapter for the external course runtime boundary."""

    def __init__(self, *, contract: Mapping[str, Any] | None = None) -> None:
        self.contract = dict(contract or load_course_runtime_contract())
        self.courses: dict[str, dict[str, Any]] = {}
        self.scenes: dict[str, dict[str, Any]] = {}
        self.openmaic_stages: dict[str, dict[str, Any]] = {}
        self.openmaic_scenes: dict[str, dict[str, Any]] = {}
        self.artifacts: dict[str, ArtifactRef] = {}
        self.sessions: dict[str, SessionRef] = {}
        self.events: list[dict[str, Any]] = []

    async def create_draft(self, manifest: Mapping[str, Any]) -> CourseRef:
        report = validate_course_manifest(manifest, contract=self.contract)
        if not report["ok"]:
            raise CognisphereIntegrationError(
                "invalid_course_manifest",
                message="course manifest failed validation",
                details=report,
            )
        ref = CourseRef(
            course_id=str(manifest["course_id"]),
            version=str(manifest["version"]),
        )
        self.courses[_course_key(ref)] = dict(manifest)
        self.openmaic_stages[ref.course_id] = build_openmaic_stage_projection(
            manifest,
            now_ms=0,
        )
        return ref

    async def upsert_scene(self, scene: Mapping[str, Any]) -> SceneRef:
        kind = str(scene.get("kind") or "").strip()
        allowed = set(_as_str_list(self.contract.get("scene_kinds")))
        if kind not in allowed:
            raise CognisphereIntegrationError(
                "invalid_learning_scene",
                message=f"unsupported scene kind: {kind}",
                details={"allowed": sorted(allowed)},
            )
        course_id = _required_str(scene, "course_id", "invalid_learning_scene")
        scene_id = _required_str(scene, "scene_id", "invalid_learning_scene")
        ref = SceneRef(course_id=course_id, scene_id=scene_id, kind=kind)
        self.scenes[f"{course_id}:{scene_id}"] = dict(scene)
        self.openmaic_scenes[f"{course_id}:{scene_id}"] = build_openmaic_scene_projection(
            scene,
            contract=self.contract,
            now_ms=0,
        )
        return ref

    async def render(
        self,
        course: CourseRef,
        profile: Mapping[str, Any],
    ) -> ArtifactRef:
        self._require_course(course)
        format = str(profile.get("format") or "html").strip()
        return self._artifact(course, "render", format)

    async def launch(
        self,
        course: CourseRef,
        learner: Mapping[str, Any],
    ) -> SessionRef:
        self._require_course(course)
        learner_id = _required_str(learner, "learner_id", "invalid_learner_context")
        learner_hash = _stable_hash(learner_id)
        session = SessionRef(
            session_id=_stable_hash(f"{course.course_id}:{course.version}:{learner_hash}")[:16],
            course_id=course.course_id,
            learner_hash=learner_hash,
        )
        self.sessions[session.session_id] = session
        return session

    async def export(self, course: CourseRef, format: str) -> ArtifactRef:
        self._require_course(course)
        allowed = set(_as_str_list(self.contract.get("export_formats")))
        if format not in allowed:
            raise CognisphereIntegrationError(
                "unsupported_course_export_format",
                message=f"unsupported export format: {format}",
                details={"allowed": sorted(allowed)},
            )
        return self._artifact(course, "export", format)

    async def record_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        report = validate_learning_event(event, contract=self.contract)
        if not report["ok"]:
            raise CognisphereIntegrationError(
                "invalid_learning_event",
                message="learning event failed validation",
                details=report,
            )
        recorded = dict(event)
        self.events.append(recorded)
        return {
            "ok": True,
            "event_count": len(self.events),
            "event_type": recorded["event_type"],
            "trace_id": recorded["trace_id"],
        }

    def _require_course(self, course: CourseRef) -> None:
        if _course_key(course) not in self.courses:
            raise CognisphereIntegrationError(
                "course_not_found",
                message=f"course not found: {course.course_id}@{course.version}",
            )

    def _artifact(self, course: CourseRef, artifact_type: str, format: str) -> ArtifactRef:
        artifact_id = _stable_hash(f"{artifact_type}:{course.course_id}:{course.version}:{format}")[
            :16
        ]
        stage = self.openmaic_stages.get(course.course_id) or {
            "id": course.course_id,
            "name": course.course_id,
            "description": "",
        }
        scenes = [
            scene
            for key, scene in sorted(self.openmaic_scenes.items())
            if key.startswith(f"{course.course_id}:")
        ]
        exported = export_course_artifact(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            format=format,
            course_id=course.course_id,
            version=course.version,
            stage=stage,
            scenes=scenes,
        )
        ref = ArtifactRef(
            artifact_id=artifact_id,
            course_id=course.course_id,
            artifact_type=artifact_type,
            format=format,
            uri=str(exported.path),
            metadata={
                "content_type": exported.content_type,
                "size_bytes": exported.size_bytes,
            },
        )
        self.artifacts[artifact_id] = ref
        return ref


def _validate_learning_objectives(
    objectives: list[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> list[str]:
    issues: list[str] = []
    required = _as_str_list(contract.get("learning_objective_required_fields"))
    for objective in objectives:
        objective_id = str(objective.get("objective_id") or "<unknown>")
        for field in required:
            if field not in objective:
                issues.append(f"missing_objective_field:{objective_id}:{field}")
        statement = str(objective.get("statement") or "").strip()
        if statement and _starts_with_weak_verb(statement, contract):
            issues.append(f"weak_objective_verb:{objective_id}")
        threshold = objective.get("mastery_threshold")
        if threshold is not None and not _valid_threshold(threshold):
            issues.append(f"invalid_mastery_threshold:{objective_id}")
    return issues


class HttpOpenMaicCourseRuntimeAdapter:
    """HTTP adapter for OpenMAIC storage/runtime plus optional export services."""

    def __init__(
        self,
        base_url: str,
        *,
        headers: Mapping[str, str]
        | Callable[[str, str], Mapping[str, str] | Awaitable[Mapping[str, str]]]
        | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
        contract: Mapping[str, Any] | None = None,
        export_routes: Mapping[str, str] | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("OpenMAIC base_url must be non-empty")
        self.base_url = base_url.rstrip("/")
        self.headers = headers
        self.client = client
        self.timeout = timeout
        self.contract = dict(contract or load_course_runtime_contract())
        self.export_routes = dict(export_routes or {})
        self._cookies = httpx.Cookies()
        self._classroom_documents: dict[str, dict[str, Any]] = {}
        self._classroom_file_fallback = False

    async def create_draft(self, manifest: Mapping[str, Any]) -> CourseRef:
        report = validate_course_manifest(manifest, contract=self.contract)
        if not report["ok"]:
            raise CognisphereIntegrationError(
                "invalid_course_manifest",
                message="course manifest failed validation",
                details=report,
            )
        course_id = str(manifest["course_id"])
        version = str(manifest["version"])
        document = {
            "stage": build_openmaic_stage_projection(manifest),
            "scenes": _manifest_openmaic_scenes(manifest, self.contract),
            "outline": {
                "source": "deeptutor",
                "course_id": course_id,
                "course_version": version,
                "competency_graph_version": manifest.get("competency_graph_version"),
                "source_pack_version": manifest.get("source_pack_version"),
            },
        }
        try:
            await self._request("PUT", f"/documents/{_segment(course_id)}", document)
        except CognisphereIntegrationError as exc:
            if not _is_openmaic_storage_unavailable(exc):
                raise
            self._classroom_file_fallback = True
            await self._save_classroom_document(course_id, document)
        else:
            self._classroom_documents[course_id] = document
        return CourseRef(course_id=course_id, version=version)

    async def upsert_scene(self, scene: Mapping[str, Any]) -> SceneRef:
        course_id = _required_str(scene, "course_id", "invalid_learning_scene")
        scene_id = _required_str(scene, "scene_id", "invalid_learning_scene")
        kind = _required_str(scene, "kind", "invalid_learning_scene")
        projected = build_openmaic_scene_projection(scene, contract=self.contract)
        if self._classroom_file_fallback:
            document = self._classroom_documents.get(course_id)
            if document is not None:
                scenes = [
                    item
                    for item in _as_mapping_list(document.get("scenes"))
                    if str(item.get("id") or "") != scene_id
                ]
                scenes.append(projected)
                scenes.sort(key=lambda item: int(item.get("order") or 0))
                document["scenes"] = scenes
                await self._save_classroom_document(course_id, document)
                return SceneRef(course_id=course_id, scene_id=scene_id, kind=kind)
        try:
            await self._request(
                "PUT",
                f"/documents/{_segment(course_id)}/scenes/{_segment(scene_id)}",
                projected,
            )
        except CognisphereIntegrationError as exc:
            if not _is_openmaic_storage_unavailable(exc):
                raise
            self._classroom_file_fallback = True
            document = self._classroom_documents.get(course_id)
            if document is None:
                raise
            scenes = [
                item
                for item in _as_mapping_list(document.get("scenes"))
                if str(item.get("id") or "") != scene_id
            ]
            scenes.append(projected)
            scenes.sort(key=lambda item: int(item.get("order") or 0))
            document["scenes"] = scenes
            await self._save_classroom_document(course_id, document)
        return SceneRef(course_id=course_id, scene_id=scene_id, kind=kind)

    async def render(
        self,
        course: CourseRef,
        profile: Mapping[str, Any],
    ) -> ArtifactRef:
        format = str(profile.get("format") or "html").strip()
        return await self._export_artifact(course, format, profile=profile, artifact_type="render")

    async def launch(
        self,
        course: CourseRef,
        learner: Mapping[str, Any],
    ) -> SessionRef:
        learner_id = _required_str(learner, "learner_id", "invalid_learner_context")
        learner_hash = _stable_hash(learner_id)
        now = str(learner.get("server_time") or learner.get("client_time") or _utc_now())
        session_id = str(
            learner.get("session_id")
            or _stable_hash(f"{course.course_id}:{course.version}:{learner_hash}")[:16]
        )
        session = {
            "id": session_id,
            "kind": str(learner.get("kind") or "playback"),
            "stageId": course.course_id,
            "learnerKey": learner_hash,
            "status": "active",
            "createdAt": now,
            "updatedAt": now,
        }
        try:
            payload = await self._request(
                "POST",
                "/runtime/sessions",
                session,
                extra_headers={"x-learner-key": learner_hash},
            )
        except CognisphereIntegrationError as exc:
            if not _is_openmaic_storage_unavailable(exc):
                raise
            payload = session
        returned = payload if isinstance(payload, Mapping) else session
        return SessionRef(
            session_id=str(returned.get("id") or session_id),
            course_id=course.course_id,
            learner_hash=learner_hash,
        )

    async def export(self, course: CourseRef, format: str) -> ArtifactRef:
        return await self._export_artifact(course, format, artifact_type="export")

    async def publish_classroom(self, course: CourseRef) -> dict[str, Any]:
        """Copy a persisted document into OpenMAIC's classroom playback store."""
        if self._classroom_file_fallback and course.course_id in self._classroom_documents:
            payload = await self._save_classroom_document(
                course.course_id,
                self._classroom_documents[course.course_id],
            )
            classroom_url = payload.get("url") if isinstance(payload, Mapping) else None
            return {
                "ok": True,
                "course_id": course.course_id,
                "classroom_url": str(classroom_url or f"{_openmaic_origin(self.base_url)}/classroom/{course.course_id}"),
                "response": dict(payload) if isinstance(payload, Mapping) else payload,
                "storage": "openmaic_classroom_file",
            }
        document = await self._request("GET", f"/documents/{_segment(course.course_id)}")
        if not isinstance(document, Mapping):
            raise CognisphereIntegrationError(
                "openmaic_malformed_response",
                message="OpenMAIC document response was not an object",
                details={"course_id": course.course_id},
            )
        stage = document.get("stage")
        scenes = document.get("scenes")
        if not isinstance(stage, Mapping) or not isinstance(scenes, list):
            raise CognisphereIntegrationError(
                "openmaic_malformed_response",
                message="OpenMAIC document response missing stage or scenes",
                details={"course_id": course.course_id},
            )
        payload = await self._request(
            "POST",
            f"{_openmaic_origin(self.base_url)}/api/classroom",
            {"stage": dict(stage), "scenes": scenes},
        )
        classroom_url = None
        if isinstance(payload, Mapping):
            classroom_url = payload.get("url")
        return {
            "ok": True,
            "course_id": course.course_id,
            "classroom_url": str(classroom_url or f"{_openmaic_origin(self.base_url)}/classroom/{course.course_id}"),
            "response": dict(payload) if isinstance(payload, Mapping) else payload,
            "storage": "openmaic_persistence",
        }

    async def _export_artifact(
        self,
        course: CourseRef,
        format: str,
        *,
        artifact_type: str,
        profile: Mapping[str, Any] | None = None,
    ) -> ArtifactRef:
        allowed = set(_as_str_list(self.contract.get("export_formats")))
        if format not in allowed:
            raise CognisphereIntegrationError(
                "unsupported_course_export_format",
                message=f"unsupported export format: {format}",
                details={"allowed": sorted(allowed)},
            )
        route = self.export_routes.get(format)
        if not route:
            raise CognisphereIntegrationError(
                "openmaic_export_route_unconfigured",
                message=f"OpenMAIC export route is not configured for format: {format}",
                details={
                    "format": format,
                    "allowed": sorted(allowed),
                    "configured_formats": sorted(self.export_routes),
                },
            )
        request = {
            "stageId": course.course_id,
            "courseId": course.course_id,
            "version": course.version,
            "format": format,
            "profile": dict(profile or {}),
        }
        payload = await self._request("POST", route, request, expect_json=False)
        return _artifact_from_export_response(
            course,
            format,
            artifact_type=artifact_type,
            route=route,
            payload=payload,
        )

    async def record_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        report = validate_learning_event(event, contract=self.contract)
        if not report["ok"]:
            raise CognisphereIntegrationError(
                "invalid_learning_event",
                message="learning event failed validation",
                details=report,
            )
        session_id = _required_str(event, "session_id", "invalid_learning_event")
        record_id = str(event.get("event_id") or _stable_hash(str(event))[:16])
        record = {
            "id": record_id,
            "sessionId": session_id,
            "createdAt": str(event["server_time"]),
            "payload": {
                "source": "deeptutor",
                "event": dict(event),
            },
        }
        scene_id = str(event.get("scene_id") or "").strip()
        if scene_id:
            record["sceneId"] = scene_id
        sub_anchor = str(event.get("sub_anchor") or event.get("trace_id") or "").strip()
        if sub_anchor:
            record["subAnchor"] = sub_anchor
        try:
            payload = await self._request(
                "POST",
                f"/runtime/sessions/{_segment(session_id)}/records",
                record,
                extra_headers={"x-learner-key": str(event["learner_hash"])},
            )
        except CognisphereIntegrationError as exc:
            if not _is_openmaic_storage_unavailable(exc):
                raise
            payload = {"id": record_id, "status": "accepted_without_runtime_store"}
        return {
            "ok": True,
            "event_type": event["event_type"],
            "trace_id": event["trace_id"],
            "runtime_record": payload,
        }

    async def _save_classroom_document(
        self,
        course_id: str,
        document: Mapping[str, Any],
    ) -> Any:
        stage = document.get("stage")
        scenes = document.get("scenes")
        if not isinstance(stage, Mapping) or not isinstance(scenes, list):
            raise CognisphereIntegrationError(
                "openmaic_malformed_response",
                message="OpenMAIC classroom fallback document missing stage or scenes",
                details={"course_id": course_id},
            )
        payload = await self._request(
            "POST",
            f"{_openmaic_origin(self.base_url)}/api/classroom",
            {"stage": dict(stage), "scenes": scenes},
        )
        self._classroom_documents[course_id] = {
            **dict(document),
            "stage": dict(stage),
            "scenes": scenes,
        }
        return payload

    async def _request(
        self,
        method: str,
        path: str,
        body: Any | None = None,
        *,
        expect_json: bool = True,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Any:
        headers = await self._headers(method, path)
        headers.update(extra_headers or {})
        client = self.client or httpx.AsyncClient(timeout=self.timeout)
        close_client = self.client is None
        try:
            response = await client.request(
                method,
                _join_url(self.base_url, path),
                headers=headers,
                json=body,
                cookies=self._cookies,
            )
            self._cookies.extract_cookies(response)
            self._remember_local_http_cookies(response)
        finally:
            if close_client:
                await client.aclose()
        if response.status_code == 204:
            return None
        if response.is_error:
            raise _openmaic_http_error(response)
        if not expect_json:
            return _response_payload(response)
        try:
            return response.json()
        except ValueError as exc:
            raise CognisphereIntegrationError(
                "openmaic_malformed_response",
                message="OpenMAIC response was not valid JSON",
                details={"status_code": response.status_code, "path": path},
            ) from exc

    async def _headers(self, method: str, path: str) -> dict[str, str]:
        if self.headers is None:
            return {}
        if isinstance(self.headers, Mapping):
            return dict(self.headers)
        result = self.headers(method, path)
        if hasattr(result, "__await__"):
            result = await result  # type: ignore[assignment]
        return dict(result)

    def _remember_local_http_cookies(self, response: httpx.Response) -> None:
        if urlsplit(self.base_url).scheme != "http":
            return
        origin = urlsplit(str(response.url))
        if origin.scheme != "http":
            return
        for header in response.headers.get_list("set-cookie"):
            cookie = SimpleCookie()
            cookie.load(header)
            for name, morsel in cookie.items():
                self._cookies.set(
                    name,
                    morsel.value,
                    domain=origin.hostname or "",
                    path=morsel["path"] or "/",
                )


def create_course_runtime_adapter(
    *,
    base_url: str | None = None,
    headers: Mapping[str, str]
    | Callable[[str, str], Mapping[str, str] | Awaitable[Mapping[str, str]]]
    | None = None,
    client: httpx.AsyncClient | None = None,
    timeout: float = 30.0,
    contract: Mapping[str, Any] | None = None,
    export_routes: Mapping[str, str] | None = None,
) -> CourseRuntimeAdapter:
    """Create the configured course runtime adapter.

    Empty ``base_url`` keeps the local in-memory adapter. A non-empty URL binds
    to OpenMAIC's HTTP DocumentStore and RuntimeStore contracts.
    """
    if base_url and base_url.strip():
        return HttpOpenMaicCourseRuntimeAdapter(
            base_url,
            headers=headers,
            client=client,
            timeout=timeout,
            contract=contract,
            export_routes=export_routes,
        )
    return InMemoryCourseRuntimeAdapter(contract=contract)


def _validate_source_gate(
    manifest: Mapping[str, Any],
    objectives: list[Mapping[str, Any]],
) -> list[str]:
    issues: list[str] = []
    high_risk_claims = _as_mapping_list(manifest.get("high_risk_claims"))
    for claim in high_risk_claims:
        claim_id = str(claim.get("claim_id") or "<unknown>")
        levels = set(_as_str_list(claim.get("source_levels")))
        if not levels.intersection({"S0", "S1"}):
            issues.append(f"gate_failed:G0 Source:{claim_id}")
    for objective in objectives:
        if not _as_str_list(objective.get("source_refs")):
            issues.append(
                f"gate_failed:G0 Source:{objective.get('objective_id') or '<unknown>'}"
            )
    return issues


def _validate_objective_gate(
    manifest: Mapping[str, Any],
    objectives: list[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> list[str]:
    issues: list[str] = []
    objective_ids = {str(item.get("objective_id")) for item in objectives if item.get("objective_id")}
    scene_kinds = set(_as_str_list(contract.get("scene_kinds")))
    for lesson in _as_mapping_list(manifest.get("lessons")):
        for scene in _as_mapping_list(lesson.get("scenes")):
            scene_id = str(scene.get("scene_id") or "<unknown>")
            kind = str(scene.get("kind") or "")
            if kind not in scene_kinds:
                issues.append(f"gate_failed:G1 Objective:{scene_id}:invalid_scene_kind")
            refs = set(_as_str_list(scene.get("objective_ids")))
            if not refs:
                issues.append(f"gate_failed:G1 Objective:{scene_id}:missing_objective_ids")
            elif objective_ids and not refs.issubset(objective_ids):
                issues.append(f"gate_failed:G1 Objective:{scene_id}:unknown_objective_id")
    return issues


def _validate_lab_gate(
    manifest: Mapping[str, Any],
    objectives: list[Mapping[str, Any]],
) -> list[str]:
    issues: list[str] = []
    lab_objective_ids: set[str] = set()
    for lesson in _as_mapping_list(manifest.get("lessons")):
        for scene in _as_mapping_list(lesson.get("scenes")):
            if scene.get("kind") == "execute_lab":
                lab_objective_ids.update(_as_str_list(scene.get("objective_ids")))
    for objective in objectives:
        objective_id = str(objective.get("objective_id") or "<unknown>")
        requires_lab = bool(objective.get("requires_lab")) or objective_id in lab_objective_ids
        if requires_lab and not _as_str_list(objective.get("lab_refs")):
            issues.append(f"gate_failed:G4 Lab:{objective_id}")
    return issues


def _validate_assessment_gate(
    manifest: Mapping[str, Any],
    objectives: list[Mapping[str, Any]],
) -> list[str]:
    issues: list[str] = []
    declared = {
        str(item.get("assessment_id"))
        for item in _as_mapping_list(manifest.get("assessments"))
        if item.get("assessment_id")
    }
    for objective in objectives:
        objective_id = str(objective.get("objective_id") or "<unknown>")
        for assessment_ref in _as_str_list(objective.get("assessment_refs")):
            if declared and assessment_ref not in declared:
                issues.append(f"gate_failed:G3 Assessment:{objective_id}:unknown_assessment_ref")
    for lesson in _as_mapping_list(manifest.get("lessons")):
        for scene in _as_mapping_list(lesson.get("scenes")):
            kind = str(scene.get("kind") or "")
            runtime_type = str(scene.get("runtime_scene_type") or "")
            if kind in {"diagnose", "reflect_evidence"} or runtime_type == "quiz":
                if not _as_str_list(scene.get("assessment_refs")):
                    issues.append(
                        f"gate_failed:G3 Assessment:{scene.get('scene_id') or '<unknown>'}"
                    )
    return issues


def _validate_security_gate(manifest: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    for lesson in _as_mapping_list(manifest.get("lessons")):
        for scene in _as_mapping_list(lesson.get("scenes")):
            kind = str(scene.get("kind") or "")
            runtime_type = str(scene.get("runtime_scene_type") or "")
            content = scene.get("openmaic_content") or scene.get("content")
            content_type = str(content.get("type") if isinstance(content, Mapping) else "")
            if kind == "observe" or runtime_type == "interactive" or content_type == "interactive":
                if not str(scene.get("sandbox_profile") or "").strip():
                    issues.append(f"gate_failed:G6 Security:{scene.get('scene_id') or '<unknown>'}")
    return issues


def _validate_reproducibility_gate(manifest: Mapping[str, Any]) -> list[str]:
    if (
        manifest.get("course_id")
        and manifest.get("version")
        and (manifest.get("generation_inputs_ref") or manifest.get("source_pack_version"))
    ):
        return []
    return ["gate_failed:G8 Reproducibility:missing_generation_inputs"]


def _manifest_openmaic_scenes(
    manifest: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    course_id = str(manifest["course_id"])
    for lesson in _as_mapping_list(manifest.get("lessons")):
        for scene in _as_mapping_list(lesson.get("scenes")):
            scenes.append(
                build_openmaic_scene_projection(
                    {**scene, "course_id": course_id},
                    contract=contract,
                )
            )
    return scenes


def _openmaic_scene_type(
    kind: str,
    scene: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> str:
    allowed = set(_as_str_list(contract.get("openmaic_scene_types")))
    explicit = str(scene.get("runtime_scene_type") or "").strip()
    if explicit:
        if explicit not in allowed:
            raise CognisphereIntegrationError(
                "invalid_learning_scene",
                message=f"unsupported OpenMAIC scene type: {explicit}",
                details={"allowed": sorted(allowed)},
            )
        return explicit
    mapping = contract.get("learning_kind_to_openmaic_type")
    scene_type = str(mapping.get(kind) if isinstance(mapping, Mapping) else "").strip()
    if scene_type not in allowed:
        raise CognisphereIntegrationError(
            "invalid_learning_scene",
            message=f"no OpenMAIC scene type mapping for learning kind: {kind}",
            details={"kind": kind},
        )
    return scene_type


def _scene_content(scene_type: str, scene: Mapping[str, Any], title: str) -> dict[str, Any]:
    content = scene.get("openmaic_content") or scene.get("content")
    if isinstance(content, Mapping) and content.get("type") == scene_type:
        return dict(content)
    return _default_scene_content(scene_type, title)


def _default_scene_content(scene_type: str, title: str) -> dict[str, Any]:
    if scene_type == "quiz":
        return {"type": "quiz", "questions": []}
    if scene_type == "slide":
        return {
            "type": "slide",
            "canvas": {
                "id": _stable_hash(title)[:12],
                "elements": [],
                "background": {"type": "solid", "color": "#FFFFFF"},
            },
        }
    if scene_type == "interactive":
        return {"type": "interactive", "html": "", "assets": []}
    if scene_type == "pbl":
        return {"type": "pbl", "project": {"title": title, "tasks": []}}
    return {"type": scene_type}


def _looks_like_iso_timestamp(value: str) -> bool:
    if len(value) < 20:
        return False
    return "T" in value and (value.endswith("Z") or "+" in value[10:] or "-" in value[10:])


def _gate(name: str, issues: list[str]) -> dict[str, Any]:
    return {"ok": not issues, "gate": name, "issues": issues}


def _starts_with_weak_verb(statement: str, contract: Mapping[str, Any]) -> bool:
    lower = statement.lower()
    weak = _as_str_list(contract.get("weak_objective_verbs"))
    observable = _as_str_list(contract.get("observable_objective_verbs"))
    starts_weak = any(lower.startswith(verb.lower()) for verb in weak)
    has_observable = any(verb.lower() in lower for verb in observable)
    return starts_weak and not has_observable


def _valid_threshold(value: Any) -> bool:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return 0.0 <= numeric <= 1.0


def _required_str(payload: Mapping[str, Any], field: str, code: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise CognisphereIntegrationError(
            code,
            message=f"{field} is required",
            details={"field": field},
        )
    return value


def _segment(value: str) -> str:
    if value in {".", ".."}:
        raise CognisphereIntegrationError(
            "invalid_openmaic_path_segment",
            message=f"OpenMAIC path segment must not be {value!r}",
        )
    return quote(value, safe="")


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _as_mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _course_key(course: CourseRef) -> str:
    return f"{course.course_id}@{course.version}"


def _join_url(base_url: str, path_or_url: str) -> str:
    if urlsplit(path_or_url).scheme in {"http", "https"}:
        return path_or_url
    path = path_or_url if path_or_url.startswith("/") else f"/{path_or_url}"
    if path.startswith("/api/") and base_url.rstrip("/").endswith("/api/persistence"):
        return f"{_openmaic_origin(base_url)}{path}"
    return f"{base_url}{path}"


def _openmaic_origin(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if not parsed.scheme or not parsed.netloc:
        return base_url.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}"


def _response_payload(response: httpx.Response) -> Any:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return response.json()
        except ValueError as exc:
            raise CognisphereIntegrationError(
                "openmaic_malformed_response",
                message="OpenMAIC export response was not valid JSON",
                details={"status_code": response.status_code},
            ) from exc
    if response.content:
        return {
            "artifact_id": response.headers.get("x-artifact-id")
            or _stable_hash(response.content.hex())[:16],
            "url": response.headers.get("location"),
            "content_type": content_type,
            "content_length": len(response.content),
        }
    location = response.headers.get("location")
    if location:
        return {"url": location}
    return {}


def _artifact_from_export_response(
    course: CourseRef,
    format: str,
    *,
    artifact_type: str,
    route: str,
    payload: Any,
) -> ArtifactRef:
    data = payload if isinstance(payload, Mapping) else {}
    artifact_id = _first_string(data, ("artifact_id", "artifactId", "id", "jobId"))
    uri = _first_string(data, ("url", "download_url", "downloadUrl", "artifact_url", "artifactUrl"))
    if not artifact_id:
        artifact_id = _stable_hash(f"{artifact_type}:{course.course_id}:{course.version}:{format}")[
            :16
        ]
    metadata = {
        "route": route,
        "response": dict(data),
    }
    return ArtifactRef(
        artifact_id=artifact_id,
        course_id=course.course_id,
        artifact_type=f"openmaic_{artifact_type}",
        format=format,
        uri=uri,
        metadata=metadata,
    )


def _first_string(payload: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _is_openmaic_storage_unavailable(exc: CognisphereIntegrationError) -> bool:
    return exc.code in {
        "openmaic_persistence_not_configured",
        "openmaic_persistence_dev_token_missing",
    } or (
        exc.code == "openmaic_http_error"
        and int(exc.details.get("status_code", 0)) in {404, 503}
    )


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _openmaic_http_error(response: httpx.Response) -> CognisphereIntegrationError:
    details: Any = {"status_code": response.status_code}
    code = "openmaic_http_error"
    message = f"OpenMAIC HTTP request failed with status {response.status_code}"
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, Mapping):
        err = payload.get("error")
        if isinstance(err, Mapping):
            raw_code = err.get("code")
            raw_message = err.get("message")
            if isinstance(raw_code, str) and raw_code:
                code = f"openmaic_{raw_code.lower()}"
            if isinstance(raw_message, str) and raw_message:
                message = raw_message
            details = {
                "status_code": response.status_code,
                "openmaic_error": dict(err),
            }
    return CognisphereIntegrationError(code, message=message, details=details)
