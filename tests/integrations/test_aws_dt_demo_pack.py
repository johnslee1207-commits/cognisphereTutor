"""Smoke / fail-closed tests for AWS DT Tutor demo pack verify helper."""

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


def test_verify_fail_closed_when_twin_unavailable(
    plugins_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cognispheretutor.integrations.cognisphere.aws_dt_demo_pack as demo
    import cognispheretutor.integrations.cognisphere.aws_digital_twin_mastery_client as mastery

    def _boom(self, **kwargs):  # noqa: ANN001, ARG001
        raise ImportError("no twin")

    monkeypatch.setattr(demo.PluginRegistryClient, "ensure_import_paths", _boom)
    monkeypatch.setattr(
        mastery,
        "aws_digital_twin_mastery_status",
        lambda **kwargs: {  # noqa: ARG005
            "ok": False,
            "error": "twin_digital_twin_mastery_unavailable",
            "status": "blocked",
        },
    )

    payload = demo.verify_aws_dt_demo_pack(root=plugins_root)
    assert payload["ok"] is False
    assert payload["live_aws_api"] is False
    assert payload["use_llm"] is False
    assert "twin_import_failed" in payload["issues"] or payload["import_ok"] is False
    assert "aws-twin-mastery" in payload["tutor_cli"]


@pytest.mark.skipif(not SIBLING_LP.is_dir(), reason="sibling CognisphereLearningPlugins missing")
def test_verify_ok_against_sibling_monorepo(monkeypatch: pytest.MonkeyPatch) -> None:
    from cognispheretutor.integrations.cognisphere.aws_dt_demo_pack import (
        verify_aws_dt_demo_pack,
    )

    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(SIBLING_LP))
    # Prefer monorepo src paths for this smoke (editable layout).
    payload = verify_aws_dt_demo_pack(root=SIBLING_LP)
    assert payload["plugins_root"] == str(SIBLING_LP.resolve())
    if payload["import_ok"] and payload["mastery_status"].get("ok"):
        assert payload["ok"] is True
        assert payload["issues"] == []
    else:
        # Still assert fail-closed envelope shape when twin not installed in this env.
        assert payload["ok"] is False
        assert isinstance(payload["issues"], list)
