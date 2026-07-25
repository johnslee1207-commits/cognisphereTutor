"""Hub gate: compose_enabled_tools mount policy (P1)."""

from __future__ import annotations

from types import SimpleNamespace

from cognispheretutor.agents._shared.tool_composition import (
    ToolMountFlags,
    compose_enabled_tools,
)


class _FakeRegistry:
    def get_enabled(self, names):
        return [SimpleNamespace(name=str(n)) for n in (names or [])]


def test_rag_mounts_only_when_has_kb() -> None:
    registry = _FakeRegistry()
    without = compose_enabled_tools(
        registry=registry,
        requested_tools=[],
        optional_whitelist=[],
        mount_flags=ToolMountFlags(has_kb=False),
    )
    with_kb = compose_enabled_tools(
        registry=registry,
        requested_tools=[],
        optional_whitelist=[],
        mount_flags=ToolMountFlags(has_kb=True),
    )
    assert "rag" not in without
    assert "rag" in with_kb


def test_exclusive_keeps_owned_and_ask_user_only() -> None:
    registry = _FakeRegistry()
    tools = compose_enabled_tools(
        registry=registry,
        requested_tools=["web_search", "reason"],
        optional_whitelist=["web_search", "reason"],
        mount_flags=ToolMountFlags(has_kb=True, has_code=True),
        capability_owned=("obsidian_search", "obsidian_read"),
        exclusive=True,
    )
    assert set(tools) == {"obsidian_search", "obsidian_read", "ask_user"}


def test_user_toggle_respected_when_not_exclusive() -> None:
    registry = _FakeRegistry()
    tools = compose_enabled_tools(
        registry=registry,
        requested_tools=["web_search"],
        optional_whitelist=["web_search", "reason"],
        mount_flags=ToolMountFlags(),
    )
    assert "web_search" in tools
    assert "reason" not in tools
