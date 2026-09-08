"""Resolve the OpenMAIC course runtime endpoint for ordinary Tutor installs."""

from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Any, Mapping
from urllib.parse import urlsplit

import httpx

OPENMAIC_RUNTIME_MODE_AUTO = "auto"
OPENMAIC_RUNTIME_MODE_CONFIGURED = "configured"
OPENMAIC_RUNTIME_MODE_DISABLED = "disabled"
OPENMAIC_RUNTIME_MODES = frozenset(
    {
        OPENMAIC_RUNTIME_MODE_AUTO,
        OPENMAIC_RUNTIME_MODE_CONFIGURED,
        OPENMAIC_RUNTIME_MODE_DISABLED,
    }
)

DEFAULT_OPENMAIC_LOCAL_ORIGINS = (
    "http://127.0.0.1:33100",
    "http://localhost:33100",
)

_DISCOVERY_ENV_NAMES = (
    "OPENMAIC_COURSE_RUNTIME_BASE_URL",
    "OPENMAIC_COURSE_RUNTIME_MANAGED_URL",
    "COGNISPHERETUTOR_OPENMAIC_URL",
)


@dataclass(frozen=True)
class OpenMaicRuntimeEndpoint:
    """Resolved OpenMAIC endpoint plus user-facing availability metadata."""

    base_url: str
    headers: dict[str, str]
    export_routes: dict[str, str]
    source: str
    available: bool
    message: str


@dataclass(frozen=True)
class OpenMaicRuntimeResolution:
    """Result of endpoint resolution before adapter construction."""

    endpoint: OpenMaicRuntimeEndpoint | None
    mode: str
    candidates: tuple[str, ...]
    reason: str


_CACHE: dict[tuple[Any, ...], tuple[float, OpenMaicRuntimeResolution]] = {}


def resolve_openmaic_course_runtime_endpoint(
    settings: Mapping[str, Any],
    *,
    process_env: Mapping[str, str] | None = None,
    probe: bool = True,
    timeout: float = 0.35,
    cache_ttl_seconds: float = 10.0,
) -> OpenMaicRuntimeResolution:
    """Resolve a configured, hosted, or local OpenMAIC endpoint.

    Ordinary users should not need to hand-edit ``integrations.json``. The
    resolver honors an explicit base URL first, then managed/local discovery in
    ``auto`` mode, and returns ``None`` only when no endpoint is reachable.
    """

    env = process_env or os.environ
    mode = _runtime_mode(settings.get("openmaic_course_runtime_mode"))
    headers = _string_map(settings.get("openmaic_course_runtime_headers"))
    export_routes = _string_map(settings.get("openmaic_course_export_routes"))
    configured = _normalize_base_url(settings.get("openmaic_course_runtime_base_url"))

    if mode == OPENMAIC_RUNTIME_MODE_DISABLED:
        return OpenMaicRuntimeResolution(
            endpoint=None,
            mode=mode,
            candidates=(),
            reason="openmaic runtime integration is disabled",
        )

    if configured:
        return OpenMaicRuntimeResolution(
            endpoint=OpenMaicRuntimeEndpoint(
                base_url=configured,
                headers=headers,
                export_routes=export_routes,
                source="configured",
                available=True,
                message="using configured OpenMAIC course runtime endpoint",
            ),
            mode=mode,
            candidates=(configured,),
            reason="configured endpoint",
        )

    if mode == OPENMAIC_RUNTIME_MODE_CONFIGURED:
        return OpenMaicRuntimeResolution(
            endpoint=None,
            mode=mode,
            candidates=(),
            reason="configured mode requires openmaic_course_runtime_base_url",
        )

    candidates = _candidate_origins(settings, env)
    key = (
        candidates,
        tuple(sorted(headers.items())),
        tuple(sorted(export_routes.items())),
        bool(probe),
        float(timeout),
    )
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < cache_ttl_seconds:
        return cached[1]

    resolution = _discover_endpoint(
        candidates,
        headers=headers,
        export_routes=export_routes,
        probe=probe,
        timeout=timeout,
    )
    _CACHE[key] = (now, resolution)
    return resolution


def clear_openmaic_runtime_discovery_cache() -> None:
    """Clear resolver cache for tests and settings changes."""

    _CACHE.clear()


def _discover_endpoint(
    candidates: tuple[str, ...],
    *,
    headers: dict[str, str],
    export_routes: dict[str, str],
    probe: bool,
    timeout: float,
) -> OpenMaicRuntimeResolution:
    if not candidates:
        return OpenMaicRuntimeResolution(
            endpoint=None,
            mode=OPENMAIC_RUNTIME_MODE_AUTO,
            candidates=(),
            reason="no OpenMAIC candidates configured",
        )

    for origin in candidates:
        base_url = _persistence_base_url(origin)
        if not probe or _probe_openmaic_origin(origin, headers=headers, timeout=timeout):
            return OpenMaicRuntimeResolution(
                endpoint=OpenMaicRuntimeEndpoint(
                    base_url=base_url,
                    headers=headers,
                    export_routes=export_routes,
                    source="auto",
                    available=True,
                    message=f"discovered OpenMAIC at {origin}",
                ),
                mode=OPENMAIC_RUNTIME_MODE_AUTO,
                candidates=candidates,
                reason="discovered endpoint",
            )

    return OpenMaicRuntimeResolution(
        endpoint=None,
        mode=OPENMAIC_RUNTIME_MODE_AUTO,
        candidates=candidates,
        reason="no reachable OpenMAIC endpoint found",
    )


def _candidate_origins(
    settings: Mapping[str, Any],
    env: Mapping[str, str],
) -> tuple[str, ...]:
    values: list[str] = []
    for name in _DISCOVERY_ENV_NAMES:
        values.append(env.get(name, ""))
    raw_candidates = settings.get("openmaic_course_runtime_auto_candidates")
    if isinstance(raw_candidates, str):
        values.extend(raw_candidates.replace(";", ",").split(","))
    elif isinstance(raw_candidates, list):
        values.extend(str(item) for item in raw_candidates)
    values.extend(DEFAULT_OPENMAIC_LOCAL_ORIGINS)

    out: list[str] = []
    for value in values:
        normalized = _origin_url(value)
        if normalized and normalized not in out:
            out.append(normalized)
    return tuple(out)


def _runtime_mode(value: Any) -> str:
    mode = str(value or OPENMAIC_RUNTIME_MODE_AUTO).strip().lower()
    return mode if mode in OPENMAIC_RUNTIME_MODES else OPENMAIC_RUNTIME_MODE_AUTO


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): str(item)
        for key, item in value.items()
        if str(key).strip() and str(item).strip()
    }


def _normalize_base_url(value: Any) -> str:
    text = str(value or "").strip().rstrip("/")
    if not text:
        return ""
    parsed = urlsplit(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if parsed.path.rstrip("/") == "/api/persistence":
        return text
    return f"{text}/api/persistence"


def _origin_url(value: Any) -> str:
    text = str(value or "").strip().rstrip("/")
    if not text:
        return ""
    parsed = urlsplit(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if parsed.path.rstrip("/") == "/api/persistence":
        return f"{parsed.scheme}://{parsed.netloc}"
    return text


def _persistence_base_url(origin: str) -> str:
    return _normalize_base_url(origin)


def _probe_openmaic_origin(
    origin: str,
    *,
    headers: Mapping[str, str],
    timeout: float,
) -> bool:
    probe_urls = (
        f"{origin}/api/health",
        f"{origin}/api/persistence/documents/__cognispheretutor_probe__",
    )
    for url in probe_urls:
        try:
            response = httpx.get(url, headers=headers, timeout=timeout)
        except httpx.HTTPError:
            continue
        if response.status_code in {200, 401, 403, 404}:
            return True
    return False
