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
    assert result["summary"]["counts"]["labs"] == 21
    assert result["curriculum"]["kind"] == "CurriculumSummary"
    assert result["maturity"]["kind"] == "LabMaturityReport"


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
