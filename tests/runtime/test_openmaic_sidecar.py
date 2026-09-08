from __future__ import annotations

from pathlib import Path

from cognispheretutor.integrations.cognisphere.openmaic_runtime_discovery import (
    OpenMaicRuntimeEndpoint,
    OpenMaicRuntimeResolution,
)
from cognispheretutor.runtime import openmaic_sidecar


def test_openmaic_sidecar_skips_when_integration_disabled(tmp_path: Path) -> None:
    plan = openmaic_sidecar.plan_openmaic_sidecar(
        {"openmaic_course_runtime_mode": "disabled"},
        runtime_home=tmp_path,
        process_env={},
    )

    assert plan.should_start is False
    assert plan.reason == "openmaic runtime integration is disabled"


def test_openmaic_sidecar_reuses_existing_endpoint(monkeypatch, tmp_path: Path) -> None:
    endpoint = OpenMaicRuntimeEndpoint(
        base_url="http://127.0.0.1:33100/api/persistence",
        headers={},
        export_routes={},
        source="auto",
        available=True,
        message="discovered",
    )
    monkeypatch.setattr(
        openmaic_sidecar,
        "resolve_openmaic_course_runtime_endpoint",
        lambda settings, **kwargs: OpenMaicRuntimeResolution(
            endpoint=endpoint,
            mode="auto",
            candidates=("http://127.0.0.1:33100",),
            reason="discovered endpoint",
        ),
    )

    plan = openmaic_sidecar.plan_openmaic_sidecar(
        {"openmaic_course_runtime_mode": "auto"},
        runtime_home=tmp_path,
        process_env={"OPENMAIC_COURSE_RUNTIME_MANAGED_COMMAND": "npm start"},
    )

    assert plan.should_start is False
    assert plan.reason == "using auto OpenMAIC"


def test_openmaic_sidecar_starts_configured_command(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        openmaic_sidecar,
        "resolve_openmaic_course_runtime_endpoint",
        lambda settings, **kwargs: OpenMaicRuntimeResolution(
            endpoint=None,
            mode="auto",
            candidates=("http://127.0.0.1:33100",),
            reason="no reachable OpenMAIC endpoint found",
        ),
    )

    plan = openmaic_sidecar.plan_openmaic_sidecar(
        {"openmaic_course_runtime_mode": "auto"},
        runtime_home=tmp_path,
        process_env={
            "OPENMAIC_COURSE_RUNTIME_MANAGED_COMMAND": '"C:/Program Files/node/node.exe" server.js',
            "OPENMAIC_COURSE_RUNTIME_MANAGED_ORIGIN": "http://127.0.0.1:33123/",
            "OPENMAIC_COURSE_RUNTIME_MANAGED_HEALTH_PATH": "api/healthz",
        },
    )

    assert plan.should_start is True
    assert plan.origin == "http://127.0.0.1:33123"
    assert plan.base_url == "http://127.0.0.1:33123"
    assert plan.command == ["C:/Program Files/node/node.exe", "server.js"]
    assert plan.cwd == tmp_path
    assert plan.health_url == "http://127.0.0.1:33123/api/healthz"
    assert plan.source == "managed"


def test_openmaic_sidecar_starts_bundled_manifest(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        openmaic_sidecar,
        "resolve_openmaic_course_runtime_endpoint",
        lambda settings, **kwargs: OpenMaicRuntimeResolution(
            endpoint=None,
            mode="auto",
            candidates=("http://127.0.0.1:33100",),
            reason="no reachable OpenMAIC endpoint found",
        ),
    )
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "openmaic-runtime.json").write_text(
        """
        {
          "command": ["node", "server.js"],
          "cwd": ".",
          "origin": "http://127.0.0.1:33144",
          "health_path": "/api/health",
          "export_routes": {
            "html": "/api/export/html",
            "pptx": "/api/export/pptx",
            "maic-zip": "/api/export/classroom"
          }
        }
        """,
        encoding="utf-8",
    )

    plan = openmaic_sidecar.plan_openmaic_sidecar(
        {"openmaic_course_runtime_mode": "auto"},
        runtime_home=tmp_path / "home",
        process_env={"OPENMAIC_COURSE_RUNTIME_BUNDLE_DIR": str(bundle)},
    )

    assert plan.should_start is True
    assert plan.source == "bundled"
    assert plan.command == ["node", "server.js"]
    assert plan.cwd == bundle
    assert plan.origin == "http://127.0.0.1:33144"
    assert plan.export_routes == {
        "html": "/api/export/html",
        "pptx": "/api/export/pptx",
        "maic-zip": "/api/export/classroom",
    }
