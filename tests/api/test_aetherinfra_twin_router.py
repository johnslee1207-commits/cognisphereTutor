from __future__ import annotations

import asyncio

from fastapi import HTTPException
import pytest

from cognispheretutor.api.routers import aetherinfra_twin


class FakeClient:
    base_url = "http://example.test"

    def embed_url(self, lab_id: str | None = None) -> str:
        return f"http://example.test/embed/{lab_id}" if lab_id else "http://example.test/"

    def get_json(self, path: str):
        if path == "/api/summary":
            return {"counts": {"labs": 21}}
        if path == "/api/curriculum":
            return {"kind": "CurriculumSummary"}
        if path == "/api/lab-maturity":
            return {"kind": "LabMaturityReport"}
        if path == "/api/capstone-flows":
            return {"kind": "CapstoneFlowList", "spec": {"count": 1}}
        if path == "/api/tutor/labs":
            return [{"labId": "lab.container.docker-lifecycle"}]
        if path == "/api/tutor/labs/lab.container.docker-lifecycle":
            return {"labId": "lab.container.docker-lifecycle"}
        if path == "/api/evidence":
            return [{"runId": "run-1", "scenarioId": "container.docker-lifecycle.real.v1"}]
        raise AssertionError(path)

    def post_json(self, path: str, payload):
        return {"path": path, "payload": payload, "status": "PASSED"}


def test_status_collects_summary_curriculum_and_maturity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aetherinfra_twin, "default_client", lambda: FakeClient())

    result = asyncio.run(aetherinfra_twin.status())

    assert result["ok"] is True
    assert result["runtime_mode"] == "full_twin"
    assert result["lab_runtime_available"] is True
    assert result["content_runtime_available"] is True
    assert result["summary"]["counts"]["labs"] == 21
    assert result["curriculum"]["kind"] == "CurriculumSummary"
    assert result["maturity"]["kind"] == "LabMaturityReport"
    assert result["capstone_flows"]["kind"] == "CapstoneFlowList"


def test_capstone_flows_are_proxied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aetherinfra_twin, "default_client", lambda: FakeClient())

    result = asyncio.run(aetherinfra_twin.capstone_flows())

    assert result["kind"] == "CapstoneFlowList"


def test_status_degrades_to_content_only_when_twin_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cognispheretutor.integrations.aetherinfra_twin import AetherInfraTwinError

    class BrokenClient(FakeClient):
        def get_json(self, path: str):
            raise AetherInfraTwinError("offline")

    monkeypatch.setattr(aetherinfra_twin, "default_client", lambda: BrokenClient())

    result = asyncio.run(aetherinfra_twin.status())

    assert result["ok"] is False
    assert result["runtime_mode"] == "content_only"
    assert result["lab_runtime_available"] is False
    assert result["content_runtime_available"] is True
    assert "run_lab" in result["unavailable_features"]
    assert "course content is available" in result["learner_message"]


def test_lab_adds_embed_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aetherinfra_twin, "default_client", lambda: FakeClient())

    result = asyncio.run(aetherinfra_twin.lab("lab.container.docker-lifecycle"))

    assert result["embed_url"].endswith("/embed/lab.container.docker-lifecycle")


def test_evidence_is_proxied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aetherinfra_twin, "default_client", lambda: FakeClient())

    result = asyncio.run(aetherinfra_twin.evidence())

    assert result == [{"runId": "run-1", "scenarioId": "container.docker-lifecycle.real.v1"}]


def test_diagnosis_payload_is_translated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aetherinfra_twin, "default_client", lambda: FakeClient())
    payload = aetherinfra_twin.DiagnosisRequest(
        selected_diagnosis="docker_lifecycle_clean",
        evidence_refs=["run-1"],
        notes="ok",
    )

    result = asyncio.run(aetherinfra_twin.submit_diagnosis("lab.container.docker-lifecycle", payload))

    assert result["payload"]["selectedDiagnosis"] == "docker_lifecycle_clean"
    assert result["payload"]["evidenceRefs"] == ["run-1"]


def test_unavailable_twin_maps_to_503(monkeypatch: pytest.MonkeyPatch) -> None:
    from cognispheretutor.integrations.aetherinfra_twin import AetherInfraTwinError

    class BrokenClient(FakeClient):
        def get_json(self, path: str):
            raise AetherInfraTwinError("offline")

    monkeypatch.setattr(aetherinfra_twin, "default_client", lambda: BrokenClient())

    with pytest.raises(HTTPException) as exc:
        asyncio.run(aetherinfra_twin.labs())
    assert exc.value.status_code == 503
    assert exc.value.detail["runtime_mode"] == "content_only"
    assert exc.value.detail["content_runtime_available"] is True


def test_learning_workspace_round_trips_state(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePathService:
        def get_workspace_dir(self):
            return tmp_path

    monkeypatch.setattr(aetherinfra_twin, "get_path_service", lambda: FakePathService())

    empty = asyncio.run(aetherinfra_twin.get_learning_workspace("default"))
    assert empty["state"]["completed_units"] == {}
    assert empty["updated_at"] is None

    payload = aetherinfra_twin.LearningWorkspaceSaveRequest(
        state=aetherinfra_twin.LearningWorkspaceState(
            selected_course_id="course.containers",
            selected_unit_id="ai_infra.expert.containers.l1",
            quiz_answers={"q1": "A"},
            completed_units={"ai_infra.expert.containers.l1": True},
            reflection_notes={"ai_infra.expert.containers.l1": "evidence-backed claim"},
            diagnosis_notes={"ai_infra.expert.containers.l1": "bounded diagnosis"},
        )
    )

    saved = asyncio.run(aetherinfra_twin.save_learning_workspace("default", payload))
    loaded = asyncio.run(aetherinfra_twin.get_learning_workspace("default"))

    assert saved["ok"] is True
    assert loaded["state"]["selected_course_id"] == "course.containers"
    assert loaded["state"]["quiz_answers"] == {"q1": "A"}
    assert loaded["state"]["completed_units"]["ai_infra.expert.containers.l1"] is True
    assert loaded["state"]["diagnosis_notes"]["ai_infra.expert.containers.l1"] == "bounded diagnosis"


def test_learning_workspace_delete_resets_state(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePathService:
        def get_workspace_dir(self):
            return tmp_path

    monkeypatch.setattr(aetherinfra_twin, "get_path_service", lambda: FakePathService())
    payload = aetherinfra_twin.LearningWorkspaceSaveRequest(
        state=aetherinfra_twin.LearningWorkspaceState(selected_course_id="course.kubernetes")
    )

    asyncio.run(aetherinfra_twin.save_learning_workspace("default", payload))
    deleted = asyncio.run(aetherinfra_twin.delete_learning_workspace("default"))
    loaded = asyncio.run(aetherinfra_twin.get_learning_workspace("default"))

    assert deleted["state"]["selected_course_id"] is None
    assert loaded["state"]["selected_course_id"] is None
    assert loaded["updated_at"] is None


def test_learning_workspace_rejects_invalid_id() -> None:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(aetherinfra_twin.get_learning_workspace("../bad"))
    assert exc.value.status_code == 400
