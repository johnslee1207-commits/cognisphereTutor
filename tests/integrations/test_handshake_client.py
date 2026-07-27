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


def test_learning_twin_flow_forwards_composition_intent(
    plugins_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Thin client must pass composition_intent into SDK run_learning_twin_flow."""
    import sys
    import types

    import cognispheretutor.integrations.cognisphere.handshake_client as hc
    from cognispheretutor.integrations.cognisphere.handshake_client import learning_twin_flow

    captured: dict[str, object] = {}

    def _fake_run(learning_domain, **kwargs):  # noqa: ANN001
        captured["learning_domain"] = learning_domain
        captured.update(kwargs)
        return {
            "ok": True,
            "flow": "learning_then_twin",
            "learning_domain": learning_domain,
            "composition_intent": kwargs.get("composition_intent"),
            "summary": {"ok": True, "composition_intent": kwargs.get("composition_intent")},
        }

    if "cognisphere_plugin_sdk" not in sys.modules:
        pkg = types.ModuleType("cognisphere_plugin_sdk")
        pkg.__path__ = []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "cognisphere_plugin_sdk", pkg)

    fake_mod = types.ModuleType("cognisphere_plugin_sdk.learning_twin_flow")
    fake_mod.run_learning_twin_flow = _fake_run  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cognisphere_plugin_sdk.learning_twin_flow", fake_mod)
    monkeypatch.setattr(
        hc.PluginRegistryClient,
        "ensure_import_paths",
        lambda self, **kwargs: None,  # noqa: ARG005
    )

    result = learning_twin_flow(
        "aws_certification",
        root=plugins_root,
        composition_intent="failure_drill",
    )
    assert result["ok"] is True
    assert result["composition_intent"] == "failure_drill"
    assert captured.get("composition_intent") == "failure_drill"
    assert captured.get("learning_domain") == "aws_certification"


def test_learning_twin_flow_fallback_keeps_composition_intent(
    plugins_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins

    from cognispheretutor.integrations.cognisphere.handshake_client import learning_twin_flow

    real_import = builtins.__import__

    def _block_sdk(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002,ANN001
        if name == "cognisphere_plugin_sdk.learning_twin_flow" or (
            name == "cognisphere_plugin_sdk" and fromlist and "learning_twin_flow" in fromlist
        ):
            raise ImportError("sdk_learning_twin_flow_unavailable")
        if name.startswith("cognisphere_plugin_sdk.learning_twin_flow"):
            raise ImportError("sdk_learning_twin_flow_unavailable")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _block_sdk)
    result = learning_twin_flow(
        "leetcode",
        root=plugins_root,
        composition_intent="learn_then_practice",
    )
    assert result.get("source") == "tutor_local_fallback"
    assert result.get("composition_intent") == "learn_then_practice"
    assert result["summary"].get("composition_intent") == "learn_then_practice"

def test_require_packs_root_ok(plugins_root: Path) -> None:
    from cognispheretutor.integrations.cognisphere.handshake_client import require_packs_root

    assert require_packs_root(plugins_root) == plugins_root.resolve()


def test_require_packs_root_fail_closed(tmp_path: Path) -> None:
    from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError
    from cognispheretutor.integrations.cognisphere.handshake_client import require_packs_root

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(CognisphereIntegrationError) as exc:
        require_packs_root(empty)
    assert exc.value.code == "plugins_root_missing"
