"""Fixture Cognisphere entrypoint for leetcode."""

from __future__ import annotations

from typing import Any

from fixture_plugins._common import plugin_info_for

DOMAIN = "leetcode"


def get_plugin_info() -> dict[str, Any]:
    return plugin_info_for(DOMAIN)


def validate() -> dict[str, Any]:
    return {"ok": True, "domain": DOMAIN}


def status() -> dict[str, Any]:
    return get_plugin_info()
