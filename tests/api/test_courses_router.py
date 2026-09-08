"""Course Experience Platform API contract tests."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from cognispheretutor.api.routers import courses
from cognispheretutor.integrations.cognisphere.openmaic_runtime_discovery import (
    OpenMaicRuntimeEndpoint,
    OpenMaicRuntimeResolution,
)

PREFIX = "/api/v1"


@pytest.fixture(autouse=True)
def _use_in_memory_course_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        courses,
        "load_integrations_settings",
        lambda: {
            "openmaic_course_runtime_mode": "disabled",
            "openmaic_course_runtime_base_url": "",
            "openmaic_course_runtime_auto_candidates": [],
            "openmaic_course_runtime_headers": {},
            "openmaic_course_export_routes": {},
        },
    )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(courses.router, prefix=PREFIX)
    return TestClient(app)


def _valid_manifest() -> dict:
    return {
        "version": "1.0.0",
        "locale": "zh-CN",
        "audience_profile": "adult_beginner",
        "source_pack_version": "2026-09-01",
        "competency_graph_version": "1.2.0",
        "risk_level": "regulated_training_support",
        "approval_status": "technical_reviewed",
        "learning_objectives": [
            {
                "objective_id": "obj-vllm-port-map",
                "statement": "诊断容器端口映射和服务监听证据",
                "domain": "ai_infra",
                "level": "foundation",
                "prerequisites": [],
                "source_refs": ["src-vllm-network-runbook"],
                "assessment_refs": ["assess-vllm-network-v1"],
                "lab_refs": ["lab-vllm-network-fixture"],
                "mastery_threshold": 0.8,
                "requires_lab": True,
            }
        ],
        "lessons": [
            {
                "lesson_id": "lesson-vllm-network",
                "scenes": [
                    {
                        "scene_id": "scene-vllm-lab",
                        "kind": "execute_lab",
                        "title": "vLLM network fixture",
                        "objective_ids": ["obj-vllm-port-map"],
                    }
                ],
            }
        ],
        "high_risk_claims": [],
        "generation_inputs_ref": "source-pack://ai-infra/vllm-network/2026-09-06",
    }


def test_course_runtime_status_exposes_contract() -> None:
    client = _client()
    response = client.get(f"{PREFIX}/courses/runtime/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "execute_lab" in payload["scene_kinds"]
    assert "pbl" in payload["openmaic_scene_types"]


def test_course_runtime_status_reflects_openmaic_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        courses,
        "load_integrations_settings",
        lambda: {
            "openmaic_course_runtime_mode": "configured",
            "openmaic_course_runtime_base_url": "https://openmaic.example",
            "openmaic_course_runtime_auto_candidates": [],
            "openmaic_course_export_routes": {
                "pptx": "/api/export/pptx",
                "maic-zip": "/api/export/classroom",
            },
        },
    )
    client = _client()

    response = client.get(f"{PREFIX}/courses/runtime/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"] == "openmaic_http_adapter"
    assert payload["runtime_resolution"]["source"] == "configured"
    assert payload["export_routes_configured"] == ["maic-zip", "pptx"]


def test_course_runtime_status_uses_auto_discovered_openmaic(monkeypatch) -> None:
    endpoint = OpenMaicRuntimeEndpoint(
        base_url="http://127.0.0.1:33100/api/persistence",
        headers={},
        export_routes={"html": "/api/export/html"},
        source="auto",
        available=True,
        message="discovered OpenMAIC at http://127.0.0.1:33100",
    )
    monkeypatch.setattr(
        courses,
        "resolve_openmaic_course_runtime_endpoint",
        lambda settings: OpenMaicRuntimeResolution(
            endpoint=endpoint,
            mode="auto",
            candidates=("http://127.0.0.1:33100",),
            reason="discovered endpoint",
        ),
    )
    client = _client()

    response = client.get(f"{PREFIX}/courses/runtime/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"] == "openmaic_http_adapter"
    assert payload["runtime_mode"] == "auto"
    assert payload["runtime_resolution"]["base_url"] == (
        "http://127.0.0.1:33100/api/persistence"
    )


def test_plan_course_returns_runnable_manifest() -> None:
    client = _client()

    response = client.post(
        f"{PREFIX}/courses/plan",
        json={"topic": "vLLM network troubleshooting", "idempotency_key": "plan-vllm"},
    )

    assert response.status_code == 200
    payload = response.json()
    manifest = payload["result"]["manifest"]
    assert manifest["course_id"] == "vllm-network-troubleshooting"
    assert payload["result"]["validation"]["ok"] is True
    assert len(manifest["lessons"][0]["scenes"]) == 6


def test_validate_course_returns_openmaic_projection() -> None:
    client = _client()
    response = client.post(
        f"{PREFIX}/courses/ai-infra-vllm-network/validate",
        json={"manifest": _valid_manifest()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["openmaic_projection"]["stage"]["id"] == "ai-infra-vllm-network"
    assert payload["openmaic_projection"]["scenes"][0]["type"] == "pbl"


def test_compile_course_creates_idempotent_job() -> None:
    client = _client()
    body = {"manifest": _valid_manifest(), "idempotency_key": "compile-vllm-v1"}

    first = client.post(f"{PREFIX}/courses/ai-infra-vllm-network/compile", json=body)
    second = client.post(f"{PREFIX}/courses/ai-infra-vllm-network/compile", json=body)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["job_id"] == second.json()["job_id"]
    assert first.json()["status"] == "completed"
    assert first.json()["result"]["scene_count"] == 1


def test_export_course_returns_requested_format_artifact() -> None:
    client = _client()
    client.post(
        f"{PREFIX}/courses/ai-infra-vllm-network/compile",
        json={"manifest": _valid_manifest(), "idempotency_key": "export-vllm-v1"},
    )

    response = client.post(
        f"{PREFIX}/courses/ai-infra-vllm-network/exports/pptx",
        json={"version": "1.0.0", "idempotency_key": "export-vllm-pptx"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["operation"] == "course.export"
    assert payload["result"]["artifact"]["format"] == "pptx"
    assert payload["result"]["artifact"]["artifact_type"] == "export"
    assert Path(payload["result"]["artifact"]["uri"]).exists()


def test_prepublish_course_compiles_exports_and_lists_catalog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _Paths:
        user_data_dir = tmp_path

    monkeypatch.setattr(courses, "get_path_service", lambda: _Paths())
    client = _client()

    response = client.post(
        f"{PREFIX}/courses/ai-infra-vllm-network/prepublish",
        json={
            "manifest": _valid_manifest(),
            "formats": ["html", "pptx", "maic-zip", "html"],
            "idempotency_key": "prepublish-vllm-v1",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    published = payload["result"]["published"]
    assert payload["operation"] == "course.prepublish"
    assert payload["status"] == "completed"
    assert payload["result"]["scene_count"] == 1
    assert published["status"] == "available"
    assert published["runtime"] == "in_memory_contract_adapter"
    assert published["artifact_formats"] == ["html", "pptx", "maic-zip"]
    assert all(Path(artifact["uri"]).exists() for artifact in published["artifacts"])

    listed = client.get(f"{PREFIX}/courses/published")
    assert listed.status_code == 200
    assert listed.json()["courses"][0]["course_id"] == "ai-infra-vllm-network"


def test_prepublish_course_records_openmaic_classroom_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _Paths:
        user_data_dir = tmp_path

    async def fake_publish(_adapter, course):
        return {
            "ok": True,
            "course_id": course.course_id,
            "classroom_url": f"https://openmaic.example/classroom/{course.course_id}",
        }

    monkeypatch.setattr(courses, "get_path_service", lambda: _Paths())
    monkeypatch.setattr(courses, "_publish_openmaic_classroom", fake_publish)
    client = _client()

    response = client.post(
        f"{PREFIX}/courses/ai-infra-vllm-network/prepublish",
        json={
            "manifest": _valid_manifest(),
            "formats": ["html"],
            "idempotency_key": "prepublish-vllm-openmaic-url",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["classroom_publish"]["ok"] is True
    assert payload["result"]["published"]["classroom_url"] == (
        "https://openmaic.example/classroom/ai-infra-vllm-network"
    )


def test_prepublish_blocks_invalid_manifest() -> None:
    client = _client()
    manifest = _valid_manifest()
    manifest["learning_objectives"][0]["source_refs"] = []

    response = client.post(
        f"{PREFIX}/courses/ai-infra-vllm-network/prepublish",
        json={"manifest": manifest},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["result"]["validation"]["ok"] is False


def test_export_course_reports_unconfigured_openmaic_export_route(monkeypatch) -> None:
    monkeypatch.setattr(
        courses,
        "load_integrations_settings",
        lambda: {
            "openmaic_course_runtime_base_url": "https://openmaic.example",
            "openmaic_course_export_routes": {},
        },
    )
    client = _client()

    response = client.post(
        f"{PREFIX}/courses/ai-infra-vllm-network/exports/pptx",
        json={"version": "1.0.0"},
    )

    assert response.status_code == 501
    assert response.json()["detail"]["code"] == "openmaic_export_route_unconfigured"


def test_launch_course_returns_anonymous_session() -> None:
    client = _client()
    client.post(
        f"{PREFIX}/courses/ai-infra-vllm-network/compile",
        json={"manifest": _valid_manifest(), "idempotency_key": "launch-vllm-v1"},
    )

    response = client.post(
        f"{PREFIX}/courses/ai-infra-vllm-network/launch",
        json={
            "learner": {
                "learner_id": "learner-123",
                "course_version": "1.0.0",
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["course_id"] == "ai-infra-vllm-network"
    assert payload["session"]["learner_hash"] != "learner-123"


def test_record_course_event_returns_runtime_result() -> None:
    client = _client()
    client.post(
        f"{PREFIX}/courses/ai-infra-vllm-network/compile",
        json={"manifest": _valid_manifest(), "idempotency_key": "event-vllm-v1"},
    )
    session = client.post(
        f"{PREFIX}/courses/ai-infra-vllm-network/launch",
        json={
            "learner": {
                "learner_id": "learner-123",
                "course_version": "1.0.0",
            }
        },
    ).json()["session"]

    response = client.post(
        f"{PREFIX}/courses/ai-infra-vllm-network/events",
        json={
            "event": {
                "session_id": session["session_id"],
                "event_type": "lab.executed",
                "client_time": "2026-09-06T01:02:03.000Z",
                "course_version": "1.0.0",
                "objective_ids": ["obj-vllm-port-map"],
                "learner_hash": session["learner_hash"],
                "trace_id": "trace-vllm-lab",
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["event_type"] == "lab.executed"
    assert payload["result"]["trace_id"] == "trace-vllm-lab"


def test_publish_blocks_manifest_that_fails_quality_gate() -> None:
    client = _client()
    manifest = _valid_manifest()
    manifest["learning_objectives"][0]["source_refs"] = []

    response = client.post(
        f"{PREFIX}/courses/ai-infra-vllm-network/publish",
        json={"manifest": manifest},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["result"]["validation"]["ok"] is False


def test_job_lookup_returns_compile_result() -> None:
    client = _client()
    compile_response = client.post(
        f"{PREFIX}/courses/ai-infra-vllm-network/compile",
        json={"manifest": _valid_manifest(), "idempotency_key": "lookup-vllm-v1"},
    )
    job_id = compile_response.json()["job_id"]

    response = client.get(f"{PREFIX}/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["job_id"] == job_id
