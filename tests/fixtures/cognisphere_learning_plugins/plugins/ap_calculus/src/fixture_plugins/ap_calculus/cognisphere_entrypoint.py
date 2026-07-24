"""Fixture Cognisphere entrypoint for ap_calculus."""

from __future__ import annotations

from typing import Any

DOMAIN = "ap_calculus"


def get_plugin_info() -> dict[str, Any]:
    return {"host": "cognisphere", "domain": DOMAIN, "capabilities": ["ontology", "deeptutor_export"]}


def validate() -> dict[str, Any]:
    return {"ok": True, "domain": DOMAIN}


def status() -> dict[str, Any]:
    return get_plugin_info()
