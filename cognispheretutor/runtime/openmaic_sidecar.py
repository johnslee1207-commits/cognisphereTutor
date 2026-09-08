"""Plan a managed OpenMAIC runtime sidecar for local Tutor launches."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
from typing import Any, Mapping
from urllib.parse import urlsplit

from cognispheretutor.integrations.cognisphere.openmaic_runtime_discovery import (
    OPENMAIC_RUNTIME_MODE_CONFIGURED,
    OPENMAIC_RUNTIME_MODE_DISABLED,
    resolve_openmaic_course_runtime_endpoint,
)

DEFAULT_MANAGED_OPENMAIC_ORIGIN = "http://127.0.0.1:33100"
DEFAULT_MANAGED_OPENMAIC_HEALTH_PATH = "/api/health"

_MANAGED_COMMAND_ENV = "OPENMAIC_COURSE_RUNTIME_MANAGED_COMMAND"
_MANAGED_CWD_ENV = "OPENMAIC_COURSE_RUNTIME_MANAGED_CWD"
_MANAGED_ORIGIN_ENV = "OPENMAIC_COURSE_RUNTIME_MANAGED_ORIGIN"
_MANAGED_HEALTH_PATH_ENV = "OPENMAIC_COURSE_RUNTIME_MANAGED_HEALTH_PATH"
_BUNDLE_DIR_ENV = "OPENMAIC_COURSE_RUNTIME_BUNDLE_DIR"
_BUNDLE_MANIFEST_NAME = "openmaic-runtime.json"
_DEFAULT_EXPORT_ROUTES = {
    "html": "/api/export/html",
    "pptx": "/api/export/pptx",
    "maic-zip": "/api/export/classroom",
}


@dataclass(frozen=True, slots=True)
class OpenMaicSidecarPlan:
    """Describes whether Tutor should launch an OpenMAIC sidecar."""

    should_start: bool
    origin: str
    base_url: str
    command: list[str]
    cwd: Path
    health_url: str
    reason: str
    source: str
    export_routes: dict[str, str]


def plan_openmaic_sidecar(
    settings: Mapping[str, Any],
    *,
    runtime_home: Path,
    process_env: Mapping[str, str] | None = None,
    probe_existing: bool = True,
) -> OpenMaicSidecarPlan:
    """Return a launch plan for an optional managed OpenMAIC runtime.

    Tutor starts the sidecar only in ``auto`` mode, only when no configured or
    already-running OpenMAIC endpoint is available, and only when the deployment
    provides an explicit managed command.
    """

    env = process_env or os.environ
    resolution = resolve_openmaic_course_runtime_endpoint(
        settings,
        process_env=env,
        probe=probe_existing,
    )
    empty = _empty_plan(runtime_home, reason=resolution.reason)

    if resolution.mode == OPENMAIC_RUNTIME_MODE_DISABLED:
        return empty
    if resolution.mode == OPENMAIC_RUNTIME_MODE_CONFIGURED:
        return empty
    if resolution.endpoint is not None:
        return _empty_plan(runtime_home, reason=f"using {resolution.endpoint.source} OpenMAIC")

    bundle = _bundled_runtime(env, runtime_home)
    command = _managed_command(env) or (bundle.get("command") if bundle else [])
    if not command:
        return _empty_plan(
            runtime_home,
            reason="no managed OpenMAIC command configured",
        )

    origin = _managed_origin(env) if env.get(_MANAGED_ORIGIN_ENV) else str(
        bundle.get("origin") if bundle else DEFAULT_MANAGED_OPENMAIC_ORIGIN
    )
    cwd = _managed_cwd(env, runtime_home) if env.get(_MANAGED_CWD_ENV) else (
        bundle.get("cwd") if bundle else runtime_home
    )
    health_path = env.get(_MANAGED_HEALTH_PATH_ENV) or (
        str(bundle.get("health_path")) if bundle else None
    )
    source = str(bundle.get("source") if bundle else "managed")
    export_routes = _string_map(bundle.get("export_routes") if bundle else {}) or dict(
        _DEFAULT_EXPORT_ROUTES
    )
    return OpenMaicSidecarPlan(
        should_start=True,
        origin=_valid_origin(origin),
        base_url=_valid_origin(origin),
        command=command,
        cwd=cwd,
        health_url=_health_url(_valid_origin(origin), health_path),
        reason=f"starting {source} OpenMAIC sidecar",
        source=source,
        export_routes=export_routes,
    )


def _empty_plan(runtime_home: Path, *, reason: str) -> OpenMaicSidecarPlan:
    return OpenMaicSidecarPlan(
        should_start=False,
        origin="",
        base_url="",
        command=[],
        cwd=runtime_home,
        health_url="",
        reason=reason,
        source="none",
        export_routes={},
    )


def _managed_command(env: Mapping[str, str]) -> list[str]:
    raw = str(env.get(_MANAGED_COMMAND_ENV) or "").strip()
    if not raw:
        return []
    return shlex.split(raw, posix=True)


def _managed_origin(env: Mapping[str, str]) -> str:
    raw = str(env.get(_MANAGED_ORIGIN_ENV) or "").strip().rstrip("/")
    if not raw:
        return DEFAULT_MANAGED_OPENMAIC_ORIGIN
    parsed = urlsplit(raw)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return raw
    return DEFAULT_MANAGED_OPENMAIC_ORIGIN


def _managed_cwd(env: Mapping[str, str], runtime_home: Path) -> Path:
    raw = str(env.get(_MANAGED_CWD_ENV) or "").strip()
    if not raw:
        return runtime_home
    return Path(raw).expanduser().resolve()


def _bundled_runtime(env: Mapping[str, str], runtime_home: Path) -> dict[str, Any] | None:
    candidates = []
    raw_bundle = str(env.get(_BUNDLE_DIR_ENV) or "").strip()
    if raw_bundle:
        candidates.append(Path(raw_bundle).expanduser())
    candidates.extend(
        [
            runtime_home / "openmaic-runtime",
            Path(__file__).resolve().parents[1] / "vendor" / "openmaic-runtime",
        ]
    )
    for candidate in candidates:
        manifest_path = candidate / _BUNDLE_MANIFEST_NAME
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, Mapping):
            continue
        command = _manifest_command(manifest.get("command"))
        if not command:
            continue
        cwd = _manifest_cwd(candidate, manifest.get("cwd"))
        return {
            "source": "bundled",
            "command": command,
            "cwd": cwd,
            "origin": _valid_origin(str(manifest.get("origin") or DEFAULT_MANAGED_OPENMAIC_ORIGIN)),
            "health_path": str(
                manifest.get("health_path") or DEFAULT_MANAGED_OPENMAIC_HEALTH_PATH
            ),
            "export_routes": _string_map(manifest.get("export_routes")),
        }
    return None


def _manifest_command(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        return shlex.split(value, posix=True)
    return []


def _manifest_cwd(bundle_root: Path, value: Any) -> Path:
    raw = str(value or ".").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = bundle_root / path
    return path.expanduser().resolve()


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): str(item)
        for key, item in value.items()
        if str(key).strip() and str(item).strip()
    }


def _valid_origin(value: str) -> str:
    raw = value.strip().rstrip("/")
    parsed = urlsplit(raw)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return raw
    return DEFAULT_MANAGED_OPENMAIC_ORIGIN


def _health_url(origin: str, raw_path: str | None) -> str:
    path = str(raw_path or DEFAULT_MANAGED_OPENMAIC_HEALTH_PATH).strip()
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{origin}{path}"


__all__ = [
    "DEFAULT_MANAGED_OPENMAIC_HEALTH_PATH",
    "DEFAULT_MANAGED_OPENMAIC_ORIGIN",
    "OpenMaicSidecarPlan",
    "plan_openmaic_sidecar",
]
