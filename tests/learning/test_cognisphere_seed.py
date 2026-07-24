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
)
from cognispheretutor.learning.storage import LearningStore


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "cognisphere_learning_plugins"
)


def test_mastery_path_id_helpers() -> None:
    assert mastery_path_id_for_domain("leetcode") == "csphere-leetcode"
    assert is_cognisphere_path_id("csphere-leetcode")
    assert not is_cognisphere_path_id("book-1")


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
    assert (store_root / "csphere-leetcode.json").exists()
