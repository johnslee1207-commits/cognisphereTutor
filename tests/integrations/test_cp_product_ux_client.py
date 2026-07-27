"""Thin CP-08 Product UX client prefers twin pack APIs."""

from __future__ import annotations

import types
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


def test_cp_product_ux_status_forwards_to_twin(
    plugins_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cognispheretutor.integrations.cognisphere.cp_product_ux_client as client
    from cognispheretutor.integrations.cognisphere.cp_product_ux_client import (
        cp_product_ux_status,
    )

    fake_mod = types.ModuleType(
        "cognisphere_plugins.aws_certification_twin.cp_product_ux"
    )

    def _status(**kwargs):  # noqa: ANN001, ARG001
        return {
            "ok": True,
            "status": "ready",
            "phase_id": "CP-08",
            "renders_ui": False,
            "lp_ui": False,
            "marketplace_ui": False,
        }

    fake_mod.cp_product_ux_status = _status  # type: ignore[attr-defined]

    twin_pkg = types.ModuleType("cognisphere_plugins.aws_certification_twin")
    twin_pkg.cp_product_ux = fake_mod  # type: ignore[attr-defined]
    plugins_pkg = types.ModuleType("cognisphere_plugins")
    plugins_pkg.aws_certification_twin = twin_pkg  # type: ignore[attr-defined]

    monkeypatch.setitem(__import__("sys").modules, "cognisphere_plugins", plugins_pkg)
    monkeypatch.setitem(
        __import__("sys").modules,
        "cognisphere_plugins.aws_certification_twin",
        twin_pkg,
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "cognisphere_plugins.aws_certification_twin.cp_product_ux",
        fake_mod,
    )
    monkeypatch.setattr(
        client.PluginRegistryClient,
        "ensure_import_paths",
        lambda self, **kwargs: None,  # noqa: ARG005
    )
    monkeypatch.setattr(
        client.PluginRegistryClient,
        "resolve_plugins_root",
        lambda self, root=None: Path(root or plugins_root),  # noqa: ARG005
    )

    result = cp_product_ux_status(root=plugins_root)
    assert result["ok"] is True
    assert result["status"] == "ready"
    assert result["renders_ui"] is False
    assert result["lp_ui"] is False
    assert result["contract"] == "cognisphere.tutor.aws_cp_product_ux.v1"


def test_cp_product_ux_fail_closed_without_twin(
    plugins_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cognispheretutor.integrations.cognisphere.cp_product_ux_client as client
    from cognispheretutor.integrations.cognisphere.cp_product_ux_client import (
        cp_product_ux_status,
    )

    def _boom(self, **kwargs):  # noqa: ANN001, ARG001
        raise ImportError("no twin")

    monkeypatch.setattr(
        client.PluginRegistryClient,
        "ensure_import_paths",
        _boom,
    )
    monkeypatch.setattr(
        client.PluginRegistryClient,
        "resolve_plugins_root",
        lambda self, root=None: Path(root or plugins_root),  # noqa: ARG005
    )

    result = cp_product_ux_status(root=plugins_root)
    assert result["ok"] is False
    assert result["error"] == "twin_cp_product_ux_unavailable"
    assert result["renders_ui"] is False


@pytest.mark.skipif(not SIBLING_LP.is_dir(), reason="sibling LP monorepo absent")
def test_live_sibling_cp08_status_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(SIBLING_LP))
    from cognispheretutor.integrations.cognisphere.cp_product_ux_client import (
        consume_cp_visualization_advert,
        cp_product_ux_status,
        run_cp_product_ux_smoke,
    )

    status = cp_product_ux_status(root=SIBLING_LP)
    if not status.get("ok"):
        pytest.skip(f"twin CP-08 not importable: {status.get('issues')}")
    assert status.get("phase_id") == "CP-08" or status.get("roadmap_band") == "CP"
    assert status["renders_ui"] is False

    advert = consume_cp_visualization_advert(
        "cp_pkg_ec2_vs_lambda", root=SIBLING_LP
    )
    assert advert.get("ok") is True, advert.get("issues")
    assert advert["renders_ui"] is False

    smoke = run_cp_product_ux_smoke(root=SIBLING_LP)
    assert smoke.get("ok") is True, smoke.get("issues")
