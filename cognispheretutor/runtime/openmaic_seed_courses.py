"""Seed packaged OpenMAIC classroom courseware into a managed sidecar."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from cognispheretutor.runtime.home import PACKAGE_ROOT

DEFAULT_OPENMAIC_COURSEWARE_DIR = (
    PACKAGE_ROOT / "cognispheretutor" / "vendor" / "openmaic-courseware"
)


@dataclass(frozen=True, slots=True)
class OpenMaicSeedResult:
    course_id: str
    ok: bool
    classroom_url: str | None = None
    error: str | None = None


def seed_openmaic_courseware(
    origin: str,
    *,
    courseware_dir: Path | None = None,
    timeout: float = 30.0,
) -> list[OpenMaicSeedResult]:
    """Post packaged OpenMAIC classroom seed files to a managed sidecar."""

    root = courseware_dir or DEFAULT_OPENMAIC_COURSEWARE_DIR
    if not root.exists():
        return []
    results: list[OpenMaicSeedResult] = []
    for path in sorted(root.glob("*.json")):
        results.append(_seed_one(origin.rstrip("/"), path, timeout=timeout))
    return results


def _seed_one(origin: str, path: Path, *, timeout: float) -> OpenMaicSeedResult:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        course_id = _course_id(payload, path)
        stage = payload.get("stage") if isinstance(payload, dict) else None
        scenes = payload.get("scenes") if isinstance(payload, dict) else None
        if not isinstance(stage, dict) or not isinstance(scenes, list):
            return OpenMaicSeedResult(course_id, False, error="missing stage/scenes")
        body = json.dumps({"stage": stage, "scenes": scenes}).encode("utf-8")
        request = urlrequest.Request(
            f"{origin}/api/classroom",
            data=body,
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urlrequest.urlopen(request, timeout=timeout) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))
        url = _classroom_url(data)
        return OpenMaicSeedResult(course_id, True, classroom_url=url)
    except (OSError, ValueError, urlerror.URLError) as exc:
        fallback_id = path.stem
        return OpenMaicSeedResult(fallback_id, False, error=str(exc))


def _course_id(payload: Any, path: Path) -> str:
    if isinstance(payload, dict):
        stage = payload.get("stage")
        if isinstance(stage, dict):
            value = str(stage.get("id") or "").strip()
            if value:
                return value
    return path.stem


def _classroom_url(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("url", "classroom_url", "classroomUrl"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


__all__ = [
    "DEFAULT_OPENMAIC_COURSEWARE_DIR",
    "OpenMaicSeedResult",
    "seed_openmaic_courseware",
]
