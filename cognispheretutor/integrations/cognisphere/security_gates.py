"""Fail-closed security gates for Cognisphere live paths."""

from __future__ import annotations

import os
from typing import Any

from cognispheretutor.integrations.cognisphere._contract import load_plugin_contract
from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError


def _env_names_for(contract_key: str, contract: dict[str, Any]) -> list[str]:
    """Primary env name plus one-release legacy aliases (e.g. COGNISPHERE_LEETCODE_*)."""
    primary = str(contract.get(contract_key) or "").strip()
    names: list[str] = []
    if primary:
        names.append(primary)
    aliases = (contract.get("legacy_env_aliases") or {}).get(contract_key) or []
    for alias in aliases:
        text = str(alias or "").strip()
        if text and text not in names:
            names.append(text)
    return names


def _env_value(names: list[str], source: Any) -> tuple[str | None, str | None]:
    for name in names:
        raw = (source.get(name) or "").strip()
        if raw:
            return name, raw
    return (names[0] if names else None), None


def is_sandbox_authorized(*, env: dict[str, str] | None = None) -> bool:
    """Return True only when the host sandbox authorization env is exactly set."""
    contract = load_plugin_contract()
    names = _env_names_for("sandbox_authorized_env", contract)
    expected = str(contract["sandbox_authorized_value"])
    source = env if env is not None else os.environ
    _name, value = _env_value(names, source)
    return value == expected


def assert_sandbox_authorized(*, env: dict[str, str] | None = None) -> None:
    if not is_sandbox_authorized(env=env):
        contract = load_plugin_contract()
        names = _env_names_for("sandbox_authorized_env", contract)
        raise CognisphereIntegrationError(
            "sandbox_unauthorized",
            details={"env": names[0] if names else None, "env_aliases": names[1:]},
        )


def gate_status(*, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Snapshot of live gates cognisphereTutor must respect (fail-closed by default)."""
    contract = load_plugin_contract()
    source = env if env is not None else os.environ
    names = _env_names_for("sandbox_authorized_env", contract)
    seen_name, seen_value = _env_value(names, source)
    return {
        "sandbox": {
            "env": names[0] if names else None,
            "env_aliases": names[1:],
            "authorized": is_sandbox_authorized(env=env),
            "value_seen": seen_value,
            "env_matched": seen_name,
            "fail_closed": True,
        },
        "policy": "cognisphereTutor MUST NOT bypass Cognisphere / plugin host gates.",
    }
