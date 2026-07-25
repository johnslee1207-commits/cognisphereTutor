"""Optional Manim dependency probes shared by math_animator and visualize."""

from __future__ import annotations

import importlib.util
from typing import Any

from cognispheretutor.agents._shared.capability_result import emit_capability_result
from cognispheretutor.core.stream_bus import StreamBus

MANIM_UNAVAILABLE_CODE = "manim_unavailable"

MANIM_INSTALL_HINT = (
    "Install with `pip install 'cognispheretutor[math-animator]'` "
    "or `pip install -r requirements/math-animator.txt`."
)


def is_manim_available() -> bool:
    """Return True when the optional ``manim`` package is importable."""
    return importlib.util.find_spec("manim") is not None


async def emit_manim_unavailable(
    stream: StreamBus,
    *,
    source: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a friendly capability result when Manim extras are missing.

    Prefer this over raising ``RuntimeError`` so CLI / Web turns end with a
    readable response instead of a raw failed-turn error.
    """
    await stream.content(message, source=source)
    payload: dict[str, Any] = {
        "response": message,
        "error": {
            "code": MANIM_UNAVAILABLE_CODE,
            "message": message,
            "install_hint": MANIM_INSTALL_HINT,
        },
        "artifacts": [],
    }
    if extra:
        payload.update(extra)
    await emit_capability_result(stream, payload, source=source)


__all__ = [
    "MANIM_INSTALL_HINT",
    "MANIM_UNAVAILABLE_CODE",
    "emit_manim_unavailable",
    "is_manim_available",
]
