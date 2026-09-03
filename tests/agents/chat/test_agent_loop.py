from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

from cognispheretutor.agents.chat.agent_loop import InlineThinkFilter, InlineToolMarkupFilter
from cognispheretutor.agents.chat.agentic_pipeline import AgenticChatPipeline
from cognispheretutor.capabilities.explore_context import explorer as explorer_mod
from cognispheretutor.capabilities.mastery import MASTERY_TOOL_NAMES
from cognispheretutor.core.context import Attachment, UnifiedContext
from cognispheretutor.core.stream import StreamEvent, StreamEventType
from cognispheretutor.core.stream_bus import StreamBus
from cognispheretutor.core.tool_protocol import ToolResult


async def _collect_bus_events(bus: StreamBus) -> tuple[list[StreamEvent], asyncio.Task[Any]]:
    events: list[StreamEvent] = []

    async def _consume() -> None:
        async for event in bus.subscribe():
            events.append(event)

    consumer = asyncio.create_task(_consume())
    await asyncio.sleep(0)
    return events, consumer  # type: ignore[return-value]


def _llm_chunk(
    *,
    content: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    usage: Any = None,
    finish_reason: str | None = None,
) -> SimpleNamespace:
    delta_fields: dict[str, Any] = {"content": content}
    if tool_calls is not None:
        delta_fields["tool_calls"] = [
            SimpleNamespace(
                index=tc.get("index", i),
                id=tc.get("id"),
                function=SimpleNamespace(
                    name=tc.get("name"),
                    arguments=tc.get("arguments"),
                ),
            )
            for i, tc in enumerate(tool_calls)
        ]
    else:
        delta_fields["tool_calls"] = None
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(**delta_fields),
                finish_reason=finish_reason,
            )
        ],
        usage=usage,
    )


def _usage_only_chunk(*, prompt: int, completion: int, total: int) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[],
        usage=SimpleNamespace(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
        ),
    )


async def _async_llm_stream(chunks: list[SimpleNamespace]):
    for chunk in chunks:
        yield chunk


class _ScriptedChatClient:
    def __init__(self, scripted: list[list[SimpleNamespace]]) -> None:
        self._script = list(scripted)
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []

        class _Completions:
            def __init__(self, parent: _ScriptedChatClient) -> None:
                self.parent = parent

            async def create(self, **kwargs):
                self.parent.call_count += 1
                self.parent.calls.append({**kwargs, "messages": list(kwargs.get("messages") or [])})
                if not self.parent._script:
                    raise RuntimeError("Scripted client exhausted")
                return _async_llm_stream(self.parent._script.pop(0))

        class _Chat:
            def __init__(self, parent: _ScriptedChatClient) -> None:
                self.completions = _Completions(parent)

        self.chat = _Chat(self)


class _Registry:
    def __init__(self) -> None:
        self.executed: list[dict[str, Any]] = []

    def deferred_tools(self):
        return []

    def build_prompt_text(self, _enabled, **_kwargs):
        return "- `web_search` - Search the web"

    def build_openai_schemas(self, _enabled):
        return [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ask_user",
                    "description": "Ask the user",
                    "parameters": {
                        "type": "object",
                        "properties": {"questions": {"type": "array"}},
                        "required": ["questions"],
                    },
                },
            },
        ]

    async def execute(self, name: str, **kwargs):
        self.executed.append({"name": name, "kwargs": kwargs})
        return ToolResult(
            content="tool answer",
            sources=[{"tool": name}],
            metadata={"tool": name},
            success=True,
        )


@pytest.fixture(autouse=True)
def _fake_llm_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cognispheretutor.agents.chat.agentic_pipeline.get_llm_config",
        lambda: SimpleNamespace(
            binding="openai",
            model="gpt-test",
            api_key="k",
            base_url="u",
            api_version=None,
            extra_headers={},
            reasoning_effort=None,
        ),
    )


async def _run(pipeline: AgenticChatPipeline, context: UnifiedContext):
    bus = StreamBus()
    events, consumer = await _collect_bus_events(bus)
    await pipeline.run(context, bus)
    await asyncio.sleep(0)
    await bus.close()
    await consumer
    return events


def _contents(events: list[StreamEvent]) -> list[str]:
    return [e.content for e in events if e.type == StreamEventType.CONTENT]


def _call_roles(events: list[StreamEvent]) -> list[str]:
    """Ordered list of per-round call_role markers ('narration' | 'finish')."""
    return [
        str(e.metadata.get("call_role"))
        for e in events
        if e.type == StreamEventType.PROGRESS
        and e.metadata.get("call_state") == "complete"
        and "call_role" in e.metadata
    ]


def _result(events: list[StreamEvent]) -> StreamEvent:
    return [e for e in events if e.type == StreamEventType.RESULT][-1]


class TestInlineThinkFilter:
    @staticmethod
    def _run(chunks: list[str]) -> list[tuple[str, str]]:
        f = InlineThinkFilter()
        out: list[tuple[str, str]] = []
        for c in chunks:
            out.extend(f.feed(c))
        out.extend(f.flush())
        return out

    @staticmethod
    def _join(segments: list[tuple[str, str]], kind: str) -> str:
        return "".join(text for k, text in segments if k == kind)

    def test_plain_content_passes_through(self) -> None:
        segs = self._run(["hello ", "world"])
        assert self._join(segs, "content") == "hello world"
        assert self._join(segs, "thinking") == ""

    def test_think_block_split_to_thinking(self) -> None:
        segs = self._run(["<think>plan</think>answer"])
        assert self._join(segs, "thinking") == "plan"
        assert self._join(segs, "content") == "answer"

    def test_tag_split_across_chunks(self) -> None:
        segs = self._run(["before<thi", "nk>inner</th", "ink>after"])
        assert self._join(segs, "content") == "beforeafter"
        assert self._join(segs, "thinking") == "inner"

    def test_unclosed_think_stays_thinking(self) -> None:
        # Interrupted stream: an opened think block never closes — its text
        # must never surface as content (mirrors clean_thinking_tags).
        segs = self._run(["<think>only reasoning, no answer"])
        assert self._join(segs, "content") == ""
        assert "only reasoning" in self._join(segs, "thinking")

    def test_thinking_variant_tag(self) -> None:
        segs = self._run(["<thinking>x</thinking>y"])
        assert self._join(segs, "thinking") == "x"
        assert self._join(segs, "content") == "y"

    def test_non_think_tags_untouched(self) -> None:
        segs = self._run(["a <b>bold</b> ", "and a < b comparison"])
        assert self._join(segs, "content") == "a <b>bold</b> and a < b comparison"

    def test_multiple_think_blocks(self) -> None:
        segs = self._run(["<think>1</think>mid<think>2</think>end"])
        assert self._join(segs, "content") == "midend"
        assert self._join(segs, "thinking") == "12"


class TestInlineToolMarkupFilter:
    @staticmethod
    def _run(chunks: list[str]) -> str:
        f = InlineToolMarkupFilter()
        out: list[str] = []
        for chunk in chunks:
            out.extend(f.feed(chunk))
        out.extend(f.flush())
        return "".join(out)

    def test_dsml_tool_block_is_suppressed(self) -> None:
        text = self._run(
            [
                "Let me register the final check.\n",
                "<｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name=\"mastery_grade\">",
                "<｜｜DSML｜｜parameter name=\"answer\" string=\"true\">B</｜｜DSML｜｜parameter>",
                "</｜｜DSML｜｜invoke> </｜｜DSML｜｜tool_calls>",
            ]
        )

        assert text == "Let me register the final check.\n"
        assert "DSML" not in text
        assert "mastery_grade" not in text


@pytest.mark.asyncio
async def test_inline_think_streams_to_trace_not_bubble(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Providers that inline <think> in the content channel: think text must
    stream as thinking events; only the post-think text is user content."""
    registry = _Registry()
    client = _ScriptedChatClient(
        [
            [
                _llm_chunk(content="<think>let me "),
                _llm_chunk(content="reason</think>"),
                _llm_chunk(content="The answer."),
            ]
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(pipeline, "_compose_enabled_tools", lambda _context: [])
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    events = await _run(pipeline, UnifiedContext(session_id="s1", user_message="Hi"))

    assert _contents(events) == ["The answer."]
    thinking = "".join(e.content for e in events if e.type == StreamEventType.THINKING)
    assert "let me reason" in thinking
    result = _result(events)
    assert result.metadata["response"] == "The answer."
    assert result.metadata["completed"] is True


@pytest.mark.asyncio
async def test_multi_chunk_usage_counts_as_one_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gemini OpenAI-compat (and similar) may attach usage to several stream
    chunks. Each completion must still count as one call with the final
    token totals — not N× inflated ``total_calls`` / tokens."""
    usage_partial = SimpleNamespace(prompt_tokens=100, completion_tokens=2, total_tokens=102)
    usage_final = SimpleNamespace(prompt_tokens=100, completion_tokens=5, total_tokens=105)
    registry = _Registry()
    client = _ScriptedChatClient(
        [
            [
                _llm_chunk(content="Hello", usage=usage_partial),
                _llm_chunk(content=" world", usage=usage_partial),
                _llm_chunk(content=".", finish_reason="stop", usage=usage_partial),
                _usage_only_chunk(prompt=100, completion=5, total=105),
            ]
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(pipeline, "_compose_enabled_tools", lambda _context: [])
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    events = await _run(pipeline, UnifiedContext(session_id="s1", user_message="Hi"))

    assert "".join(_contents(events)) == "Hello world."
    assert client.call_count == 1
    summary = pipeline.usage.summary()
    assert summary is not None
    assert summary["total_calls"] == 1
    assert summary["prompt_tokens"] == 100
    assert summary["completion_tokens"] == 5
    assert summary["total_tokens"] == 105
    # Final usage frame wins over earlier partials.
    assert usage_final.total_tokens == summary["total_tokens"]
    result = _result(events)
    cost = (result.metadata.get("metadata") or {}).get("cost_summary") or result.metadata.get(
        "cost_summary"
    )
    if cost is not None:
        assert cost["total_calls"] == 1
        assert cost["total_tokens"] == 105


@pytest.mark.asyncio
async def test_empty_finish_gets_one_nudge_then_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tool-less round that is ALL internal reasoning must not finalize as
    an empty answer: the loop nudges once and the model recovers."""
    registry = _Registry()
    client = _ScriptedChatClient(
        [
            # Round 1: the model "finishes" with nothing but think text.
            [_llm_chunk(content="<think>I wrote a whole script here</think>")],
            # Round 2 (after the nudge): a real answer.
            [_llm_chunk(content="Here is the real answer.")],
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(pipeline, "_compose_enabled_tools", lambda _context: [])
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    events = await _run(pipeline, UnifiedContext(session_id="s1", user_message="Make a PDF"))

    assert client.call_count == 2
    # The nudge round keeps the raw think text in-conversation and appends
    # the nudge instruction as the trailing user message.
    second_round = client.calls[1]["messages"]
    assert second_round[-1]["role"] == "user"
    assert "internal reasoning" in second_round[-1]["content"]
    assert any(
        m.get("role") == "assistant" and "whole script" in str(m.get("content"))
        for m in second_round
    )
    result = _result(events)
    assert result.metadata["response"] == "Here is the real answer."
    assert result.metadata["completed"] is True


@pytest.mark.asyncio
async def test_explore_context_pre_pass_seeds_loop_without_polluting_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the user attaches fresh context, the explore_context pre-pass runs
    before the answer loop and folds an objective briefing into the loop's
    user-message seed — while its own output never appears as the answer."""

    def _fake_explore_stream(*_args, **_kwargs):
        async def _gen():
            yield "The user and the external agent updated the navigation."

        return _gen()

    monkeypatch.setattr(explorer_mod, "llm_stream", _fake_explore_stream)
    monkeypatch.setattr(
        explorer_mod,
        "get_llm_config",
        lambda: SimpleNamespace(
            model="gpt-test", api_key="k", base_url="u", api_version=None, binding="openai"
        ),
    )

    registry = _Registry()
    client = _ScriptedChatClient([[_llm_chunk(content="Here is what that chat did.")]])
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(pipeline, "_compose_enabled_tools", lambda _context: [])
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    context = UnifiedContext(
        session_id="s1",
        user_message="what did this chat do?",
        source_manifest="[Attached Sources]\n- id=hs-imported_claude_code_x type=history",
        metadata={
            "source_index": {"hs-imported_claude_code_x": "## Claude Code\nI updated the nav."},
            "history_references": ["imported_claude_code_x"],
        },
    )
    events = await _run(pipeline, context)

    # The briefing rode into the answer loop's trailing user message (the seed).
    first_call_messages = client.calls[0]["messages"]
    seed_user_msg = first_call_messages[-1]["content"]
    assert "external agent updated the navigation" in seed_user_msg

    # The pre-pass streamed THINKING (reasoning trace), never CONTENT — the
    # answer is only the chat loop's finish text.
    assert _contents(events) == ["Here is what that chat did."]
    explore_thinking = "".join(
        e.content
        for e in events
        if e.type == StreamEventType.THINKING
        and str((e.metadata or {}).get("call_kind")) == "context_exploration"
    )
    assert "external agent updated the navigation" in explore_thinking


@pytest.mark.asyncio
async def test_finish_first_round_no_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """A request that needs no exploration: the first round emits no tool
    calls, so it IS the finish — one LLM call, streamed straight to the user."""
    registry = _Registry()
    client = _ScriptedChatClient([[_llm_chunk(content="A direct answer.")]])
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(pipeline, "_compose_enabled_tools", lambda _context: [])
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    events = await _run(pipeline, UnifiedContext(session_id="s1", user_message="Hello"))

    assert client.call_count == 1
    # The finish round's text streams to the user, not the trace.
    assert _contents(events) == ["A direct answer."]
    assert _call_roles(events) == ["finish"]
    result = _result(events)
    assert result.metadata["engine"] == "agent_loop"
    assert result.metadata["completed"] is True
    assert result.metadata["response"] == "A direct answer."
    assert result.metadata["rounds"] == 1
    assert result.metadata["tool_steps"] == 0


@pytest.mark.asyncio
async def test_tool_round_then_finish(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tool round (narration text + a tool call) is followed by a tool-less
    finish round whose text is the answer — two LLM calls, no respond pass."""
    registry = _Registry()
    client = _ScriptedChatClient(
        [
            # Round 1: preamble (narration) text + a tool call.
            [
                _llm_chunk(content="Searching."),
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-1",
                            "name": "web_search",
                            "arguments": json.dumps({"query": "Fourier transform"}),
                        }
                    ]
                ),
            ],
            # Round 2: the model sees the tool result in-protocol and finishes
            # by replying without tool calls.
            [_llm_chunk(content="Found what was needed.")],
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(pipeline, "_compose_enabled_tools", lambda _context: ["web_search"])
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    events = await _run(
        pipeline,
        UnifiedContext(
            session_id="s1", user_message="Look up Fourier", enabled_tools=["web_search"]
        ),
    )

    assert client.call_count == 2
    assert registry.executed[0]["name"] == "web_search"
    assert registry.executed[0]["kwargs"]["query"] == "Fourier transform"
    # Both rounds' text streams to the user; the round roles distinguish them.
    assert _contents(events) == ["Searching.", "Found what was needed."]
    assert _call_roles(events) == ["narration", "finish"]
    # Round 2 sees the tool exchange in-protocol: the assistant tool_calls
    # message (with its preamble text) followed by the role=tool result.
    second_round = client.calls[1]["messages"]
    assistant_tc = [m for m in second_round if m.get("role") == "assistant" and m.get("tool_calls")]
    assert assistant_tc and assistant_tc[0]["tool_calls"][0]["function"]["name"] == "web_search"
    assert assistant_tc[0]["content"] == "Searching."
    tool_msgs = [m for m in second_round if m.get("role") == "tool"]
    assert tool_msgs and "tool answer" in tool_msgs[0]["content"]
    result = _result(events)
    assert result.metadata["tool_steps"] == 1
    assert result.metadata["rounds"] == 2
    # Only the finish round's text is the persisted answer.
    assert result.metadata["response"] == "Found what was needed."


@pytest.mark.asyncio
async def test_midloop_llm_failure_salvages_turn_with_forced_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mid-loop LLM failure (e.g. a timeout) after useful work must not nuke
    the turn — it is salvaged with a forced finish, not propagated."""

    class _FailingThenFinishClient:
        def __init__(self) -> None:
            self.call_count = 0
            self.calls: list[dict[str, Any]] = []
            parent = self

            class _Completions:
                async def create(self, **kwargs):
                    parent.call_count += 1
                    parent.calls.append({**kwargs, "messages": list(kwargs.get("messages") or [])})
                    if parent.call_count == 1:
                        return _async_llm_stream(
                            [
                                _llm_chunk(content="Searching."),
                                _llm_chunk(
                                    tool_calls=[
                                        {
                                            "id": "call-1",
                                            "name": "web_search",
                                            "arguments": json.dumps({"query": "q"}),
                                        }
                                    ]
                                ),
                            ]
                        )
                    if parent.call_count == 2:
                        raise TimeoutError("Request timed out.")
                    return _async_llm_stream([_llm_chunk(content="Best-effort answer.")])

            class _Chat:
                def __init__(self) -> None:
                    self.completions = _Completions()

            self.chat = _Chat()

    registry = _Registry()
    client = _FailingThenFinishClient()
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(pipeline, "_compose_enabled_tools", lambda _context: ["web_search"])
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    events = await _run(
        pipeline,
        UnifiedContext(session_id="s1", user_message="Look up", enabled_tools=["web_search"]),
    )

    # 1 tool round + 1 failed round + 1 forced-finish call = 3 create() calls.
    assert client.call_count == 3
    # The turn produced an answer instead of failing.
    result = _result(events)
    assert result.metadata["response"] == "Best-effort answer."
    # The forced-finish warning explains the salvage.
    progress = [
        e.content
        for e in events
        if e.type == StreamEventType.PROGRESS and "A step failed" in str(e.content or "")
    ]
    assert progress, "expected the loop_error_finish notice to be emitted"


@pytest.mark.asyncio
async def test_first_round_llm_failure_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure on the very first round (no work gathered yet) has nothing to
    salvage and propagates so the orchestrator surfaces the error."""

    class _AlwaysFailClient:
        def __init__(self) -> None:
            class _Completions:
                async def create(self, **kwargs):
                    raise TimeoutError("Request timed out.")

            class _Chat:
                def __init__(self) -> None:
                    self.completions = _Completions()

            self.chat = _Chat()

    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = _Registry()
    monkeypatch.setattr(pipeline, "_compose_enabled_tools", lambda _context: ["web_search"])
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: _AlwaysFailClient())

    bus = StreamBus()
    _events, consumer = await _collect_bus_events(bus)
    with pytest.raises(TimeoutError):
        await pipeline.run(
            UnifiedContext(session_id="s1", user_message="x", enabled_tools=["web_search"]),
            bus,
        )
    await bus.close()
    await consumer


@pytest.mark.asyncio
async def test_context_checkpoint_folds_completed_tool_rounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _CheckpointRegistry(_Registry):
        async def execute(self, name: str, **kwargs):
            self.executed.append({"name": name, "kwargs": kwargs})
            query = str(kwargs.get("query") or "")
            return ToolResult(
                content=f"noisy tool result for {query}",
                success=True,
                metadata={"_context_checkpoint": {"summary": f"checkpoint: {query}"}},
            )

    registry = _CheckpointRegistry()
    client = _ScriptedChatClient(
        [
            [
                _llm_chunk(content="Searching step one."),
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-1",
                            "name": "web_search",
                            "arguments": json.dumps({"query": "step one"}),
                        }
                    ]
                ),
            ],
            [
                _llm_chunk(content="Searching step two."),
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-2",
                            "name": "web_search",
                            "arguments": json.dumps({"query": "step two"}),
                        }
                    ]
                ),
            ],
            [_llm_chunk(content="Final from checkpoints.")],
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(pipeline, "_compose_enabled_tools", lambda _context: ["web_search"])
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    events = await _run(
        pipeline,
        UnifiedContext(
            session_id="s1",
            user_message="Research this",
            enabled_tools=["web_search"],
        ),
    )

    assert client.call_count == 3
    second_round = client.calls[1]["messages"]
    assert any(
        m.get("role") == "system" and "checkpoint: step one" in str(m.get("content"))
        for m in second_round
    )
    assert not any(m.get("role") == "tool" for m in second_round)
    assert not any("Searching step one." in str(m.get("content")) for m in second_round)
    third_round = client.calls[2]["messages"]
    checkpoint_text = "\n".join(
        str(m.get("content") or "") for m in third_round if m.get("role") == "system"
    )
    assert "checkpoint: step one" in checkpoint_text
    assert "checkpoint: step two" in checkpoint_text
    assert not any(m.get("role") == "tool" for m in third_round)
    assert not any("noisy tool result" in str(m.get("content")) for m in third_round)
    result = _result(events)
    assert result.metadata["response"] == "Final from checkpoints."


@pytest.mark.asyncio
async def test_ask_user_available_every_round(monkeypatch: pytest.MonkeyPatch) -> None:
    """The single loop offers the full tool belt — including ask_user — on
    every round; there is no respond stage that narrows tools to ask_user."""
    registry = _Registry()
    client = _ScriptedChatClient([[_llm_chunk(content="Final answer.")]])
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(
        pipeline, "_compose_enabled_tools", lambda _context: ["web_search", "ask_user"]
    )
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    await _run(
        pipeline,
        UnifiedContext(
            session_id="s1",
            user_message="Quick question",
            enabled_tools=["web_search", "ask_user"],
        ),
    )

    loop_tools = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert loop_tools == {"web_search", "ask_user"}


@pytest.mark.asyncio
async def test_ask_user_pause_resumes_and_streams_interleaved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _PausingRegistry(_Registry):
        async def execute(self, name: str, **kwargs):
            self.executed.append({"name": name, "kwargs": kwargs})
            if name == "ask_user":
                return ToolResult(
                    content="Asked the user.",
                    success=True,
                    pause_for_user={"questions": [{"id": "q1", "prompt": "Which topic?"}]},
                )
            return await super().execute(name, **kwargs)

    registry = _PausingRegistry()
    client = _ScriptedChatClient(
        [
            # Round 1: a clarification (narration text + ask_user tool call).
            [
                _llm_chunk(content="Let me check one thing."),
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-1",
                            "name": "ask_user",
                            "arguments": json.dumps(
                                {"questions": [{"id": "q1", "prompt": "Which topic?"}]}
                            ),
                        }
                    ]
                ),
            ],
            # Round 2 finishes after the user's reply resumes the loop.
            [_llm_chunk(content="The answer.")],
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(pipeline, "_compose_enabled_tools", lambda _context: ["ask_user"])
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    async def _waiter():
        return {"text": "Topic A"}

    events = await _run(
        pipeline,
        UnifiedContext(
            session_id="s1",
            user_message="Quick question",
            enabled_tools=["ask_user"],
            metadata={"wait_for_user_reply": _waiter},
        ),
    )

    assert client.call_count == 2
    assert _contents(events) == ["Let me check one thing.", "The answer."]
    assert _call_roles(events) == ["narration", "finish"]
    # The reply was substituted into the role=tool message in-protocol.
    final_round = client.calls[-1]["messages"]
    tool_msgs = [m for m in final_round if m.get("role") == "tool"]
    assert tool_msgs and "Topic A" in tool_msgs[-1]["content"]
    result = _result(events)
    # The persisted answer is the finish round's text.
    assert result.metadata["response"] == "The answer."
    assert result.metadata["completed"] is True


@pytest.mark.asyncio
async def test_unresolved_ask_user_halts_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    class _PausingRegistry(_Registry):
        async def execute(self, name: str, **kwargs):
            self.executed.append({"name": name, "kwargs": kwargs})
            return ToolResult(
                content="Asked the user.",
                success=True,
                pause_for_user={"questions": [{"id": "q1", "prompt": "Which topic?"}]},
            )

    registry = _PausingRegistry()
    client = _ScriptedChatClient(
        [
            [
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-1",
                            "name": "ask_user",
                            "arguments": json.dumps({"questions": []}),
                        }
                    ]
                ),
            ],
            # No further scripted responses: with no wait_for_user_reply waiter
            # the loop must halt here instead of producing another answer.
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(pipeline, "_compose_enabled_tools", lambda _context: ["ask_user"])
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    events = await _run(
        pipeline,
        UnifiedContext(session_id="s1", user_message="Help me study", enabled_tools=["ask_user"]),
    )

    assert client.call_count == 1
    assert _contents(events) == ["Which topic?"]
    result = _result(events)
    assert result.metadata["completed"] is False


@pytest.mark.asyncio
async def test_mastery_plain_text_choice_is_repaired_into_quiz_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _MasteryRegistry(_Registry):
        def build_openai_schemas(self, _enabled):
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "mastery_quiz",
                        "description": "Register quiz",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "knowledge_point_id": {"type": "string"},
                                "question": {"type": "string"},
                                "expected_answer": {"type": "string"},
                                "question_type": {"type": "string"},
                                "options": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": [
                                "knowledge_point_id",
                                "question",
                                "expected_answer",
                            ],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "ask_user",
                        "description": "Ask the user",
                        "parameters": {
                            "type": "object",
                            "properties": {"questions": {"type": "array"}},
                            "required": ["questions"],
                        },
                    },
                },
            ]

        async def execute(self, name: str, **kwargs):
            self.executed.append({"name": name, "kwargs": kwargs})
            if name == "ask_user":
                return ToolResult(
                    content="Asked the user.",
                    success=True,
                    pause_for_user={
                        "questions": [
                            {
                                "id": "q1",
                                "prompt": "Which AWS concept isolates data centers?",
                                "options": [
                                    {"label": "A", "description": "Edge Location"},
                                    {"label": "B", "description": "Availability Zone"},
                                ],
                            }
                        ]
                    },
                )
            return ToolResult(content="registered", success=True)

    registry = _MasteryRegistry()
    plain_choice = (
        "Quick check:\n\n"
        "Question: Which AWS component is an isolated set of data centers?\n\n"
        "A) Edge Location\n"
        "B) Availability Zone\n"
        "C) Global Namespace\n"
        "D) Service Tier"
    )
    client = _ScriptedChatClient(
        [
            [_llm_chunk(content=plain_choice)],
            [
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-quiz",
                            "name": "mastery_quiz",
                            "arguments": json.dumps(
                                {
                                    "knowledge_point_id": "sk-aws-clf-c02",
                                    "question": (
                                        "Which AWS component is an isolated set "
                                        "of data centers?"
                                    ),
                                    "expected_answer": "B",
                                    "question_type": "choice",
                                    "options": [
                                        "A: Edge Location",
                                        "B: Availability Zone",
                                        "C: Global Namespace",
                                        "D: Service Tier",
                                    ],
                                }
                            ),
                        },
                        {
                            "id": "call-ask",
                            "name": "ask_user",
                            "arguments": json.dumps(
                                {
                                    "questions": [
                                        {
                                            "id": "q1",
                                            "prompt": (
                                                "Which AWS component is an isolated "
                                                "set of data centers?"
                                            ),
                                            "options": [
                                                {
                                                    "label": "A",
                                                    "description": "Edge Location",
                                                },
                                                {
                                                    "label": "B",
                                                    "description": "Availability Zone",
                                                },
                                            ],
                                        }
                                    ]
                                }
                            ),
                        },
                    ]
                )
            ],
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(
        pipeline,
        "_compose_enabled_tools",
        lambda _context: ["mastery_quiz", "ask_user"],
    )
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)
    monkeypatch.setattr(
        pipeline,
        "_capability_pre_loop_seed",
        lambda context: context.metadata.setdefault("mastery_status_injected", True)
        and "### Deterministic Mastery Status\n{}",
    )

    events = await _run(
        pipeline,
        UnifiedContext(
            session_id="s1",
            user_message="teach aws",
            enabled_tools=["mastery_quiz", "ask_user"],
            metadata={"mastery_mode": True, "mastery_path_id": "csphere-aws_certification"},
        ),
    )

    assert client.call_count == 2
    repair_instruction = client.calls[1]["messages"][-1]["content"]
    assert "Register the same check with mastery_quiz" in repair_instruction
    assert "Plain-text check to convert" in repair_instruction
    assert [call["name"] for call in registry.executed] == ["mastery_quiz", "ask_user"]
    assert _call_roles(events) == ["finish", "narration"]
    result = _result(events)
    assert result.metadata["completed"] is False


@pytest.mark.asyncio
async def test_mastery_generic_menu_after_plain_choice_gets_repaired_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _PausingRegistry(_Registry):
        def build_openai_schemas(self, _enabled):
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "mastery_quiz",
                        "description": "Register quiz",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "ask_user",
                        "description": "Ask the user",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
            ]

        async def execute(self, name: str, **kwargs):
            self.executed.append({"name": name, "kwargs": kwargs})
            if name == "ask_user":
                return ToolResult(
                    content="Asked the user.",
                    success=True,
                    pause_for_user={"questions": [{"id": "q1", "prompt": "Choose"}]},
                )
            return ToolResult(content="registered", success=True)

    registry = _PausingRegistry()
    client = _ScriptedChatClient(
        [
            [
                _llm_chunk(
                    content=(
                        "Question: Which is a benefit of AWS?\n"
                        "A) No cost\nB) Pay as you go\nC) More hardware\nD) No scaling"
                    )
                )
            ],
            [
                _llm_chunk(
                    content=(
                        "Hello! What subject or topic would you like to learn about today?"
                    )
                )
            ],
            [
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-quiz",
                            "name": "mastery_quiz",
                            "arguments": json.dumps({"knowledge_point_id": "kp1"}),
                        },
                        {
                            "id": "call-ask",
                            "name": "ask_user",
                            "arguments": json.dumps({"questions": []}),
                        },
                    ]
                )
            ],
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(
        pipeline,
        "_compose_enabled_tools",
        lambda _context: ["mastery_quiz", "ask_user"],
    )
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)
    monkeypatch.setattr(
        pipeline,
        "_capability_pre_loop_seed",
        lambda context: context.metadata.setdefault("mastery_status_injected", True)
        and "### Deterministic Mastery Status\n{}",
    )

    events = await _run(
        pipeline,
        UnifiedContext(
            session_id="s1",
            user_message="learn aws one by one",
            enabled_tools=["mastery_quiz", "ask_user"],
            metadata={"mastery_mode": True, "mastery_path_id": "csphere-aws_certification"},
        ),
    )

    assert client.call_count == 3
    assert [call["name"] for call in registry.executed] == ["mastery_quiz", "ask_user"]
    result = _result(events)
    assert result.metadata["completed"] is False


@pytest.mark.asyncio
async def test_mastery_quiz_format_negotiation_is_repaired_to_default_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _PausingRegistry(_Registry):
        def build_openai_schemas(self, _enabled):
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "mastery_quiz",
                        "description": "Register quiz",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "ask_user",
                        "description": "Ask the user",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
            ]

        async def execute(self, name: str, **kwargs):
            self.executed.append({"name": name, "kwargs": kwargs})
            if name == "ask_user":
                return ToolResult(
                    content="Asked the user.",
                    success=True,
                    pause_for_user={"questions": [{"id": "q1", "prompt": "Choose"}]},
                )
            return ToolResult(content="registered", success=True)

    registry = _PausingRegistry()
    client = _ScriptedChatClient(
        [
            [
                _llm_chunk(
                    content=(
                        "Would you prefer to answer using Multiple Choice or "
                        "True/False? You can also write your own explanation."
                    )
                )
            ],
            [
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-quiz",
                            "name": "mastery_quiz",
                            "arguments": json.dumps(
                                {
                                    "knowledge_point_id": "sk-aws-clf-c02",
                                    "question": "What does elasticity mean?",
                                    "expected_answer": "B",
                                    "question_type": "choice",
                                    "options": [
                                        "A: Paying only for active resources",
                                        "B: Scaling resources based on demand",
                                    ],
                                }
                            ),
                        },
                        {
                            "id": "call-ask",
                            "name": "ask_user",
                            "arguments": json.dumps({"questions": [{"id": "q1"}]}),
                        },
                    ]
                )
            ],
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(
        pipeline,
        "_compose_enabled_tools",
        lambda _context: ["mastery_quiz", "ask_user"],
    )
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)
    monkeypatch.setattr(
        pipeline,
        "_capability_pre_loop_seed",
        lambda context: context.metadata.setdefault("mastery_status_injected", True)
        and "### Deterministic Mastery Status\n{}",
    )

    events = await _run(
        pipeline,
        UnifiedContext(
            session_id="s1",
            user_message="learn aws one by one",
            enabled_tools=["mastery_quiz", "ask_user"],
            metadata={"mastery_mode": True, "mastery_path_id": "csphere-aws_certification"},
        ),
    )

    assert client.call_count == 2
    repair_instruction = client.calls[1]["messages"][-1]["content"]
    assert "Do not ask the learner to provide it" in repair_instruction
    assert [call["name"] for call in registry.executed] == ["mastery_quiz", "ask_user"]
    assert _result(events).metadata["completed"] is False


@pytest.mark.asyncio
async def test_mastery_ask_user_without_quiz_is_repaired_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _PausingRegistry(_Registry):
        def build_openai_schemas(self, _enabled):
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "mastery_quiz",
                        "description": "Register quiz",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "ask_user",
                        "description": "Ask the user",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
            ]

        async def execute(self, name: str, **kwargs):
            self.executed.append({"name": name, "kwargs": kwargs})
            if name == "ask_user":
                return ToolResult(
                    content="Asked the user.",
                    success=True,
                    pause_for_user={"questions": [{"id": "q1", "prompt": "Choose"}]},
                )
            return ToolResult(content="registered", success=True)

    registry = _PausingRegistry()
    client = _ScriptedChatClient(
        [
            [
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-unregistered-ask",
                            "name": "ask_user",
                            "arguments": json.dumps({"questions": [{"id": "q1"}]}),
                        }
                    ]
                )
            ],
            [
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-quiz",
                            "name": "mastery_quiz",
                            "arguments": json.dumps(
                                {
                                    "knowledge_point_id": "kp1",
                                    "question": "What is elasticity?",
                                    "expected_answer": "B",
                                    "question_type": "choice",
                                    "options": [
                                        "A: Pay only for active resources",
                                        "B: Scale resources based on demand",
                                    ],
                                }
                            ),
                        },
                        {
                            "id": "call-ask",
                            "name": "ask_user",
                            "arguments": json.dumps({"questions": [{"id": "q1"}]}),
                        },
                    ]
                )
            ],
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(
        pipeline,
        "_compose_enabled_tools",
        lambda _context: ["mastery_quiz", "ask_user"],
    )
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)
    monkeypatch.setattr(
        pipeline,
        "_capability_pre_loop_seed",
        lambda context: context.metadata.setdefault("mastery_status_injected", True)
        and "### Deterministic Mastery Status\n{}",
    )

    events = await _run(
        pipeline,
        UnifiedContext(
            session_id="s1",
            user_message="learn aws one by one",
            enabled_tools=["mastery_quiz", "ask_user"],
            metadata={"mastery_mode": True, "mastery_path_id": "csphere-aws_certification"},
        ),
    )

    assert client.call_count == 2
    repair_instruction = client.calls[1]["messages"][-1]["content"]
    assert "without first registering the question with mastery_quiz" in repair_instruction
    assert [call["name"] for call in registry.executed] == ["mastery_quiz", "ask_user"]
    result = _result(events)
    assert result.metadata["completed"] is False


@pytest.mark.asyncio
async def test_mastery_answered_card_requires_grade_before_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _GradingRegistry(_Registry):
        def build_openai_schemas(self, _enabled):
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "mastery_quiz",
                        "description": "Register quiz",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "ask_user",
                        "description": "Ask the user",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "mastery_grade",
                        "description": "Grade answer",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
            ]

        async def execute(self, name: str, **kwargs):
            self.executed.append({"name": name, "kwargs": kwargs})
            if name == "ask_user":
                return ToolResult(
                    content="Asked the user.",
                    success=True,
                    pause_for_user={"questions": [{"id": "q1", "prompt": "Choose"}]},
                )
            if name == "mastery_grade":
                return ToolResult(
                    content=json.dumps({"is_correct": True, "mastered": False}),
                    success=True,
                    metadata={"mastery_grade": {"is_correct": True, "mastered": False}},
                )
            return ToolResult(content="registered", success=True)

    pending_checks = {"value": True}

    def _fake_pending(_context):
        return pending_checks["value"]

    async def _waiter():
        return {"text": "B"}

    registry = _GradingRegistry()
    client = _ScriptedChatClient(
        [
            [
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-quiz",
                            "name": "mastery_quiz",
                            "arguments": json.dumps({"knowledge_point_id": "kp1"}),
                        },
                        {
                            "id": "call-ask",
                            "name": "ask_user",
                            "arguments": json.dumps({"questions": [{"id": "q1"}]}),
                        },
                    ]
                )
            ],
            [_llm_chunk(content="Hello! What subject would you like to learn?")],
            [
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-grade",
                            "name": "mastery_grade",
                            "arguments": json.dumps({"answer": "B"}),
                        }
                    ]
                )
            ],
            [_llm_chunk(content="Correct, but let's practice once more.")],
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(
        pipeline,
        "_compose_enabled_tools",
        lambda _context: ["mastery_quiz", "ask_user", "mastery_grade"],
    )
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)
    monkeypatch.setattr(
        "cognispheretutor.agents.chat.agent_loop._has_pending_mastery_question",
        _fake_pending,
    )

    events = await _run(
        pipeline,
        UnifiedContext(
            session_id="s1",
            user_message="learn aws one by one",
            enabled_tools=["mastery_quiz", "ask_user", "mastery_grade"],
            metadata={
                "mastery_mode": True,
                "mastery_path_id": "csphere-aws_certification",
                "wait_for_user_reply": _waiter,
            },
        ),
    )

    assert client.call_count == 4
    repair_instruction = client.calls[2]["messages"][-1]["content"]
    assert "You must grade that answer" in repair_instruction
    assert [call["name"] for call in registry.executed] == [
        "mastery_quiz",
        "ask_user",
        "mastery_grade",
    ]
    result = _result(events)
    assert result.metadata["completed"] is True
    assert result.metadata["response"].startswith("Correct, but let's practice once more.")


@pytest.mark.asyncio
async def test_mastery_blocks_back_to_back_quiz_after_mastered_grade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _PostGradeRegistry(_Registry):
        def build_openai_schemas(self, _enabled):
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "mastery_grade",
                        "description": "Grade answer",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "mastery_quiz",
                        "description": "Register quiz",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
            ]

        async def execute(self, name: str, **kwargs):
            self.executed.append({"name": name, "kwargs": kwargs})
            if name == "mastery_grade":
                return ToolResult(
                    content=json.dumps({"is_correct": True, "mastered": True}),
                    success=True,
                    metadata={"mastery_grade": {"is_correct": True, "mastered": True}},
                )
            return ToolResult(content="registered", success=True)

    registry = _PostGradeRegistry()
    client = _ScriptedChatClient(
        [
            [
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-grade",
                            "name": "mastery_grade",
                            "arguments": json.dumps({"answer": "A"}),
                        }
                    ]
                )
            ],
            [
                _llm_chunk(
                    content="Correct. Next question:",
                    tool_calls=[
                        {
                            "id": "call-next-quiz",
                            "name": "mastery_quiz",
                            "arguments": json.dumps({"knowledge_point_id": "kp2"}),
                        }
                    ],
                )
            ],
            [
                _llm_chunk(
                    content=(
                        "Great, that check is cleared. Now let's actually learn the next "
                        "objective before another question. In AWS, this next idea means "
                        "understanding what the service is responsible for and what you, "
                        "as the customer, still control. For example, AWS operates the "
                        "cloud infrastructure, but you configure your own workloads, "
                        "identity rules, and data choices. The key idea is that cloud "
                        "learning is not just memorizing service names; it is learning "
                        "where responsibility sits and why that changes design decisions."
                    )
                )
            ],
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(
        pipeline,
        "_compose_enabled_tools",
        lambda _context: ["mastery_grade", "mastery_quiz"],
    )
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    events = await _run(
        pipeline,
        UnifiedContext(
            session_id="s1",
            user_message="A",
            enabled_tools=["mastery_grade", "mastery_quiz"],
            metadata={"mastery_mode": True, "mastery_path_id": "csphere-aws_certification"},
        ),
    )

    assert client.call_count == 3
    repair_instruction = client.calls[2]["messages"][-1]["content"]
    assert "attempted to register the next quiz before teaching" in repair_instruction
    assert [call["name"] for call in registry.executed] == ["mastery_grade"]
    result = _result(events)
    assert result.metadata["completed"] is True
    assert "actually learn the next objective" in result.metadata["response"]


@pytest.mark.asyncio
async def test_mastery_blocks_say_continue_after_mastered_grade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _PostGradeRegistry(_Registry):
        def build_openai_schemas(self, _enabled):
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "mastery_grade",
                        "description": "Grade answer",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ]

        async def execute(self, name: str, **kwargs):
            self.executed.append({"name": name, "kwargs": kwargs})
            return ToolResult(
                content=json.dumps(
                    {
                        "is_correct": True,
                        "mastered": True,
                        "next": {
                            "knowledge_point_id": "observability-golden-signals",
                            "title": "Observability and golden signals",
                        },
                    }
                ),
                success=True,
                metadata={
                    "mastery_grade": {
                        "is_correct": True,
                        "mastered": True,
                        "next": {
                            "knowledge_point_id": "observability-golden-signals",
                            "title": "Observability and golden signals",
                        },
                    }
                },
            )

    registry = _PostGradeRegistry()
    client = _ScriptedChatClient(
        [
            [
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-grade",
                            "name": "mastery_grade",
                            "arguments": json.dumps({"answer": "B"}),
                        }
                    ]
                )
            ],
            [
                _llm_chunk(
                    content=(
                        "Runtime readiness is now mastered. Ready to continue "
                        "when you are - just say continue."
                    )
                )
            ],
            [
                _llm_chunk(
                    content=(
                        "Runtime readiness is cleared. Next up: Observability "
                        "and golden signals. In this objective, you learn how "
                        "to tell whether a running AI infrastructure service is "
                        "healthy from evidence instead of vibes. The four golden "
                        "signals are latency, traffic, errors, and saturation. "
                        "Together they help you separate a slow model endpoint, "
                        "an overloaded runtime, and a request failure pattern."
                    )
                )
            ],
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(
        pipeline,
        "_compose_enabled_tools",
        lambda _context: ["mastery_grade"],
    )
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    events = await _run(
        pipeline,
        UnifiedContext(
            session_id="s1",
            user_message="B",
            enabled_tools=["mastery_grade"],
            metadata={"mastery_mode": True, "mastery_path_id": "csphere-ai_infra"},
        ),
    )

    assert client.call_count == 3
    repair_instruction = client.calls[2]["messages"][-1]["content"]
    assert "asked the learner to say continue" in repair_instruction
    assert [call["name"] for call in registry.executed] == ["mastery_grade"]
    result = _result(events)
    assert result.metadata["completed"] is True
    assert "Next up: Observability" in result.metadata["response"]
    assert "say continue" not in result.metadata["response"]


@pytest.mark.asyncio
async def test_inline_dsml_mastery_grade_executes_without_leaking_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _GradeRegistry(_Registry):
        def build_openai_schemas(self, _enabled):
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "mastery_grade",
                        "description": "Grade answer",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ]

        async def execute(self, name: str, **kwargs):
            self.executed.append({"name": name, "kwargs": kwargs})
            return ToolResult(
                content=json.dumps({"is_correct": True, "mastered": True}),
                success=True,
                metadata={"mastery_grade": {"is_correct": True, "mastered": True}},
            )

    registry = _GradeRegistry()
    dsml_grade = (
        "<｜｜DSML｜｜tool_calls> "
        "<｜｜DSML｜｜invoke name=\"mastery_grade\"> "
        "<｜｜DSML｜｜parameter name=\"answer\" string=\"true\">B</｜｜DSML｜｜parameter> "
        "</｜｜DSML｜｜invoke> "
        "</｜｜DSML｜｜tool_calls>"
    )
    client = _ScriptedChatClient(
        [
            [
                _llm_chunk(content="Let me register the final check.\n"),
                _llm_chunk(content=dsml_grade),
            ],
            [
                _llm_chunk(
                    content=(
                        "Correct. Observability and golden signals is mastered. "
                        "Next up: MiniMind reference workload boundaries."
                    )
                )
            ],
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(pipeline, "_compose_enabled_tools", lambda _context: ["mastery_grade"])
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    events = await _run(
        pipeline,
        UnifiedContext(
            session_id="s1",
            user_message="B",
            enabled_tools=["mastery_grade"],
            metadata={"mastery_mode": True, "mastery_path_id": "csphere-ai_infra"},
        ),
    )

    assert client.call_count == 2
    assert [call["name"] for call in registry.executed] == ["mastery_grade"]
    assert registry.executed[0]["kwargs"]["answer"] == "B"
    visible = "".join(_contents(events))
    assert "DSML" not in visible
    assert "mastery_grade" not in visible
    result = _result(events)
    assert result.metadata["completed"] is True
    assert "DSML" not in result.metadata["response"]
    assert "Next up: MiniMind reference workload boundaries" in result.metadata["response"]


@pytest.mark.asyncio
async def test_round_budget_forces_tool_less_finish(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _Registry()
    client = _ScriptedChatClient(
        [
            [
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-1",
                            "name": "web_search",
                            "arguments": json.dumps({"query": "step one"}),
                        }
                    ]
                ),
            ],
            [_llm_chunk(content="Best effort answer.")],
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    pipeline._max_rounds = 1
    monkeypatch.setattr(pipeline, "_compose_enabled_tools", lambda _context: ["web_search"])
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    events = await _run(
        pipeline,
        UnifiedContext(session_id="s1", user_message="Research this", enabled_tools=["web_search"]),
    )

    assert client.call_count == 2
    # The forced finish round disables tools and tells the model to answer now.
    assert "tools" not in client.calls[-1]
    forced_instruction = client.calls[-1]["messages"][-1]["content"]
    assert "round budget ran out" in forced_instruction
    result = _result(events)
    assert result.metadata["response"] == "Best effort answer."
    assert result.metadata["completed"] is True


def test_compose_enabled_tools_injects_rag_when_kb_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "cognispheretutor.services.memory.get_memory_store",
        lambda: SimpleNamespace(read_raw=lambda *_args, **_kwargs: ""),
    )
    monkeypatch.setattr(
        "cognispheretutor.services.notebook.get_notebook_manager",
        lambda: SimpleNamespace(list_notebooks=lambda: []),
    )
    pipeline = AgenticChatPipeline.__new__(AgenticChatPipeline)
    pipeline._deferred_loader = None
    pipeline._exec_enabled = False
    pipeline.registry = SimpleNamespace(
        get_enabled=lambda selected: [SimpleNamespace(name=n) for n in selected]
    )
    context = UnifiedContext(
        user_message="hi",
        enabled_tools=["web_search"],
        knowledge_bases=["kb-a"],
    )
    assert "rag" in pipeline._compose_enabled_tools(context)
    assert "web_search" in pipeline._compose_enabled_tools(context)


def test_compose_enabled_tools_mounts_mastery_plugin_only_in_mastery_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "cognispheretutor.services.memory.get_memory_store",
        lambda: SimpleNamespace(read_raw=lambda *_args, **_kwargs: ""),
    )
    monkeypatch.setattr(
        "cognispheretutor.services.notebook.get_notebook_manager",
        lambda: SimpleNamespace(list_notebooks=lambda: []),
    )
    pipeline = AgenticChatPipeline.__new__(AgenticChatPipeline)
    pipeline._deferred_loader = None
    pipeline._exec_enabled = False
    pipeline.registry = SimpleNamespace(
        get_enabled=lambda selected: [SimpleNamespace(name=n) for n in selected]
    )

    ordinary = UnifiedContext(user_message="hi")
    mastery = UnifiedContext(
        user_message="teach me",
        metadata={"mastery_mode": True, "mastery_path_id": "path-a"},
    )

    ordinary_tools = pipeline._compose_enabled_tools(ordinary)
    mastery_tools = pipeline._compose_enabled_tools(mastery)
    assert not set(MASTERY_TOOL_NAMES).intersection(ordinary_tools)
    assert set(MASTERY_TOOL_NAMES).issubset(mastery_tools)
    # Additive plugin surface: a mastery turn reuses chat's full built-in
    # surface (always-on defaults included) and just adds its owned tools.
    assert {"web_fetch", "github", "cron"}.issubset(mastery_tools)
    assert {"web_fetch", "github", "cron"}.issubset(ordinary_tools)


def test_augment_tool_kwargs_injects_mastery_path_id() -> None:
    pipeline = AgenticChatPipeline.__new__(AgenticChatPipeline)
    context = UnifiedContext(
        user_message="teach",
        metadata={
            "mastery_mode": True,
            "mastery_path_id": "book-1",
            "mastery_start_point": "apprenticeship_entry",
        },
    )

    augmented = pipeline._augment_tool_kwargs("mastery_status", {}, context)

    assert augmented["_mastery_path_id"] == "book-1"
    assert augmented["_mastery_start_point"] == "apprenticeship_entry"


def test_mastery_path_id_resolves_from_config_override() -> None:
    from cognispheretutor.capabilities.mastery.capability import resolve_mastery_path_id

    context = UnifiedContext(
        session_id="chat-session-1",
        config_overrides={"mastery_path_id": "csphere-aws_certification"},
    )

    assert resolve_mastery_path_id(context) == "csphere-aws_certification"


def test_legacy_aws_unified_path_resolves_to_plugin_path(monkeypatch) -> None:
    from cognispheretutor.capabilities.mastery import capability as mastery_capability
    from cognispheretutor.learning.models import (
        KnowledgePoint,
        KnowledgeType,
        LearningModule,
        LearningProgress,
    )

    progress = LearningProgress(
        book_id="unified_aws",
        modules=[
            LearningModule(
                id="m1",
                name="AWS Certification Overview",
                order=0,
                knowledge_points=[
                    KnowledgePoint(
                        id="kp1",
                        name="Cloud Practitioner CLF-C02",
                        type=KnowledgeType.CONCEPT,
                        module_id="m1",
                    )
                ],
            )
        ],
    )

    class FakeStore:
        def load(self, book_id: str):
            return progress if book_id == "unified_aws" else None

        def exists(self, book_id: str) -> bool:
            return book_id == "csphere-aws_certification"

    monkeypatch.setattr(mastery_capability, "LearningStore", FakeStore)
    context = UnifiedContext(session_id="unified_aws")

    assert mastery_capability.resolve_mastery_path_id(context) == "csphere-aws_certification"


def test_source_provenance_marks_plugin_web_and_rag() -> None:
    from cognispheretutor.agents.chat.agent_loop import (
        AgentLoopState,
        _source_provenance_for_turn,
    )

    context = UnifiedContext(
        user_message="teach aws",
        metadata={"mastery_path_id": "csphere-aws_certification"},
    )
    state = AgentLoopState(
        tools_used=["mastery_status", "web_search", "rag"],
        sources=[{"title": "doc"}],
    )

    provenance = _source_provenance_for_turn(context, state)

    assert provenance["sources"] == [
        "local plugin pack",
        "Cognisphere materialized",
        "web_search",
        "Knowledge/RAG",
        "model wording",
    ]
    assert provenance["visible_label"] == (
        "Source: local plugin pack, Cognisphere materialized, web_search, Knowledge/RAG, model wording"
    )


def test_source_provenance_does_not_mark_plugin_without_grounding() -> None:
    from cognispheretutor.agents.chat.agent_loop import (
        AgentLoopState,
        _source_provenance_for_turn,
    )

    context = UnifiedContext(
        user_message="teach aws",
        metadata={"mastery_mode": True, "mastery_path_id": "csphere-aws_certification"},
    )
    state = AgentLoopState()

    provenance = _source_provenance_for_turn(context, state)

    assert provenance["sources"] == ["model"]
    assert provenance["visible_label"] == "Source: model"


def test_mastery_loop_pre_loop_seed_injects_deterministic_status(monkeypatch) -> None:
    from cognispheretutor.capabilities.mastery import loop as mastery_loop

    monkeypatch.setattr(mastery_loop, "_auto_advance_overview_if_ready", lambda _context: "")
    monkeypatch.setattr(
        mastery_loop,
        "_deterministic_mastery_status",
        lambda _context: "### Deterministic Mastery Status\n{}",
    )
    monkeypatch.setattr(
        mastery_loop,
        "_deterministic_plugin_grounding",
        lambda _context: "### Cognisphere Plugin Graph Grounding\n{}",
    )
    monkeypatch.setattr(
        mastery_loop,
        "_deterministic_lesson_contract",
        lambda _context: "### Mastery Lesson Contract\n{}",
    )
    context = UnifiedContext(
        user_message="teach aws",
        metadata={"mastery_mode": True, "mastery_path_id": "csphere-aws_certification"},
    )

    seed = mastery_loop.MasteryLoopCapability().pre_loop_seed(context)

    assert "Deterministic Mastery Status" in seed
    assert "Cognisphere Plugin Graph Grounding" in seed
    assert "Mastery Lesson Contract" in seed
    assert "Mastery Turn Directive" in seed
    assert "do not finish with a menu" in seed
    assert context.metadata["mastery_status_injected"] is True
    assert context.metadata["plugin_graph_grounding_injected"] is True
    assert context.metadata["mastery_lesson_contract_injected"] is True


def test_mastery_loop_pre_loop_seed_guards_orphan_choice_answer(monkeypatch) -> None:
    from cognispheretutor.capabilities.mastery import loop as mastery_loop

    monkeypatch.setattr(mastery_loop, "_auto_advance_overview_if_ready", lambda _context: "")
    monkeypatch.setattr(
        mastery_loop,
        "_deterministic_mastery_status",
        lambda _context: "### Deterministic Mastery Status\n{}",
    )
    monkeypatch.setattr(mastery_loop, "_deterministic_plugin_grounding", lambda _context: "")
    monkeypatch.setattr(mastery_loop, "_deterministic_lesson_contract", lambda _context: "")

    class FakeService:
        def __init__(self, _store):
            pass

        def get_or_create(self, _path_id):
            return object()

    class FakeStep:
        def to_dict(self):
            return {
                "action": "probe",
                "knowledge_point_id": "sk-aws-clf-c02",
                "knowledge_point_name": "Cloud Practitioner",
            }

    monkeypatch.setattr("cognispheretutor.learning.service.LearningService", FakeService)
    monkeypatch.setattr(
        "cognispheretutor.learning.policy.next_objective",
        lambda _progress: FakeStep(),
    )

    context = UnifiedContext(
        user_message="A",
        metadata={"mastery_mode": True, "mastery_path_id": "csphere-aws_certification"},
    )

    seed = mastery_loop.MasteryLoopCapability().pre_loop_seed(context)

    assert "Mastery Orphan Quiz Answer Guard" in seed
    assert "orphan_quiz_answer" in seed
    assert "Do not advance to the next lesson" in seed
    assert "mastery_quiz" in seed
    assert "ask_user" in seed


def test_mastery_loop_extracts_choice_answer_from_chat_text() -> None:
    from cognispheretutor.capabilities.mastery import loop as mastery_loop

    assert mastery_loop._extract_quiz_answer(
        "the answer for the above question is A, then continue the next class"
    ) == "A"
    assert mastery_loop._extract_quiz_answer("option b is my answer") == "B"
    assert mastery_loop._extract_quiz_answer("answer is true") == "true"


def test_mastery_loop_pre_loop_seed_grades_pending_text_answer(monkeypatch) -> None:
    from cognispheretutor.capabilities.mastery import loop as mastery_loop

    monkeypatch.setattr(mastery_loop, "_auto_advance_overview_if_ready", lambda _context: "")
    monkeypatch.setattr(
        mastery_loop,
        "_deterministic_mastery_status",
        lambda _context: "### Deterministic Mastery Status\n{}",
    )
    monkeypatch.setattr(mastery_loop, "_deterministic_plugin_grounding", lambda _context: "")
    monkeypatch.setattr(mastery_loop, "_deterministic_lesson_contract", lambda _context: "")

    class FakeService:
        def __init__(self, _store):
            pass

        def get_or_create(self, _path_id):
            return object()

    class FakeStep:
        def to_dict(self):
            return {
                "action": "answer_pending",
                "knowledge_point_id": "sk-aws-clf-c02",
                "knowledge_point_name": "Cloud Practitioner",
                "pending_prompt": "Which option is correct?",
            }

    monkeypatch.setattr("cognispheretutor.learning.service.LearningService", FakeService)
    monkeypatch.setattr(
        "cognispheretutor.learning.policy.next_objective",
        lambda _progress: FakeStep(),
    )

    context = UnifiedContext(
        user_message="the answer for the above question is A, then continue the next class",
        metadata={"mastery_mode": True, "mastery_path_id": "csphere-aws_certification"},
    )

    seed = mastery_loop.MasteryLoopCapability().pre_loop_seed(context)

    assert "Mastery Pending Text Answer Guard" in seed
    assert "pending_text_answer" in seed
    assert "answer='A'" in seed
    assert "Do not ask the learner to answer the same question again" in seed


def test_mastery_loop_clears_unpresented_pending_after_failed_turn(tmp_path, monkeypatch) -> None:
    import sqlite3

    from cognispheretutor.capabilities.mastery import loop as mastery_loop
    from cognispheretutor.learning.models import LearningProgress, PendingQuestion
    import cognispheretutor.learning.storage as storage_mod

    real_store_cls = storage_mod.LearningStore
    store = real_store_cls(tmp_path / "learning")
    progress = LearningProgress(
        book_id="csphere-aws_certification",
        pending_question=PendingQuestion(
            question_id="q-hidden",
            knowledge_point_id="sk-aws-clf-c02",
            prompt="Hidden question",
            expected_answer="B",
            created_at=20.0,
        ),
    )
    store.save(progress)
    monkeypatch.setattr(storage_mod, "LearningStore", lambda: real_store_cls(tmp_path / "learning"))

    db_path = tmp_path / "chat_history.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE messages (session_id TEXT, role TEXT, created_at REAL)"
        )
        conn.execute(
            "CREATE TABLE turns (session_id TEXT, status TEXT, error TEXT, created_at REAL)"
        )
        conn.execute(
            "INSERT INTO messages VALUES (?, ?, ?)",
            ("unified_1", "assistant", 10.0),
        )
        conn.execute(
            "INSERT INTO turns VALUES (?, ?, ?, ?)",
            ("unified_1", "failed", "Turn interrupted by server restart.", 30.0),
        )

    class FakePathService:
        def get_chat_history_db(self):
            return db_path

    monkeypatch.setattr(
        "cognispheretutor.services.path_service.get_path_service",
        lambda: FakePathService(),
    )
    context = UnifiedContext(
        session_id="unified_1",
        user_message="continue",
        metadata={"mastery_mode": True, "mastery_path_id": "csphere-aws_certification"},
    )

    seed = mastery_loop._clear_unpresented_pending_after_failed_turn(context)
    updated = store.load("csphere-aws_certification")

    assert "Mastery Stale Pending Cleanup" in seed
    assert updated is not None
    assert updated.pending_question is None


def test_mastery_overview_auto_advance_records_qualitative_pass(tmp_path, monkeypatch) -> None:
    from cognispheretutor.capabilities.mastery import loop as mastery_loop
    from cognispheretutor.learning.models import (
        KnowledgePoint,
        KnowledgeType,
        LearningModule,
        LearningProgress,
    )
    import cognispheretutor.learning.storage as storage_mod

    real_store_cls = storage_mod.LearningStore
    store = real_store_cls(tmp_path)
    progress = LearningProgress(
        book_id="csphere-demo",
        modules=[
            LearningModule(
                id="csphere-demo-overview",
                name="Cognisphere · demo",
                order=0,
                knowledge_points=[
                    KnowledgePoint(
                        id="ov-overview",
                        name="Cognisphere · demo",
                        type=KnowledgeType.CONCEPT,
                        module_id="csphere-demo-overview",
                    )
                ],
            ),
            LearningModule(
                id="csphere-demo-objectives",
                name="Learning objectives",
                order=1,
                knowledge_points=[
                    KnowledgePoint(
                        id="obj-first",
                        name="First real content",
                        type=KnowledgeType.CONCEPT,
                        module_id="csphere-demo-objectives",
                    )
                ],
            ),
        ],
        knowledge_types={
            "ov-overview": KnowledgeType.CONCEPT,
            "obj-first": KnowledgeType.CONCEPT,
        },
    )
    store.save(progress)
    monkeypatch.setattr(storage_mod, "LearningStore", lambda: real_store_cls(tmp_path))
    context = UnifiedContext(
        user_message="the direction how to pass the exam",
        metadata={"mastery_mode": True, "mastery_path_id": "csphere-demo"},
    )

    seed = mastery_loop._auto_advance_overview_if_ready(context)
    updated = store.load("csphere-demo")

    assert "Mastery Auto Advance" in seed
    assert updated.qualitative_mastery["ov-overview"] is True
    assert "First real content" in seed
    assert context.metadata["mastery_overview_auto_advanced"] is True


def test_formal_course_overview_is_not_auto_advanced(tmp_path, monkeypatch) -> None:
    from cognispheretutor.capabilities.mastery import loop as mastery_loop
    from cognispheretutor.learning.models import (
        KnowledgePoint,
        KnowledgeType,
        LearningModule,
        LearningProgress,
    )
    import cognispheretutor.learning.storage as storage_mod

    real_store_cls = storage_mod.LearningStore
    store = real_store_cls(tmp_path)
    progress = LearningProgress(
        book_id="csphere-ai_infra",
        modules=[
            LearningModule(
                id="csphere-ai_infra-overview",
                name="AI Infrastructure Knowledge Platform and Digital Twin Course",
                order=0,
                knowledge_points=[
                    KnowledgePoint(
                        id="ov-ai_infra-course_overview-v1",
                        name="AI Infrastructure Knowledge Platform and Digital Twin Course",
                        type=KnowledgeType.CONCEPT,
                        module_id="csphere-ai_infra-overview",
                    )
                ],
            ),
            LearningModule(
                id="csphere-ai_infra-objectives",
                name="Learning objectives",
                order=1,
                knowledge_points=[
                    KnowledgePoint(
                        id="obj-runtime-readiness",
                        name="Runtime readiness",
                        type=KnowledgeType.CONCEPT,
                        module_id="csphere-ai_infra-objectives",
                    )
                ],
            ),
        ],
        knowledge_types={
            "ov-ai_infra-course_overview-v1": KnowledgeType.CONCEPT,
            "obj-runtime-readiness": KnowledgeType.CONCEPT,
        },
    )
    store.save(progress)
    monkeypatch.setattr(storage_mod, "LearningStore", lambda: real_store_cls(tmp_path))
    context = UnifiedContext(
        user_message="I understand the direction and want the systematic path.",
        metadata={"mastery_mode": True, "mastery_path_id": "csphere-ai_infra"},
    )

    seed = mastery_loop._auto_advance_overview_if_ready(context)
    updated = store.load("csphere-ai_infra")

    assert seed == ""
    assert updated is not None
    assert "ov-ai_infra-course_overview-v1" not in updated.qualitative_mastery
    assert "mastery_overview_auto_advanced" not in context.metadata


def test_augment_tool_kwargs_injects_geogebra_image() -> None:
    pipeline = AgenticChatPipeline.__new__(AgenticChatPipeline)
    pipeline.language = "zh"
    context = UnifiedContext(
        user_message="solve this triangle",
        attachments=[
            Attachment(
                type="image",
                base64="REAL_IMG_BYTES",
                filename="problem.png",
                mime_type="image/png",
            ),
        ],
        language="zh",
    )

    augmented = pipeline._augment_tool_kwargs(
        "geogebra_analysis",
        {"image_base64": "HALLUCINATED"},
        context,
    )

    assert augmented["image_base64"] == "data:image/png;base64,REAL_IMG_BYTES"
    assert augmented["language"] == "zh"


def test_build_llm_tool_schemas_kb_name_enum_matches_attached() -> None:
    pipeline = AgenticChatPipeline.__new__(AgenticChatPipeline)
    pipeline.registry = _Registry()

    schemas = pipeline._build_llm_tool_schemas(
        ["web_search"],
        UnifiedContext(knowledge_bases=["kb-a", "kb-b"]),
    )

    assert schemas[0]["function"]["parameters"]["additionalProperties"] is False
