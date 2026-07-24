"""Fixture cognisphereTutor entrypoints for Cognisphere integration tests."""

from __future__ import annotations

from typing import Any

from fixture_plugins._common import (
    export_package_for,
    negotiate_for,
    validate_adapter_for,
)

DOMAIN = "leetcode"


def export_deeptutor_package() -> dict[str, Any]:
    return export_package_for(DOMAIN)


def validate_adapter() -> dict[str, Any]:
    return validate_adapter_for(DOMAIN)


def negotiate_capabilities(request: dict[str, Any] | None = None) -> dict[str, Any]:
    return negotiate_for(DOMAIN, request)
