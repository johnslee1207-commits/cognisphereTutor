"""Thin CP-06 Socratic tutor client prefers twin pack APIs."""

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


def test_cp_socratic_tutor_status_forwards_to_twin(
    plugins_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cognispheretutor.integrations.cognisphere.cp_socratic_tutor_client as client
    from cognispheretutor.integrations.cognisphere.cp_socratic_tutor_client import (
        cp_socratic_tutor_status,
    )

    fake_mod = types.ModuleType(
        "cognisphere_plugins.aws_certification_twin.cp_socratic_tutor"
    )

    def _status(**kwargs):  # noqa: ANN001, ARG001
        return {
            "ok": True,
            "status": "ready",
            "phase_id": "CP-06",
            "mastery_writeback": False,
            "ct08_write_back": False,
        }

    fake_mod.cp_socratic_tutor_status = _status  # type: ignore[attr-defined]

    twin_pkg = types.ModuleType("cognisphere_plugins.aws_certification_twin")
    twin_pkg.cp_socratic_tutor = fake_mod  # type: ignore[attr-defined]
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
        "cognisphere_plugins.aws_certification_twin.cp_socratic_tutor",
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

    result = cp_socratic_tutor_status(root=plugins_root)
    assert result["ok"] is True
    assert result["status"] == "ready"
    assert result["renders_ui"] is False
    assert result["ct08_write_back"] is False
    assert result["contract"] == "cognisphere.tutor.aws_cp_socratic_tutor.v1"


def test_cp_socratic_tutor_fail_closed_without_twin(
    plugins_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cognispheretutor.integrations.cognisphere.cp_socratic_tutor_client as client
    from cognispheretutor.integrations.cognisphere.cp_socratic_tutor_client import (
        cp_socratic_tutor_status,
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

    result = cp_socratic_tutor_status(root=plugins_root)
    assert result["ok"] is False
    assert result["error"] == "twin_cp_socratic_tutor_unavailable"
    assert result["mastery_writeback"] is False


@pytest.mark.skipif(not SIBLING_LP.is_dir(), reason="sibling LP monorepo absent")
def test_live_sibling_cp06_status_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(SIBLING_LP))
    from cognispheretutor.integrations.cognisphere.cp_socratic_tutor_client import (
        cp_socratic_tutor_status,
        start_cp_tutor_session,
    )

    status = cp_socratic_tutor_status(root=SIBLING_LP)
    if not status.get("ok"):
        pytest.skip(f"twin CP-06 not importable: {status.get('issues')}")
    assert status["phase_id"] == "CP-06" or status.get("validation", {}).get(
        "phase_id"
    ) == "CP-06" or status.get("roadmap_band") == "CP"

    started = start_cp_tutor_session("cp_pkg_ec2_vs_lambda", root=SIBLING_LP)
    assert started.get("ok") is True, started.get("issues")
    assert started["session"]["asks_not_spoils"] is True
