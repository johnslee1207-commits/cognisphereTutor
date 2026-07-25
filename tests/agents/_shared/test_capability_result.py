"""Hub gate: emit_capability_result envelope discipline (P1)."""

from __future__ import annotations

from typing import Any
from types import SimpleNamespace

import pytest

from cognispheretutor.agents._shared.capability_result import emit_capability_result
from cognispheretutor.core.agentic.usage import UsageTracker


class _FakeStream:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], str]] = []

    async def result(self, payload: dict[str, Any], *, source: str) -> None:
        self.calls.append((payload, source))


@pytest.mark.asyncio
async def test_emit_attaches_cost_summary_into_metadata() -> None:
    stream = _FakeStream()
    usage = UsageTracker(model="test-model")
    usage.add_from_response(
        SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    )

    payload: dict[str, Any] = {"response": "hi", "metadata": {"kept": True}}
    await emit_capability_result(stream, payload, source="chat", usage=usage)

    assert len(stream.calls) == 1
    emitted, source = stream.calls[0]
    assert source == "chat"
    assert emitted is payload
    assert payload["metadata"]["kept"] is True
    assert payload["metadata"]["cost_summary"]["total_tokens"] == 15
    assert payload["metadata"]["cost_summary"]["total_calls"] == 1


@pytest.mark.asyncio
async def test_emit_without_usage_leaves_payload_untouched() -> None:
    stream = _FakeStream()
    payload: dict[str, Any] = {"response": "ok"}
    await emit_capability_result(stream, payload, source="visualize", usage=None)
    assert stream.calls == [(payload, "visualize")]
    assert "metadata" not in payload
