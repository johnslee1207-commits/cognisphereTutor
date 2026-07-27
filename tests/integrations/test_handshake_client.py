"""Thin handshake_client prefers LearningPlugins SDK when available."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "cognisphere_learning_plugins"
)


@pytest.fixture()
def plugins_root(monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(FIXTURE_ROOT))
    return FIXTURE_ROOT


def test_list_handshake_domains_ok(plugins_root: Path) -> None:
    from cognispheretutor.integrations.cognisphere.handshake_client import list_domains

    listing = list_domains(root=plugins_root)
    assert listing["ok"] is True
    domains = {p["domain"] for p in listing["plugins"]}
    assert {"leetcode", "ap_calculus", "aws_certification"} <= domains
    assert listing.get("sot_docs")


def test_handshake_fixture_domain(plugins_root: Path) -> None:
    from cognispheretutor.integrations.cognisphere.handshake_client import handshake

    # Fixture packs may not expose full SDK; client must still return structured envelope.
    result = handshake("leetcode", root=plugins_root, check_mode="full")
    assert "ok" in result
    assert result.get("contract")
    assert result.get("source") in {"cognisphere_plugin_sdk", "tutor_local_fallback"}
    assert "issues" in result


def test_learning_twin_flow_envelope(plugins_root: Path) -> None:
    from cognispheretutor.integrations.cognisphere.handshake_client import (
        learning_twin_flow,
        list_learning_twin_pairs,
    )

    listing = list_learning_twin_pairs(root=plugins_root)
    assert listing.get("contract")
    assert listing.get("flow") == "learning_then_twin"
    assert "learning" in listing

    # Fixture root may lack twin packs / full SDK; envelope must stay structured.
    result = learning_twin_flow("leetcode", root=plugins_root)
    assert result.get("flow") == "learning_then_twin"
    assert "summary" in result
    assert result.get("source") in {"cognisphere_plugin_sdk", "tutor_local_fallback"}
