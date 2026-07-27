"""Guided Learning /handshake routes — thin client, fail-closed without packs root."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from cognispheretutor.api.routers import cognisphere_learning

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "cognisphere_learning_plugins"
)
PREFIX = "/api/v1/learning/cognisphere"


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(FIXTURE_ROOT))
    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix=PREFIX)
    return TestClient(app)


def test_handshake_list_ok(client: TestClient) -> None:
    resp = client.get(f"{PREFIX}/handshake")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("ok") is True
    domains = {p["domain"] for p in body.get("plugins") or []}
    assert "leetcode" in domains
    assert body.get("sot_docs") or body.get("contract")


def test_handshake_post_envelope(client: TestClient) -> None:
    resp = client.post(
        f"{PREFIX}/handshake",
        json={"domain": "leetcode", "check_mode": "full"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "ok" in body
    assert body.get("source") in {"cognisphere_plugin_sdk", "tutor_local_fallback"}
    assert body.get("contract") or body.get("sot_docs")


def test_learning_twin_routes_envelope(client: TestClient) -> None:
    pairs = client.get(f"{PREFIX}/handshake/learning-twin/pairs")
    assert pairs.status_code == 200, pairs.text
    listing = pairs.json()
    assert listing.get("flow") == "learning_then_twin"
    assert listing.get("contract")

    flow = client.post(
        f"{PREFIX}/handshake/learning-twin",
        json={"learning_domain": "leetcode"},
    )
    assert flow.status_code == 200, flow.text
    body = flow.json()
    assert body.get("flow") == "learning_then_twin"
    assert "summary" in body


def test_learning_twin_route_forwards_composition_intent(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_flow(learning_domain, **kwargs):  # noqa: ANN001
        captured["learning_domain"] = learning_domain
        captured.update(kwargs)
        return {
            "ok": True,
            "flow": "learning_then_twin",
            "composition_intent": kwargs.get("composition_intent"),
            "summary": {"ok": True},
        }

    monkeypatch.setattr(
        "cognispheretutor.integrations.cognisphere.handshake_client.learning_twin_flow",
        _fake_flow,
    )
    resp = client.post(
        f"{PREFIX}/handshake/learning-twin",
        json={
            "learning_domain": "aws_certification",
            "composition_intent": "failure_drill",
            "goal": "practice Multi-AZ",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["composition_intent"] == "failure_drill"
    assert captured.get("composition_intent") == "failure_drill"
    assert captured.get("learning_domain") == "aws_certification"
    assert captured.get("goal") == "practice Multi-AZ"


def test_handshake_fail_closed_without_packs_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty = tmp_path / "no_packs"
    empty.mkdir()
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(empty))
    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix=PREFIX)
    client = TestClient(app)

    resp = client.get(f"{PREFIX}/handshake")
    assert resp.status_code == 503, resp.text
    detail = resp.json()["detail"]
    assert detail["code"] == "plugins_root_missing"
    assert detail["ok"] is False

    post = client.post(f"{PREFIX}/handshake", json={"domain": "leetcode"})
    assert post.status_code == 503
    assert post.json()["detail"]["code"] == "plugins_root_missing"
