"""Sandboxed shell execution: pluggable isolation backends + per-user quota."""

from cognispheretutor.services.sandbox.registry import (
    IMPLEMENTED_BACKENDS,
    assert_sandbox_registry_valid,
    list_implemented_backend_ids,
    validate_sandbox_registry,
)
from cognispheretutor.services.sandbox.service import (
    SandboxService,
    exec_capability_available,
    get_sandbox_service,
    reset_sandbox_service,
)
from cognispheretutor.services.sandbox.spec import (
    ExecRequest,
    ExecResult,
    IsolationLevel,
    Mount,
    ResourceLimits,
)

__all__ = [
    "IMPLEMENTED_BACKENDS",
    "ExecRequest",
    "ExecResult",
    "IsolationLevel",
    "Mount",
    "ResourceLimits",
    "SandboxService",
    "assert_sandbox_registry_valid",
    "exec_capability_available",
    "get_sandbox_service",
    "list_implemented_backend_ids",
    "reset_sandbox_service",
    "validate_sandbox_registry",
]
