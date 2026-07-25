"""Explicit registry of implemented sandbox backends.

Only backends listed here may be selected by :func:`build_backend`. Startup /
tests call :func:`validate_sandbox_registry` so an incomplete or abstract
backend cannot silently become the active executor.
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Type

from cognispheretutor.services.sandbox.backends import (
    BwrapBackend,
    RestrictedSubprocessBackend,
    RunnerSidecarBackend,
    SandboxBackend,
)

IMPLEMENTED_BACKENDS: dict[str, Type[SandboxBackend]] = {
    "runner_sidecar": RunnerSidecarBackend,
    "bwrap": BwrapBackend,
    "restricted_subprocess": RestrictedSubprocessBackend,
}


def list_implemented_backend_ids() -> tuple[str, ...]:
    """Stable ids for backends that may be selected at runtime."""
    return tuple(IMPLEMENTED_BACKENDS)


def validate_sandbox_registry(
    registry: Mapping[str, Type[SandboxBackend]] | None = None,
) -> list[str]:
    """Return human-readable errors; empty means the registry is sound.

    Checks that every entry is a concrete ``SandboxBackend`` subclass (not the
    abstract base itself, and not a class that still leaves ``exec`` abstract).
    """
    reg = dict(registry if registry is not None else IMPLEMENTED_BACKENDS)
    errors: list[str] = []
    if not reg:
        return ["sandbox registry is empty"]

    for name, cls in reg.items():
        if not isinstance(name, str) or not name.strip():
            errors.append(f"invalid backend id: {name!r}")
            continue
        if not isinstance(cls, type):
            errors.append(f"{name}: expected a class, got {type(cls).__name__}")
            continue
        if not issubclass(cls, SandboxBackend):
            errors.append(f"{name}: must subclass SandboxBackend")
            continue
        if cls is SandboxBackend:
            errors.append(f"{name}: abstract SandboxBackend is not an implementation")
            continue
        if inspect.isabstract(cls):
            abstract = sorted(getattr(cls, "__abstractmethods__", ()))
            errors.append(
                f"{name}: still abstract ({', '.join(abstract) or 'unknown methods'})"
            )
    return errors


def assert_sandbox_registry_valid(
    registry: Mapping[str, Type[SandboxBackend]] | None = None,
) -> None:
    """Raise ``RuntimeError`` when the registry fails validation."""
    errors = validate_sandbox_registry(registry)
    if errors:
        raise RuntimeError("Sandbox backend registry invalid: " + "; ".join(errors))


__all__ = [
    "IMPLEMENTED_BACKENDS",
    "assert_sandbox_registry_valid",
    "list_implemented_backend_ids",
    "validate_sandbox_registry",
]
