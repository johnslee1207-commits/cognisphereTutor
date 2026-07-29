"""Thin clients for AWS twin CP-04 / MVP-2 / digital twin mastery."""

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


def test_runtime_interaction_fail_closed_without_twin(
    plugins_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cognispheretutor.integrations.cognisphere.cp_runtime_interaction_client as client
    from cognispheretutor.integrations.cognisphere.cp_runtime_interaction_client import (
        runtime_interaction_status,
    )

    def _boom(self, **kwargs):  # noqa: ANN001, ARG001
        raise ImportError("no twin")

    monkeypatch.setattr(client.PluginRegistryClient, "ensure_import_paths", _boom)
    monkeypatch.setattr(
        client.PluginRegistryClient,
        "resolve_plugins_root",
        lambda self, root=None: Path(root or plugins_root),  # noqa: ARG005
    )

    result = runtime_interaction_status(root=plugins_root)
    assert result["ok"] is False
    assert result["error"] == "twin_runtime_interaction_unavailable"
    assert result["renders_ui"] is False


def test_mvp_product_forwards_to_twin(
    plugins_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cognispheretutor.integrations.cognisphere.cp_mvp_product_client as client
    from cognispheretutor.integrations.cognisphere.cp_mvp_product_client import (
        mvp_product_status,
    )

    fake_mod = types.ModuleType("cognisphere_plugins.aws_certification_twin.product_mvp")

    def _status(**kwargs):  # noqa: ANN001, ARG001
        return {"ok": True, "status": "ready", "phase_id": "MVP-2"}

    fake_mod.mvp_product_status = _status  # type: ignore[attr-defined]
    twin_pkg = types.ModuleType("cognisphere_plugins.aws_certification_twin")
    twin_pkg.product_mvp = fake_mod  # type: ignore[attr-defined]
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
        "cognisphere_plugins.aws_certification_twin.product_mvp",
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

    result = mvp_product_status(root=plugins_root)
    assert result["ok"] is True
    assert result["contract"] == "cognisphere.tutor.aws_twin_mvp_product.v1"


def test_mastery_fail_closed_without_twin(
    plugins_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cognispheretutor.integrations.cognisphere.aws_digital_twin_mastery_client as client
    from cognispheretutor.integrations.cognisphere.aws_digital_twin_mastery_client import (
        run_aws_digital_twin_mastery,
    )

    def _boom(self, **kwargs):  # noqa: ANN001, ARG001
        raise ImportError("no twin")

    monkeypatch.setattr(client.PluginRegistryClient, "ensure_import_paths", _boom)
    monkeypatch.setattr(
        client.PluginRegistryClient,
        "resolve_plugins_root",
        lambda self, root=None: Path(root or plugins_root),  # noqa: ARG005
    )

    result = run_aws_digital_twin_mastery(root=plugins_root)
    assert result["ok"] is False
    assert result["path"] == "aws_digital_twin_mastery"
    assert result["error"] == "twin_digital_twin_mastery_unavailable"
    assert result["renders_ui"] is False


def test_mastery_forwards_to_twin(
    plugins_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cognispheretutor.integrations.cognisphere.aws_digital_twin_mastery_client as client
    from cognispheretutor.integrations.cognisphere.aws_digital_twin_mastery_client import (
        run_aws_digital_twin_mastery,
    )

    fake_mod = types.ModuleType(
        "cognisphere_plugins.aws_certification_twin.practitioner_mastery_path"
    )

    def _run(**kwargs):  # noqa: ANN001, ARG001
        return {
            "ok": True,
            "path": "aws_digital_twin_mastery",
            "status": "complete",
            "steps": {"cp04_experience": {"ok": True}},
            "issues": [],
        }

    fake_mod.run_aws_digital_twin_mastery = _run  # type: ignore[attr-defined]
    twin_pkg = types.ModuleType("cognisphere_plugins.aws_certification_twin")
    twin_pkg.practitioner_mastery_path = fake_mod  # type: ignore[attr-defined]
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
        "cognisphere_plugins.aws_certification_twin.practitioner_mastery_path",
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

    result = run_aws_digital_twin_mastery(root=plugins_root)
    assert result["ok"] is True
    assert result["path"] == "aws_digital_twin_mastery"
    assert result["contract"] == "cognisphere.tutor.aws_digital_twin_mastery.v1"


@pytest.mark.skipif(not SIBLING_LP.is_dir(), reason="sibling LP monorepo absent")
def test_live_sibling_aws_twin_mastery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(SIBLING_LP))
    from cognispheretutor.integrations.cognisphere.aws_digital_twin_mastery_client import (
        aws_digital_twin_mastery_status,
        run_aws_digital_twin_mastery,
    )

    status = aws_digital_twin_mastery_status(root=SIBLING_LP)
    if not status.get("ok"):
        pytest.skip(f"twin mastery not importable: {status.get('issues')}")
    assert status["path"] == "aws_digital_twin_mastery"

    result = run_aws_digital_twin_mastery(
        root=SIBLING_LP,
        include_tutor=True,
        include_acceptance=True,
        include_mvp_product=False,
    )
    assert result.get("ok") is True, result.get("issues")
    assert result["path"] == "aws_digital_twin_mastery"
    assert result["live_aws_api"] is False
