"""Course runtime contract tests for OpenMAIC-style adapters."""

from __future__ import annotations

import json
from zipfile import ZipFile

import httpx
import pytest

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
    validate_learning_event,
)
from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError


def _valid_manifest() -> dict:
    return {
        "course_id": "california-electrician-ge-foundation",
        "version": "1.0.0",
        "locale": "zh-CN",
        "audience_profile": "adult_beginner",
        "source_pack_version": "2026-09-01",
        "competency_graph_version": "1.2.0",
        "risk_level": "regulated_training_support",
        "approval_status": "technical_reviewed",
        "learning_objectives": [
            {
                "objective_id": "obj-branch-circuit-load",
                "statement": "计算给定分支电路的负载并解释安全边界",
                "domain": "electrical",
                "level": "foundation",
                "prerequisites": [],
                "source_refs": ["src-nec-2026-example"],
                "assessment_refs": ["assess-load-calc-v1"],
                "lab_refs": ["lab-load-calc-fixture"],
                "mastery_threshold": 0.8,
                "requires_lab": True,
            }
        ],
        "lessons": [
            {
                "lesson_id": "lesson-branch-circuits",
                "scenes": [
                    {
                        "scene_id": "scene-load-lab",
                        "kind": "execute_lab",
                        "objective_ids": ["obj-branch-circuit-load"],
                    }
                ],
            }
        ],
        "high_risk_claims": [
            {
                "claim_id": "claim-nec-load-limit",
                "source_levels": ["S0"],
            }
        ],
        "generation_inputs_ref": "source-pack://california-electrician/2026-09-01",
    }


def test_contract_loads_from_manifest() -> None:
    contract = load_course_runtime_contract()
    assert contract["contract_id"] == "deeptutor.openmaic.course_runtime.v1"
    assert "execute_lab" in contract["scene_kinds"]
    assert "maic-zip" in contract["export_formats"]


def test_validate_course_manifest_accepts_mvp_shape() -> None:
    report = validate_course_manifest(_valid_manifest())
    assert report["ok"] is True
    assert report["issues"] == []
    assert report["gates"]["G0 Source"]["ok"] is True
    assert report["gates"]["G4 Lab"]["ok"] is True


def test_validate_course_manifest_blocks_weak_objectives_and_unverified_claims() -> None:
    manifest = _valid_manifest()
    manifest["learning_objectives"][0]["statement"] = "理解分支电路"
    manifest["learning_objectives"][0]["source_refs"] = []
    manifest["high_risk_claims"][0]["source_levels"] = ["S3"]

    report = validate_course_manifest(manifest)

    assert report["ok"] is False
    assert "weak_objective_verb:obj-branch-circuit-load" in report["issues"]
    assert "gate_failed:G0 Source:claim-nec-load-limit" in report["issues"]
    assert "gate_failed:G0 Source:obj-branch-circuit-load" in report["issues"]


def test_openmaic_projection_preserves_deeptutor_ownership_metadata() -> None:
    stage = build_openmaic_stage_projection(_valid_manifest())
    scene = build_openmaic_scene_projection(
        {
            "course_id": "california-electrician-ge-foundation",
            "scene_id": "scene-load-lab",
            "kind": "execute_lab",
            "title": "Load calculation fixture",
            "order": 3,
            "objective_ids": ["obj-branch-circuit-load"],
            "source_refs": ["src-nec-2026-example"],
            "lab_refs": ["lab-load-calc-fixture"],
        }
    )

    assert stage["id"] == "california-electrician-ge-foundation"
    assert stage["style"] == "deeptutor-evidence-driven"
    assert scene["type"] == "pbl"
    assert scene["content"]["type"] == "pbl"
    assert scene["metadata"]["deeptutor_learning_kind"] == "execute_lab"
    assert scene["metadata"]["objective_ids"] == ["obj-branch-circuit-load"]


def test_minimal_course_compiler_generates_runnable_manifest() -> None:
    manifest = compile_minimal_course_manifest(
        topic="vLLM network troubleshooting",
        locale="zh-CN",
        audience_profile="adult_beginner",
    )

    report = validate_course_manifest(manifest)
    projected = [
        build_openmaic_scene_projection(scene)
        for lesson in manifest["lessons"]
        for scene in lesson["scenes"]
    ]

    assert report["ok"] is True
    assert report["gates"]["G3 Assessment"]["ok"] is True
    assert report["gates"]["G6 Security"]["ok"] is True
    assert report["gates"]["G8 Reproducibility"]["ok"] is True
    assert len(projected) == 6
    assert all(scene["content"] for scene in projected)


def test_learning_event_validation_requires_traceable_anonymous_envelope() -> None:
    valid_event = {
        "event_type": "lab.executed",
        "client_time": "2026-09-06T01:02:03.000Z",
        "server_time": "2026-09-06T01:02:04.000Z",
        "course_id": "california-electrician-ge-foundation",
        "course_version": "1.0.0",
        "objective_ids": ["obj-branch-circuit-load"],
        "learner_hash": "a" * 64,
        "trace_id": "trace-1",
    }

    assert validate_learning_event(valid_event)["ok"] is True

    invalid_event = dict(valid_event)
    invalid_event["event_type"] = "raw.answer.key"
    invalid_event["learner_hash"] = "learner-123"

    report = validate_learning_event(invalid_event)
    assert report["ok"] is False
    assert "unsupported_learning_event_type:raw.answer.key" in report["issues"]
    assert "invalid_learning_event_field:learner_hash" in report["issues"]


def test_course_runtime_adapter_factory_selects_memory_or_http() -> None:
    assert isinstance(create_course_runtime_adapter(), InMemoryCourseRuntimeAdapter)
    adapter = create_course_runtime_adapter(
        base_url="https://openmaic.example",
        export_routes={"pptx": "/api/export/pptx"},
    )
    assert isinstance(adapter, HttpOpenMaicCourseRuntimeAdapter)
    assert adapter.export_routes["pptx"] == "/api/export/pptx"


@pytest.mark.asyncio
async def test_in_memory_adapter_runs_runtime_boundary() -> None:
    adapter: CourseRuntimeAdapter = InMemoryCourseRuntimeAdapter()

    course = await adapter.create_draft(_valid_manifest())
    scene = await adapter.upsert_scene(
        {
            "course_id": course.course_id,
            "scene_id": "scene-load-lab",
            "kind": "execute_lab",
            "objective_ids": ["obj-branch-circuit-load"],
        }
    )
    rendered = await adapter.render(course, {"format": "html"})
    session = await adapter.launch(course, {"learner_id": "learner-123"})
    exported = await adapter.export(course, "maic-zip")
    event = await adapter.record_event(
        {
            "event_type": "lab.executed",
            "client_time": "2026-09-06T01:02:03.000Z",
            "server_time": "2026-09-06T01:02:04.000Z",
            "course_id": course.course_id,
            "course_version": course.version,
            "objective_ids": ["obj-branch-circuit-load"],
            "learner_hash": session.learner_hash,
            "trace_id": "trace-load-lab",
        }
    )

    assert scene.kind == "execute_lab"
    assert rendered.format == "html"
    assert session.learner_hash != "learner-123"
    assert exported.artifact_type == "export"
    assert event["event_count"] == 1


@pytest.mark.asyncio
async def test_in_memory_adapter_exports_real_local_artifacts() -> None:
    adapter = InMemoryCourseRuntimeAdapter()
    manifest = compile_minimal_course_manifest(
        topic="Evidence based debugging",
        locale="en",
        audience_profile="developer",
    )
    course = await adapter.create_draft(manifest)
    for lesson in manifest["lessons"]:
        for scene in lesson["scenes"]:
            await adapter.upsert_scene(scene)

    html = await adapter.export(course, "html")
    pptx = await adapter.export(course, "pptx")
    archive = await adapter.export(course, "maic-zip")

    assert html.uri is not None and html.uri.endswith("course.html")
    assert pptx.uri is not None and pptx.uri.endswith("course.pptx")
    assert archive.uri is not None and archive.uri.endswith("course.maic.zip")
    with ZipFile(archive.uri) as zip_file:
        assert "manifest.json" in zip_file.namelist()
        manifest_json = json.loads(zip_file.read("manifest.json").decode("utf-8"))
    assert manifest_json["stage"]["id"] == course.course_id
    assert len(manifest_json["scenes"]) == 6


@pytest.mark.asyncio
async def test_in_memory_adapter_rejects_invalid_export_format() -> None:
    adapter = InMemoryCourseRuntimeAdapter()
    course = await adapter.create_draft(_valid_manifest())

    with pytest.raises(CognisphereIntegrationError) as exc:
        await adapter.export(course, "pdf")

    assert exc.value.code == "unsupported_course_export_format"


@pytest.mark.asyncio
async def test_http_openmaic_adapter_uses_document_and_runtime_contracts() -> None:
    calls: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json_body(request)
        calls.append((request.method, request.url.path, body))
        if request.method == "POST" and request.url.path == "/runtime/sessions":
            assert body is not None
            assert request.headers["x-learner-key"] == body["learnerKey"]
            return httpx.Response(
                201,
                json={
                    **body,
                    "runtimeDslVersion": "runtime-1",
                },
            )
        if request.method == "POST" and request.url.path.endswith("/records"):
            assert body is not None
            assert request.headers["x-learner-key"] == body["payload"]["event"]["learner_hash"]
            return httpx.Response(201, json={**body, "seq": 0})
        return httpx.Response(204)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://openmaic.example",
    ) as client:
        adapter = HttpOpenMaicCourseRuntimeAdapter(
            "https://openmaic.example",
            client=client,
            headers={"authorization": "Bearer test"},
        )
        course = await adapter.create_draft(_valid_manifest())
        await adapter.upsert_scene(
            {
                "course_id": course.course_id,
                "scene_id": "scene-load-lab",
                "kind": "execute_lab",
                "objective_ids": ["obj-branch-circuit-load"],
            }
        )
        session = await adapter.launch(
            course,
            {
                "learner_id": "learner-123",
                "server_time": "2026-09-06T01:02:04.000Z",
            },
        )
        event = await adapter.record_event(
            {
                "session_id": session.session_id,
                "event_id": "event-load-lab",
                "event_type": "lab.executed",
                "client_time": "2026-09-06T01:02:03.000Z",
                "server_time": "2026-09-06T01:02:04.000Z",
                "course_id": course.course_id,
                "course_version": course.version,
                "objective_ids": ["obj-branch-circuit-load"],
                "learner_hash": session.learner_hash,
                "trace_id": "trace-load-lab",
                "scene_id": "scene-load-lab",
            }
        )

    assert ("PUT", "/documents/california-electrician-ge-foundation") == calls[0][:2]
    assert calls[0][2]["stage"]["id"] == "california-electrician-ge-foundation"
    assert calls[0][2]["scenes"][0]["type"] == "pbl"
    assert (
        "PUT",
        "/documents/california-electrician-ge-foundation/scenes/scene-load-lab",
    ) == calls[1][:2]
    assert calls[2][:2] == ("POST", "/runtime/sessions")
    assert calls[2][2]["learnerKey"] == session.learner_hash
    assert calls[3][:2] == (
        "POST",
        f"/runtime/sessions/{session.session_id}/records",
    )
    assert calls[3][2]["payload"]["event"]["event_type"] == "lab.executed"
    assert event["runtime_record"]["seq"] == 0


@pytest.mark.asyncio
async def test_http_openmaic_adapter_calls_configured_export_route() -> None:
    calls: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json_body(request)
        calls.append((request.method, request.url.path, body))
        if request.url.path == "/api/export/pptx":
            assert body is not None
            assert body["stageId"] == "california-electrician-ge-foundation"
            assert body["format"] == "pptx"
            return httpx.Response(
                202,
                json={
                    "artifact_id": "artifact-pptx-1",
                    "download_url": "https://openmaic.example/downloads/artifact-pptx-1",
                },
            )
        return httpx.Response(204)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://openmaic.example",
    ) as client:
        adapter = HttpOpenMaicCourseRuntimeAdapter(
            "https://openmaic.example",
            client=client,
            export_routes={"pptx": "/api/export/pptx"},
        )
        artifact = await adapter.export(
            CourseRef(
                course_id="california-electrician-ge-foundation",
                version="1.0.0",
            ),
            "pptx",
        )

    assert calls == [
        (
            "POST",
            "/api/export/pptx",
            {
                "stageId": "california-electrician-ge-foundation",
                "courseId": "california-electrician-ge-foundation",
                "version": "1.0.0",
                "format": "pptx",
                "profile": {},
            },
        )
    ]
    assert artifact.artifact_id == "artifact-pptx-1"
    assert artifact.artifact_type == "openmaic_export"
    assert artifact.uri == "https://openmaic.example/downloads/artifact-pptx-1"


@pytest.mark.asyncio
async def test_http_openmaic_adapter_publishes_persistence_document_to_classroom() -> None:
    calls: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json_body(request)
        calls.append((request.method, request.url.path, body))
        if request.method == "GET" and request.url.path == (
            "/api/persistence/documents/california-electrician-ge-foundation"
        ):
            return httpx.Response(
                200,
                json={
                    "stage": {"id": "california-electrician-ge-foundation", "name": "GE"},
                    "scenes": [{"id": "scene-load-lab", "stageId": "california-electrician-ge-foundation"}],
                },
            )
        if request.method == "POST" and request.url.path == "/api/classroom":
            assert body is not None
            assert body["stage"]["id"] == "california-electrician-ge-foundation"
            assert body["scenes"][0]["id"] == "scene-load-lab"
            return httpx.Response(
                201,
                json={
                    "success": True,
                    "id": "california-electrician-ge-foundation",
                    "url": "https://openmaic.example/classroom/california-electrician-ge-foundation",
                },
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://openmaic.example",
    ) as client:
        adapter = HttpOpenMaicCourseRuntimeAdapter(
            "https://openmaic.example/api/persistence",
            client=client,
        )
        result = await adapter.publish_classroom(
            CourseRef(
                course_id="california-electrician-ge-foundation",
                version="1.0.0",
            )
        )

    assert calls[0][:2] == (
        "GET",
        "/api/persistence/documents/california-electrician-ge-foundation",
    )
    assert calls[1][:2] == ("POST", "/api/classroom")
    assert result["classroom_url"] == (
        "https://openmaic.example/classroom/california-electrician-ge-foundation"
    )


@pytest.mark.asyncio
async def test_http_openmaic_adapter_keeps_owner_cookie_between_requests() -> None:
    cookies_seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cookies_seen.append(request.headers.get("cookie"))
        if len(cookies_seen) == 1:
            return httpx.Response(
                204,
                headers={"set-cookie": "openmaic_owner=owner-1; Path=/; Secure"},
            )
        return httpx.Response(204)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://openmaic.example",
    ) as client:
        adapter = HttpOpenMaicCourseRuntimeAdapter(
            "http://openmaic.example",
            client=client,
        )
        await adapter.create_draft(_valid_manifest())
        await adapter.upsert_scene(
            {
                "course_id": "california-electrician-ge-foundation",
                "scene_id": "scene-load-lab",
                "kind": "execute_lab",
                "objective_ids": ["obj-branch-circuit-load"],
            }
        )

    assert cookies_seen == [None, "openmaic_owner=owner-1"]


@pytest.mark.asyncio
async def test_http_openmaic_adapter_maps_binary_export_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/export/classroom"
        return httpx.Response(
            200,
            content=b"PK\x03\x04test",
            headers={
                "content-type": "application/zip",
                "location": "https://openmaic.example/downloads/course.maic.zip",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://openmaic.example",
    ) as client:
        adapter = HttpOpenMaicCourseRuntimeAdapter(
            "https://openmaic.example",
            client=client,
            export_routes={"maic-zip": "/api/export/classroom"},
        )
        artifact = await adapter.export(
            CourseRef(
                course_id="california-electrician-ge-foundation",
                version="1.0.0",
            ),
            "maic-zip",
        )

    assert artifact.format == "maic-zip"
    assert artifact.artifact_type == "openmaic_export"
    assert artifact.uri == "https://openmaic.example/downloads/course.maic.zip"
    assert artifact.metadata is not None
    assert artifact.metadata["response"]["content_length"] == 8


@pytest.mark.asyncio
async def test_http_openmaic_adapter_requires_configured_export_route() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(204)),
        base_url="https://openmaic.example",
    ) as client:
        adapter = HttpOpenMaicCourseRuntimeAdapter(
            "https://openmaic.example",
            client=client,
        )
        with pytest.raises(CognisphereIntegrationError) as exc:
            await adapter.export(
                CourseRef(
                    course_id="california-electrician-ge-foundation",
                    version="1.0.0",
                ),
                "html",
            )

    assert exc.value.code == "openmaic_export_route_unconfigured"


@pytest.mark.asyncio
async def test_http_openmaic_adapter_maps_storage_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": "VALIDATION_FAILED",
                    "message": "@openmaic/storage: invalid stage",
                    "details": [{"path": "/stage"}],
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://openmaic.example",
    ) as client:
        adapter = HttpOpenMaicCourseRuntimeAdapter(
            "https://openmaic.example",
            client=client,
        )
        with pytest.raises(CognisphereIntegrationError) as exc:
            await adapter.create_draft(_valid_manifest())

    assert exc.value.code == "openmaic_validation_failed"
    assert exc.value.details["status_code"] == 400


def json_body(request: httpx.Request) -> dict | None:
    if not request.content:
        return None
    return json.loads(request.content.decode("utf-8"))
