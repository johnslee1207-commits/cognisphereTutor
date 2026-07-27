"""Thin visualization_advert_client prefers LearningPlugins SDK (N-15)."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "cognisphere_learning_plugins"
)
SIBLING_LP = Path(r"D:\Projects\CognisphereLearningPlugins")


@pytest.fixture()
def plugins_root(monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(FIXTURE_ROOT))
    return FIXTURE_ROOT


def test_consume_visualization_advert_forwards_to_sdk(
    plugins_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import types

    import cognispheretutor.integrations.cognisphere.visualization_advert_client as vac
    from cognispheretutor.integrations.cognisphere.visualization_advert_client import (
        consume_visualization_advert,
    )

    captured: dict[str, object] = {}

    def _fake_consume(twin_domain=None, **kwargs):  # noqa: ANN001
        captured["twin_domain"] = twin_domain
        captured.update(kwargs)
        return {
            "ok": True,
            "advertised": True,
            "advertisement_only": True,
            "visualization_ui": False,
            "renders_ui": False,
            "twin_domain": twin_domain or "aws_certification_twin",
            "contract": "cognisphere.tutor.twin_visualization_advert.v1",
            "roadmap_id": "N-15",
        }

    fake_mod = types.ModuleType("cognisphere_plugin_sdk.digital_twin")
    fake_mod.consume_visualization_advert = _fake_consume  # type: ignore[attr-defined]
    monkeypatch.setitem(
        __import__("sys").modules,
        "cognisphere_plugin_sdk.digital_twin",
        fake_mod,
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "cognisphere_plugin_sdk",
        types.ModuleType("cognisphere_plugin_sdk"),
    )

    # Bypass ensure_import_paths failures on fixture-only roots.
    monkeypatch.setattr(
        vac.PluginRegistryClient,
        "ensure_import_paths",
        lambda self, **kwargs: None,  # noqa: ARG005
    )
    monkeypatch.setattr(
        vac.PluginRegistryClient,
        "resolve_plugins_root",
        lambda self, root=None: Path(root or plugins_root),  # noqa: ARG005
    )

    result = consume_visualization_advert(
        "aws_certification_twin",
        root=plugins_root,
        learning_domain=None,
    )
    assert result["ok"] is True
    assert result["advertised"] is True
    assert result["renders_ui"] is False
    assert result["source"] == "cognisphere_plugin_sdk"
    assert result.get("sot_docs")
    assert captured.get("twin_domain") == "aws_certification_twin"


def test_visualization_advert_fallback_envelope(plugins_root: Path) -> None:
    from cognispheretutor.integrations.cognisphere.visualization_advert_client import (
        consume_visualization_advert,
        list_visualization_adverts,
        run_visualization_advert_smoke,
    )

    # Fixture root without twin SDK surface → structured fail-closed envelope.
    result = consume_visualization_advert("aws_certification_twin", root=plugins_root)
    assert result["ok"] is False
    assert result["renders_ui"] is False
    assert result["mode"] == "advert_only"
    assert result.get("contract")
    assert result.get("source") in {"cognisphere_plugin_sdk", "tutor_local_fallback"}

    listing = list_visualization_adverts(root=plugins_root)
    assert listing["renders_ui"] is False
    assert "issues" in listing

    smoke = run_visualization_advert_smoke(root=plugins_root)
    assert smoke["smoke"] == "visualization_advert"
    assert smoke["renders_ui"] is False


@pytest.mark.skipif(
    not SIBLING_LP.is_dir(),
    reason="Sibling CognisphereLearningPlugins monorepo not present",
)
def test_consume_against_sibling_lp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(SIBLING_LP))
    from cognispheretutor.integrations.cognisphere.visualization_advert_client import (
        consume_visualization_advert,
        run_visualization_advert_smoke,
    )

    advert = consume_visualization_advert(
        learning_domain="aws_certification",
        root=SIBLING_LP,
    )
    assert advert["ok"] is True, advert.get("issues")
    assert advert["advertised"] is True
    assert advert["visualization_ui"] is False
    assert advert["renders_ui"] is False

    smoke = run_visualization_advert_smoke(root=SIBLING_LP)
    assert smoke["ok"] is True, smoke.get("issues")
