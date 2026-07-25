"""Tests for Cognisphere → Guided Learning seed + API binding."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cognispheretutor.api.routers import cognisphere_learning
from cognispheretutor.learning.cognisphere_seed import (
    is_cognisphere_path_id,
    mastery_path_id_for_domain,
    modules_from_knowledge,
    seed_payload_from_import_receipt,
)
from cognispheretutor.learning.storage import LearningStore


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "cognisphere_learning_plugins"
)


def test_mastery_path_id_helpers() -> None:
    assert mastery_path_id_for_domain("leetcode") == "csphere-leetcode"
    assert mastery_path_id_for_domain("ap_calculus") == "csphere-ap_calculus"
    assert mastery_path_id_for_domain("aws_certification") == "csphere-aws_certification"
    assert is_cognisphere_path_id("csphere-leetcode")
    assert not is_cognisphere_path_id("book-1")


def test_seed_payload_requires_domain() -> None:
    from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError

    with pytest.raises(CognisphereIntegrationError) as exc:
        seed_payload_from_import_receipt({"knowledge": {}})
    assert exc.value.code == "domain_required"
    payload = seed_payload_from_import_receipt(
        {"domain": "ap_calculus", "knowledge": {"concepts": [{"id": "c1"}]}}
    )
    assert payload["domain"] == "ap_calculus"


def test_modules_from_knowledge_groups() -> None:
    modules = modules_from_knowledge(
        {
            "patterns": [{"pattern_id": "two-pointers", "name": "Two Pointers"}],
            "skills": [{"skill_id": "hash-map", "name": "Hash Map"}],
            "problems": [{"slug": "two-sum", "title": "Two Sum"}],
        },
        domain="leetcode",
    )
    names = [m.name for m in modules]
    assert names[0].startswith("Cognisphere")
    assert "Patterns" in names
    assert "Skills" in names
    assert "Practice problems" in names
    assert sum(len(m.knowledge_points) for m in modules) >= 4


def test_import_and_seed_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(FIXTURE_ROOT))
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path / "imports"))

    store_root = tmp_path / "learning"
    monkeypatch.setattr(
        cognisphere_learning,
        "_service",
        lambda: __import__(
            "cognispheretutor.learning.service", fromlist=["LearningService"]
        ).LearningService(LearningStore(store_root)),
    )

    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix="/api/v1/learning/cognisphere")
    client = TestClient(app)

    status = client.get("/api/v1/learning/cognisphere/status")
    assert status.status_code == 200
    body = status.json()
    assert body["ok"] is True
    assert body["defaults"]["chat_capability"] == "mastery_path"
    assert "trusted_context" in body["gates"]
    assert body["gates"]["trusted_context"]["phase"] == "DT-P3"
    domains = {p["domain"] for p in body["plugins"]}
    assert "leetcode" in domains

    seeded = client.post(
        "/api/v1/learning/cognisphere/import-and-seed",
        json={"domain": "leetcode", "seed_mastery_path": True},
    )
    assert seeded.status_code == 200, seeded.text
    payload = seeded.json()
    assert payload["ok"] is True
    assert payload["mastery_path"]["path_id"] == "csphere-leetcode"
    assert payload["mastery_path"]["kp_count"] >= 1
    assert "capability=mastery_path" in (payload.get("continue_in_chat") or "")
    assert (store_root / "csphere-leetcode.json").exists()


def test_cross_domain_and_compose_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(FIXTURE_ROOT))
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path / "imports"))

    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix="/api/v1/learning/cognisphere")
    client = TestClient(app)

    cross = client.post(
        "/api/v1/learning/cognisphere/cross-domain",
        json={"required_capabilities": ["socratic_tutor"], "goal": "practice algorithms"},
    )
    assert cross.status_code == 200, cross.text
    cross_body = cross.json()
    assert cross_body["match_count"] >= 1
    assert any(m.get("domain") == "leetcode" for m in cross_body.get("matches") or [])

    composed = client.post(
        "/api/v1/learning/cognisphere/compose",
        json={"domains": ["leetcode"], "required_capabilities": ["deeptutor_export"]},
    )
    assert composed.status_code == 200, composed.text
    compose_body = composed.json()
    assert compose_body.get("phase") == "DT-P6"
    assert any(
        (c.get("domain") == "leetcode") for c in (compose_body.get("contexts") or [])
    )


def test_recommend_from_goal_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(FIXTURE_ROOT))
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path / "imports"))

    store_root = tmp_path / "learning"
    monkeypatch.setattr(
        cognisphere_learning,
        "_service",
        lambda: __import__(
            "cognispheretutor.learning.service", fromlist=["LearningService"]
        ).LearningService(LearningStore(store_root)),
    )

    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix="/api/v1/learning/cognisphere")
    client = TestClient(app)

    preview = client.post(
        "/api/v1/learning/cognisphere/recommend-from-goal",
        json={
            "goal": "practice algorithms with Tutor export packs",
            "required_capabilities": ["deeptutor_export"],
            "compose_and_seed": False,
        },
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["match_count"] >= 1
    assert "leetcode" in body["recommended_domains"]

    seeded = client.post(
        "/api/v1/learning/cognisphere/recommend-from-goal",
        json={
            "goal": "practice algorithms with Tutor export packs",
            "required_capabilities": ["deeptutor_export"],
            "compose_and_seed": True,
        },
    )
    assert seeded.status_code == 200, seeded.text
    seeded_body = seeded.json()
    assert seeded_body["compose_seed"] is not None
    assert seeded_body["compose_seed"]["seeded_count"] >= 1
    assert (store_root / "csphere-leetcode.json").exists()


def test_compose_and_seed_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(FIXTURE_ROOT))
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path / "imports"))

    store_root = tmp_path / "learning"
    monkeypatch.setattr(
        cognisphere_learning,
        "_service",
        lambda: __import__(
            "cognispheretutor.learning.service", fromlist=["LearningService"]
        ).LearningService(LearningStore(store_root)),
    )

    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix="/api/v1/learning/cognisphere")
    client = TestClient(app)

    result = client.post(
        "/api/v1/learning/cognisphere/compose-and-seed",
        json={"domains": ["leetcode"], "seed_mastery_path": True},
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["seeded_count"] >= 1
    assert any(s.get("domain") == "leetcode" and s.get("ok") for s in body["seeds"])
    assert (store_root / "csphere-leetcode.json").exists()
