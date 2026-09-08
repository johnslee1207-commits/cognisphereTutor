"""Plan a managed OpenMAIC runtime sidecar for local Tutor launches."""

from __future__ import annotations

from dataclasses import dataclass
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

    command = _managed_command(env)
    if not command:
        return _empty_plan(
            runtime_home,
            reason="no managed OpenMAIC command configured",
        )

    origin = _managed_origin(env)
    cwd = _managed_cwd(env, runtime_home)
    return OpenMaicSidecarPlan(
        should_start=True,
        origin=origin,
        base_url=origin,
        command=command,
        cwd=cwd,
        health_url=_health_url(origin, env.get(_MANAGED_HEALTH_PATH_ENV)),
        reason="starting managed OpenMAIC sidecar",
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
