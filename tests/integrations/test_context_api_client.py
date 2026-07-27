"""Thin context_api_client prefers LearningPlugins SDK; stay fail-closed offline."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "cognisphere_learning_plugins"
)


@pytest.fixture()
def plugins_root(monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(FIXTURE_ROOT))
    monkeypatch.delenv("COGNISPHERE_CONTEXT_API_BASE_URL", raising=False)
    return FIXTURE_ROOT


def test_context_api_status_fail_closed_envelope(plugins_root: Path) -> None:
    from cognispheretutor.integrations.cognisphere.context_api_client import (
        context_api_status,
    )

    status = context_api_status(root=plugins_root)
    assert status.get("live_graphql") is False
    assert status.get("contract")
    assert status.get("sot_docs")
    mode = status.get("stub_mode") or status.get("client_mode")
    assert mode == "fail_closed"
    assert status.get("source") in {"cognisphere_plugin_sdk", "tutor_local_fallback"}


def test_bind_context_api_absent_url_unbound(plugins_root: Path) -> None:
    from cognispheretutor.integrations.cognisphere.context_api_client import (
        bind_context_api,
        reset_context_api,
    )

    result = bind_context_api(root=plugins_root)
    assert result.get("bound") is False
    assert (result.get("client_mode") or result.get("stub_mode")) == "fail_closed"
    assert result.get("live_graphql") is False
    assert result.get("source") in {"cognisphere_plugin_sdk", "tutor_local_fallback"}
    # Teardown helper must keep a structured envelope even without SDK.
    reset = reset_context_api(root=plugins_root)
    assert reset.get("client_mode") == "fail_closed"
    assert "ok" in reset
