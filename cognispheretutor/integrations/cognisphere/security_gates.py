"""Fail-closed security gates for Cognisphere live paths."""

from __future__ import annotations

import os
from typing import Any

from cognispheretutor.integrations.cognisphere._contract import load_plugin_contract
from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError


def is_sandbox_authorized(*, env: dict[str, str] | None = None) -> bool:
    """Return True only when the host sandbox authorization env is exactly set."""
    contract = load_plugin_contract()
    env_name = str(contract["sandbox_authorized_env"])
    expected = str(contract["sandbox_authorized_value"])
    source = env if env is not None else os.environ
    return (source.get(env_name) or "").strip() == expected


def assert_sandbox_authorized(*, env: dict[str, str] | None = None) -> None:
    if not is_sandbox_authorized(env=env):
        contract = load_plugin_contract()
        raise CognisphereIntegrationError(
            "sandbox_unauthorized",
            details={"env": contract["sandbox_authorized_env"]},
        )


def gate_status(*, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Snapshot of live gates cognisphereTutor must respect (fail-closed by default)."""
    contract = load_plugin_contract()
    source = env if env is not None else os.environ
    sandbox_env = str(contract["sandbox_authorized_env"])
    return {
        "sandbox": {
            "env": sandbox_env,
            "authorized": is_sandbox_authorized(env=env),
            "value_seen": (source.get(sandbox_env) or "").strip() or None,
            "fail_closed": True,
        },
        "policy": "cognisphereTutor MUST NOT bypass Cognisphere / plugin host gates.",
    }
