"""Single-loop chat agent.

One chat turn = ONE agent loop over a single growing conversation:

* each round is one LLM call; its text streams to the user as a ``content``
  block, and its tool calls are dispatched with their ``role=tool`` results
  appended back into the conversation;
* a round that DOES call tools is "narration" — its text is a preamble to
  the tool work — and the loop continues;
* a round that calls NO tools is the ``finish``: its text IS the final
  user-facing answer and the loop ends (the model deciding it is done; a
  first round without tool calls is the "no exploration needed" fast path);
* if the round budget runs out while tools are still being requested, one
  final tool-less ``finish`` round is forced.

``ask_user`` pauses the turn for a reply and resumes in-protocol; an
unresolved pause (or a terminator tool) halts the turn.

There is no separate respond pass and no text destination has to be guessed
mid-stream: every round's text streams to the user as it is generated, and a
``call_role`` (``narration`` vs ``finish``) emitted when the round completes
tells the frontend how to render that round's text.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
import json
import logging
import re
from typing import TYPE_CHECKING, Any

from cognispheretutor.agents._shared.capability_result import emit_capability_result
from cognispheretutor.core.agentic.messages import assistant_message_with_tool_calls
from cognispheretutor.core.agentic.tool_dispatch import DispatchOutcome
from cognispheretutor.core.agentic.usage import message_content_chars, record_streamed_usage
from cognispheretutor.core.context import UnifiedContext
from cognispheretutor.core.stream_bus import StreamBus
from cognispheretutor.core.trace import build_trace_metadata, merge_trace_metadata, new_call_id
from cognispheretutor.services.llm import clean_thinking_tags
from cognispheretutor.services.llm.multimodal import (
    should_degrade_to_text,
    strip_image_parts_inplace,
)
from cognispheretutor.services.llm.request_compat import (
    is_image_input_unsupported,
    is_stream_options_unsupported,
    is_tool_schema_unsupported,
)

if TYPE_CHECKING:  # pragma: no cover
    from cognispheretutor.agents.chat.agentic_pipeline import AgenticChatPipeline

logger = logging.getLogger(__name__)

# The loop runs over a single conversation; this is the maximum number of
# tool-calling rounds before a tool-less finish is forced. The model normally
# exits earlier by replying without tool calls.
LOOP_STAGE = "responding"

_THINK_OPEN_RE = re.compile(r"<\s*think(?:ing)?\b[^>]*>", re.IGNORECASE)
_THINK_CLOSE_RE = re.compile(r"<\s*/\s*think(?:ing)?\s*>", re.IGNORECASE)
# Longest partial tag worth waiting a chunk for (e.g. "</thinking" + slack).
_TAG_HOLDBACK_CHARS = 24
_DSML_TOOL_OPEN_RE = re.compile(r"<\s*[|｜]{2}\s*DSML\s*[|｜]{2}\s*tool_calls\s*>", re.IGNORECASE)
_DSML_TOOL_CLOSE_RE = re.compile(r"<\s*/\s*[|｜]{2}\s*DSML\s*[|｜]{2}\s*tool_calls\s*>", re.IGNORECASE)
_DSML_TOOL_BLOCK_RE = re.compile(
    r"<\s*[|｜]{2}\s*DSML\s*[|｜]{2}\s*tool_calls\s*>.*?"
    r"<\s*/\s*[|｜]{2}\s*DSML\s*[|｜]{2}\s*tool_calls\s*>",
    re.IGNORECASE | re.DOTALL,
)
_DSML_INVOKE_RE = re.compile(
    r"<\s*[|｜]{2}\s*DSML\s*[|｜]{2}\s*invoke\s+name=[\"'](?P<name>[^\"']+)[\"']\s*>"
    r"(?P<body>.*?)"
    r"<\s*/\s*[|｜]{2}\s*DSML\s*[|｜]{2}\s*invoke\s*>",
    re.IGNORECASE | re.DOTALL,
)
_DSML_PARAMETER_RE = re.compile(
    r"<\s*[|｜]{2}\s*DSML\s*[|｜]{2}\s*parameter\s+name=[\"'](?P<name>[^\"']+)[\"'][^>]*>"
    r"(?P<value>.*?)"
    r"<\s*/\s*[|｜]{2}\s*DSML\s*[|｜]{2}\s*parameter\s*>",
    re.IGNORECASE | re.DOTALL,
)


class InlineThinkFilter:
    """Incremental ``<think>``/``<thinking>`` splitter for streamed content.

    Some providers surface reasoning inline in the *content* channel (instead
    of ``reasoning_content``), wrapped in think tags. Splitting at streaming
    time keeps the user-facing content channel clean everywhere downstream —
    the live bubble, the persisted message, and the loop's finish detection —
    in one place. The raw text (tags included) still goes back into the LLM
    conversation untouched.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._in_think = False

    def feed(self, chunk: str) -> list[tuple[str, str]]:
        """Consume *chunk*; return ``(kind, text)`` segments, kind in
        ``{"content", "thinking"}``. May hold back a partial trailing tag
        until the next chunk (``flush`` releases it at stream end)."""
        self._buffer += chunk
        segments: list[tuple[str, str]] = []
        while True:
            pattern = _THINK_CLOSE_RE if self._in_think else _THINK_OPEN_RE
            match = pattern.search(self._buffer)
            if match is None:
                break
            if match.start() > 0:
                segments.append((self._kind(), self._buffer[: match.start()]))
            self._buffer = self._buffer[match.end() :]
            self._in_think = not self._in_think
        emit_upto = len(self._buffer)
        tag_start = self._buffer.rfind("<")
        if (
            tag_start != -1
            and len(self._buffer) - tag_start <= _TAG_HOLDBACK_CHARS
            and ">" not in self._buffer[tag_start:]
        ):
            emit_upto = tag_start
        if emit_upto > 0:
            segments.append((self._kind(), self._buffer[:emit_upto]))
            self._buffer = self._buffer[emit_upto:]
        return segments

    def flush(self) -> list[tuple[str, str]]:
        """Release whatever is still buffered (stream ended)."""
        if not self._buffer:
            return []
        segments = [(self._kind(), self._buffer)]
        self._buffer = ""
        return segments

    def _kind(self) -> str:
        return "thinking" if self._in_think else "content"


class InlineToolMarkupFilter:
    """Incremental filter for provider-emitted inline DSML tool blocks."""

    def __init__(self) -> None:
        self._buffer = ""
        self._in_tool_markup = False

    def feed(self, chunk: str) -> list[str]:
        self._buffer += chunk
        segments: list[str] = []
        while True:
            pattern = _DSML_TOOL_CLOSE_RE if self._in_tool_markup else _DSML_TOOL_OPEN_RE
            match = pattern.search(self._buffer)
            if match is None:
                break
            if not self._in_tool_markup and match.start() > 0:
                segments.append(self._buffer[: match.start()])
            self._buffer = self._buffer[match.end() :]
            self._in_tool_markup = not self._in_tool_markup
        if self._in_tool_markup:
            return segments
        emit_upto = len(self._buffer)
        tag_start = self._buffer.rfind("<")
        if tag_start != -1 and len(self._buffer) - tag_start <= _TAG_HOLDBACK_CHARS:
            tail = self._buffer[tag_start:]
            if _looks_like_partial_dsml_tool_open(tail):
                emit_upto = tag_start
        if emit_upto > 0:
            segments.append(self._buffer[:emit_upto])
            self._buffer = self._buffer[emit_upto:]
        return segments

    def flush(self) -> list[str]:
        if not self._buffer:
            return []
        if self._in_tool_markup or _DSML_TOOL_OPEN_RE.search(self._buffer):
            self._buffer = ""
            self._in_tool_markup = False
            return []
        segments = [self._buffer]
        self._buffer = ""
        return segments


def _looks_like_partial_dsml_tool_open(text: str) -> bool:
    compact = re.sub(r"\s+", "", text).lower().replace("｜", "|")
    return "<||dsml||tool_calls>".startswith(compact)


@dataclass(slots=True)
class AgentLoopState:
    """Turn-level counters shared across the loop's rounds."""

    rounds: int = 0
    tool_steps: int = 0
    tools_used: list[str] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    mastery_gate_cleared: bool = False


@dataclass(slots=True)
class LLMCallResult:
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = ""


@dataclass(slots=True)
class LoopOutcome:
    """Result of running the turn's loop.

    ``final_text`` is the user-facing answer (the finish round's text, or a
    terminator tool's content). ``completed`` is False only when the turn
    halted on an unresolved ``ask_user`` pause — the pending question is then
    the turn's final artefact.
    """

    final_text: str = ""
    completed: bool = False


class AgentLoop:
    """Run one chat turn as a single agent loop over one conversation."""

    def __init__(
        self,
        *,
        pipeline: "AgenticChatPipeline",
        context: UnifiedContext,
        stream: StreamBus,
        client: Any,
        enabled_tools: list[str],
        tool_schemas: list[dict[str, Any]] | None,
    ) -> None:
        self.pipeline = pipeline
        self.context = context
        self.stream = stream
        self.client = client
        self.enabled_tools = enabled_tools
        self.tool_schemas = tool_schemas

    async def run(self) -> None:
        state = AgentLoopState()
        # Optional async pre-pass briefings (e.g. explore_context) run BEFORE
        # the answer stage so they form their own preceding activity group and
        # their grounding can ride in the loop's user-message seed.
        capability_briefing = await self.pipeline._capability_pre_loop_briefings(
            self.context, self.stream
        )
        async with self.stream.stage(LOOP_STAGE, source="chat"):
            seed_block = await self.pipeline._retrieve_kb_seed_block(self.context, self.stream)
            capability_seed = self.pipeline._capability_pre_loop_seed(self.context)
            seed_block = "\n\n".join(
                block
                for block in (
                    seed_block.strip(),
                    capability_seed.strip(),
                    capability_briefing.strip(),
                )
                if block
            )
            messages = self.pipeline._build_loop_messages(
                context=self.context,
                enabled_tools=self.enabled_tools,
                kb_seed=seed_block,
                include_tool_manifest=bool(self.tool_schemas),
            )
            outcome = await self._run_loop(
                messages=messages,
                state=state,
                checkpoint_boundary=len(messages),
            )

        if state.sources:
            await self.stream.sources(
                state.sources,
                source="chat",
                stage=LOOP_STAGE,
                metadata={"trace_kind": "sources"},
            )
        source_provenance = _source_provenance_for_turn(self.context, state)
        if source_provenance.get("visible_label"):
            marker = f"\n\n{source_provenance['visible_label']}"
            await self.stream.content(
                marker,
                source="chat",
                stage=LOOP_STAGE,
                metadata={
                    "trace_kind": "source_provenance",
                    "source_provenance": source_provenance,
                },
            )
            outcome.final_text = f"{outcome.final_text.rstrip()}{marker}"
        await emit_capability_result(
            self.stream,
            {
                "response": outcome.final_text,
                "completed": outcome.completed,
                "engine": "agent_loop",
                "rounds": state.rounds,
                "tool_steps": state.tool_steps,
                "metadata": {"source_provenance": source_provenance},
            },
            source="chat",
            usage=self.pipeline.usage,
        )

    def _clean(self, text: str) -> str:
        return clean_thinking_tags(text, self.pipeline.binding, self.pipeline.model).strip()

    # ---- agent loop --------------------------------------------------------

    async def _run_loop(
        self,
        *,
        messages: list[dict[str, Any]],
        state: AgentLoopState,
        checkpoint_boundary: int,
    ) -> LoopOutcome:
        """Run rounds of one LLM call + tool dispatch over *messages*.

        A round with tool calls keeps its assistant message (text + tool
        calls) and the ``role=tool`` results in-conversation, then continues.
        A round with no tool calls is the finish: its text — already streamed
        to the user — is the answer, and the loop ends.
        """
        explore_label = self.pipeline._t("labels.exploring", default="Exploring")
        nudged_empty_finish = False
        mastery_quiz_repair_attempts = 0
        mastery_ask_registration_repair_attempts = 0
        mastery_grade_repair_attempts = 0
        mastery_post_grade_lesson_repair_attempts = 0
        mastery_continue_wait_repair_attempts = 0
        for _round in range(max(1, self.pipeline.effective_max_rounds(self.context))):
            try:
                result = await self._call_llm(
                    messages=messages,
                    label=explore_label,
                    call_kind="agent_loop_round",
                    trace_role="explore",
                    max_tokens=self.pipeline.loop_max_tokens,
                    tool_schemas=self.tool_schemas,
                )
            except Exception as exc:
                # A mid-loop LLM failure (timeout / transient network) must not
                # discard a turn that already gathered useful work. Salvage it
                # with a forced finish; only a failure on the very first round
                # (nothing gathered yet) propagates as before.
                if state.rounds == 0:
                    raise
                logger.warning(
                    "agent loop round failed after %d round(s); forcing finish: %s",
                    state.rounds,
                    exc,
                )
                return await self._forced_finish(messages, state, reason="error")
            state.rounds += 1
            if not result.tool_calls:
                final_text = self._clean(result.text)
                if not final_text and not nudged_empty_finish:
                    # The round produced only internal reasoning (e.g. the
                    # whole reply inside <think>) — the model planned but
                    # never acted. Keep its raw text in-conversation (the
                    # plan/script lives there) and nudge it once to act
                    # instead of falling back to an empty answer.
                    nudged_empty_finish = True
                    await self.stream.progress(
                        self.pipeline._t(
                            "notices.empty_finish_nudged",
                            default=(
                                "The round produced only internal reasoning; "
                                "asked the model to continue."
                            ),
                        ),
                        source="chat",
                        stage=LOOP_STAGE,
                        metadata={"trace_kind": "warning"},
                    )
                    if result.text:
                        messages.append({"role": "assistant", "content": result.text})
                    messages.append(
                        {
                            "role": "user",
                            "content": self.pipeline._t(
                                "loop.finish_empty_nudge",
                                default=(
                                    "Your previous round produced only internal "
                                    "reasoning — no tool call and no user-facing "
                                    "answer. Continue now: either call the tools "
                                    "to execute your plan, or write the final "
                                    "user-facing answer directly."
                                ),
                            ),
                        }
                    )
                    continue
                if _needs_mastery_grade_repair(
                    context=self.context,
                    enabled_tools=self.enabled_tools,
                    tools_used=state.tools_used,
                ):
                    if mastery_grade_repair_attempts >= 2:
                        return await self._finalize_finish(
                            self.pipeline._t(
                                "notices.mastery_grade_required",
                                default=(
                                    "I need to grade the answer with mastery_grade "
                                    "before we continue. Please retry this turn so "
                                    "the mastery gate can be updated correctly."
                                ),
                            )
                        )
                    mastery_grade_repair_attempts += 1
                    await self.stream.progress(
                        self.pipeline._t(
                            "notices.mastery_grade_repaired",
                            default=(
                                "Detected an answered mastery card; asking the "
                                "model to grade it before continuing."
                            ),
                        ),
                        source="chat",
                        stage=LOOP_STAGE,
                        metadata={
                            "trace_kind": "warning",
                            "mastery_grade_repair": True,
                        },
                    )
                    messages.append({"role": "assistant", "content": result.text})
                    messages.append(
                        {
                            "role": "user",
                            "content": _mastery_grade_repair_instruction(),
                        }
                    )
                    continue
                if _needs_mastery_quiz_card_repair(
                    context=self.context,
                    final_text=final_text,
                    enabled_tools=self.enabled_tools,
                    tools_used=state.tools_used,
                ):
                    if mastery_quiz_repair_attempts >= 2:
                        return await self._finalize_finish(
                            self.pipeline._t(
                                "notices.mastery_quiz_card_required",
                                default=(
                                    "I need to present this check as an interactive "
                                    "mastery card before we continue. Please retry this "
                                    "turn; I will register the question with mastery_quiz "
                                    "and ask_user instead of moving to the next lesson."
                                ),
                            )
                        )
                    mastery_quiz_repair_attempts += 1
                    await self.stream.progress(
                        self.pipeline._t(
                            "notices.mastery_plain_quiz_repaired",
                            default=(
                                "Detected a mastery quiz written as plain text; "
                                "asking the model to register an interactive card."
                            ),
                        ),
                        source="chat",
                        stage=LOOP_STAGE,
                        metadata={
                            "trace_kind": "warning",
                            "mastery_plain_quiz_repair": True,
                        },
                    )
                    messages.append({"role": "assistant", "content": result.text})
                    messages.append(
                        {
                            "role": "user",
                            "content": _mastery_quiz_card_repair_instruction(final_text),
                        }
                    )
                    continue
                if _needs_mastery_continue_wait_repair(
                    context=self.context,
                    final_text=final_text,
                    gate_cleared_this_turn=state.mastery_gate_cleared,
                ):
                    if mastery_continue_wait_repair_attempts >= 2:
                        return await self._finalize_finish(final_text)
                    mastery_continue_wait_repair_attempts += 1
                    await self.stream.progress(
                        self.pipeline._t(
                            "notices.mastery_continue_wait_repaired",
                            default=(
                                "Detected a mastered objective ending with a "
                                "manual continue prompt; asking the model to "
                                "continue the ordered learning flow."
                            ),
                        ),
                        source="chat",
                        stage=LOOP_STAGE,
                        metadata={
                            "trace_kind": "warning",
                            "mastery_continue_wait_repair": True,
                        },
                    )
                    messages.append({"role": "assistant", "content": result.text})
                    messages.append(
                        {
                            "role": "user",
                            "content": _mastery_continue_wait_instruction(),
                        }
                    )
                    continue
                # Finish: the text streamed live this round IS the answer.
                return await self._finalize_finish(final_text)

            if _needs_mastery_ask_user_registration_repair(
                context=self.context,
                tool_calls=result.tool_calls,
                enabled_tools=self.enabled_tools,
                tools_used=state.tools_used,
            ):
                if mastery_ask_registration_repair_attempts >= 2:
                    return await self._finalize_finish(
                        self.pipeline._t(
                            "notices.mastery_quiz_card_required",
                            default=(
                                "I need to present this check as an interactive "
                                "mastery card before we continue. Please retry this "
                                "turn; I will register the question with mastery_quiz "
                                "and ask_user instead of moving to the next lesson."
                            ),
                        )
                    )
                mastery_ask_registration_repair_attempts += 1
                await self.stream.progress(
                    self.pipeline._t(
                        "notices.mastery_ask_user_without_quiz_repaired",
                        default=(
                            "Detected an unregistered mastery card; asking the "
                            "model to register mastery_quiz before ask_user."
                        ),
                    ),
                    source="chat",
                    stage=LOOP_STAGE,
                    metadata={
                        "trace_kind": "warning",
                        "mastery_ask_user_registration_repair": True,
                    },
                )
                messages.append(
                    {
                        "role": "assistant",
                        "content": result.text
                        or "I attempted to show an interactive mastery check.",
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": _mastery_ask_user_registration_repair_instruction(),
                    }
                )
                continue

            if _needs_mastery_post_grade_lesson_repair(
                context=self.context,
                tool_calls=result.tool_calls,
                enabled_tools=self.enabled_tools,
                gate_cleared_this_turn=state.mastery_gate_cleared,
                pre_tool_text=result.text,
            ):
                if mastery_post_grade_lesson_repair_attempts >= 2:
                    return await self._finalize_finish(
                        self.pipeline._t(
                            "notices.mastery_lesson_before_quiz_required",
                            default=(
                                "We just cleared a mastery check. I should teach "
                                "the next mini-lesson before asking another quiz. "
                                "Please retry this turn so the learning flow can "
                                "continue in lesson-first order."
                            ),
                        )
                    )
                mastery_post_grade_lesson_repair_attempts += 1
                await self.stream.progress(
                    self.pipeline._t(
                        "notices.mastery_lesson_before_quiz_repaired",
                        default=(
                            "Detected a next quiz before the next mini-lesson; "
                            "asking the model to teach first."
                        ),
                    ),
                    source="chat",
                    stage=LOOP_STAGE,
                    metadata={
                        "trace_kind": "warning",
                        "mastery_lesson_before_quiz_repair": True,
                    },
                )
                messages.append(
                    {
                        "role": "assistant",
                        "content": result.text
                        or "I attempted to start the next mastery check immediately.",
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": _mastery_lesson_before_quiz_instruction(),
                    }
                )
                continue

            messages.append(assistant_message_with_tool_calls(result.text, result.tool_calls))
            dispatch = await self.pipeline._dispatch_tool_calls(
                tool_calls=result.tool_calls,
                context=self.context,
                stream=self.stream,
                iteration_index=state.tool_steps,
                stage=LOOP_STAGE,
            )
            state.tool_steps += 1
            if _dispatch_cleared_mastery_gate(dispatch):
                state.mastery_gate_cleared = True
            state.tools_used.extend(
                tool_name
                for tool_name in (
                    str(call.get("function", {}).get("name") or call.get("name") or "").strip()
                    for call in result.tool_calls
                )
                if tool_name
            )
            state.sources.extend(dispatch.sources)
            messages.extend(dispatch.tool_messages)

            if dispatch.pause:
                resumed = await self.pipeline._await_user_reply_and_resolve(
                    context=self.context,
                    stream=self.stream,
                    dispatch=dispatch,
                )
                if not resumed:
                    # The pending question is already the turn's final
                    # artefact (or the user abandoned the turn) — stop.
                    return LoopOutcome(final_text="", completed=False)
                # The user's answers were substituted into the matching
                # ``role=tool`` message; the next round sees them in-protocol.
                continue

            checkpoint_boundary = self._fold_context_checkpoint(
                messages=messages,
                dispatch=dispatch,
                checkpoint_boundary=checkpoint_boundary,
            )

            if dispatch.terminate:
                payload = dispatch.terminate_payload or {}
                await self.pipeline._emit_terminator_final_response(self.stream, payload)
                return LoopOutcome(
                    final_text=str(payload.get("content") or ""),
                    completed=True,
                )

        # Round budget ran out while still requesting tools — force a finish.
        return await self._forced_finish(messages, state)

    def _fold_context_checkpoint(
        self,
        *,
        messages: list[dict[str, Any]],
        dispatch: DispatchOutcome,
        checkpoint_boundary: int,
    ) -> int:
        summary = _last_context_checkpoint_summary(dispatch)
        if not summary:
            return checkpoint_boundary
        prefix = messages[:checkpoint_boundary]
        prefix.append(
            {
                "role": "system",
                "content": f"[Context checkpoint]\n{summary}",
            }
        )
        messages[:] = prefix
        return len(messages)

    async def _forced_finish(
        self,
        messages: list[dict[str, Any]],
        state: AgentLoopState,
        *,
        reason: str = "budget",
    ) -> LoopOutcome:
        if reason == "error":
            notice = self.pipeline._t(
                "notices.loop_error_finish",
                default="A step failed; answering with what has been gathered.",
            )
        else:
            notice = self.pipeline._t(
                "notices.loop_budget_exhausted",
                default="Exploration budget reached; answering with what has been gathered.",
            )
        await self.stream.progress(
            notice,
            source="chat",
            stage=LOOP_STAGE,
            metadata={"trace_kind": "warning"},
        )
        messages.append({"role": "user", "content": self.pipeline._finish_exhausted_instruction()})
        try:
            result = await self._call_llm(
                messages=messages,
                label=self.pipeline._t("labels.final_response", default="Final response"),
                call_kind="llm_final_response",
                trace_role="response",
                max_tokens=self.pipeline.loop_max_tokens,
                tool_schemas=None,  # tools disabled so the model must finish
            )
        except Exception as exc:
            # The salvage call itself failed (e.g. the provider is still
            # stalling). Don't bubble up and lose the turn — emit the graceful
            # fallback answer instead.
            logger.warning("forced-finish LLM call failed: %s", exc)
            return await self._finalize_finish("")
        state.rounds += 1
        return await self._finalize_finish(result.text)

    async def _finalize_finish(self, raw_text: str) -> LoopOutcome:
        final_text = self._clean(raw_text)
        if not final_text:
            # The finish round produced no usable text; nothing streamed to
            # the user, so emit a fallback answer here.
            final_text = self.pipeline._t(
                "notices.empty_final_response",
                default=(
                    "I could not produce a useful response from the model "
                    "output. Please try again or narrow the request."
                ),
            )
            await self.pipeline._emit_protocol_fallback_final_response(self.stream, final_text)
        return LoopOutcome(final_text=final_text, completed=True)

    # ---- LLM call ----------------------------------------------------------

    async def _call_llm(
        self,
        *,
        messages: list[dict[str, Any]],
        label: str,
        call_kind: str,
        trace_role: str,
        max_tokens: int,
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> LLMCallResult:
        await self.pipeline._guard_context_window(messages, self.stream)
        stage = LOOP_STAGE
        call_id = new_call_id(f"chat-{stage}")
        trace_meta = build_trace_metadata(
            call_id=call_id,
            phase=stage,
            label=label,
            call_kind=call_kind,
            trace_id=call_id,
            trace_role=trace_role,
            trace_group="stage",
        )
        await self.stream.progress(
            label,
            source="chat",
            stage=stage,
            metadata=merge_trace_metadata(
                trace_meta,
                {"trace_kind": "call_status", "call_state": "running"},
            ),
        )

        kwargs: dict[str, Any] = {
            "model": self.pipeline.model,
            "messages": messages,
            "stream": True,
            **self.pipeline._completion_kwargs(max_tokens=max_tokens),
        }
        if self.pipeline.usage is not None:
            kwargs["stream_options"] = {"include_usage": True}
        if tool_schemas:
            kwargs["tools"] = tool_schemas
            kwargs["tool_choice"] = "auto"

        # Providers (esp. Gemini OpenAI-compat) may attach ``usage`` to more
        # than one stream chunk. Keep the latest frame; it is recorded once
        # after the stream via ``record_streamed_usage``.
        usage_seen: Any = None
        text_parts: list[str] = []
        tool_acc: dict[int, dict[str, str]] = {}
        output_chars = 0
        finish_reason = ""
        think_filter = InlineThinkFilter()
        tool_markup_filter = InlineToolMarkupFilter()
        chunk_meta = merge_trace_metadata(trace_meta, {"trace_kind": "llm_chunk"})

        async def _emit_segments(segments: list[tuple[str, str]]) -> None:
            for kind, segment in segments:
                if kind == "content":
                    await self.stream.content(
                        segment, source="chat", stage=stage, metadata=chunk_meta
                    )
                else:
                    await self.stream.thinking(
                        segment, source="chat", stage=stage, metadata=chunk_meta
                    )

        response_stream = await self._create_response_stream(kwargs, trace_meta, stage)
        try:
            async for chunk in response_stream:
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    usage_seen = usage
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                choice = choices[0]
                if getattr(choice, "finish_reason", None):
                    finish_reason = str(choice.finish_reason)
                delta = getattr(choice, "delta", None)
                if delta is None:
                    continue

                reasoning_text = getattr(delta, "reasoning_content", None) or getattr(
                    delta,
                    "reasoning",
                    None,
                )
                if reasoning_text:
                    output_chars += len(reasoning_text)
                    await self.stream.thinking(
                        reasoning_text, source="chat", stage=stage, metadata=chunk_meta
                    )

                content = getattr(delta, "content", None)
                if content:
                    output_chars += len(content)
                    text_parts.append(content)
                    # Every round's text streams to the user; the round's
                    # call_role (emitted at completion) tells the frontend
                    # whether to render it as narration or as the answer.
                    # Inline <think> segments are split off to the thinking
                    # channel so the content stream stays user-facing.
                    for visible_content in tool_markup_filter.feed(content):
                        await _emit_segments(think_filter.feed(visible_content))

                for tc_delta in getattr(delta, "tool_calls", None) or []:
                    index = int(getattr(tc_delta, "index", 0) or 0)
                    acc = tool_acc.setdefault(index, {"id": "", "name": "", "arguments": ""})
                    tcid = getattr(tc_delta, "id", None)
                    if tcid:
                        acc["id"] += str(tcid)
                    fn = getattr(tc_delta, "function", None)
                    if fn is None:
                        continue
                    name = getattr(fn, "name", None)
                    arguments = getattr(fn, "arguments", None)
                    if name:
                        acc["name"] += str(name)
                        output_chars += len(str(name))
                    if arguments:
                        acc["arguments"] += str(arguments)
                        output_chars += len(str(arguments))
        finally:
            close = getattr(response_stream, "close", None)
            if callable(close):
                with suppress(Exception):
                    await close()

        for visible_content in tool_markup_filter.flush():
            await _emit_segments(think_filter.feed(visible_content))
        await _emit_segments(think_filter.flush())
        text = "".join(text_parts)
        record_streamed_usage(
            self.pipeline.usage,
            usage_seen,
            input_chars=sum(message_content_chars(message) for message in messages),
            output_chars=output_chars,
        )

        tool_calls = [
            {
                "id": data.get("id") or f"call_{idx}",
                "name": data.get("name", ""),
                "arguments": data.get("arguments") or "{}",
            }
            for idx, data in sorted(tool_acc.items())
            if data.get("name")
        ]
        inline_tool_calls = _parse_inline_tool_markup(text)
        if inline_tool_calls:
            tool_calls.extend(inline_tool_calls)
            text = _strip_inline_tool_markup(text)

        await self.stream.progress(
            "",
            source="chat",
            stage=stage,
            metadata=merge_trace_metadata(
                trace_meta,
                {
                    "trace_kind": "call_status",
                    "call_state": "complete",
                    # A round with tool calls is narration; a tool-less round
                    # is the finish whose text is the user-facing answer.
                    "call_role": "narration" if tool_calls else "finish",
                },
            ),
        )
        return LLMCallResult(text=text, tool_calls=tool_calls, finish_reason=finish_reason)

    async def _create_response_stream(
        self,
        kwargs: dict[str, Any],
        trace_meta: dict[str, Any],
        stage: str,
    ) -> Any:
        try:
            return await self.client.chat.completions.create(**kwargs)
        except Exception as exc:
            if "stream_options" in kwargs and is_stream_options_unsupported(exc):
                retry_kwargs = dict(kwargs)
                retry_kwargs.pop("stream_options", None)
                return await self.client.chat.completions.create(**retry_kwargs)
            if kwargs.get("tools") and is_tool_schema_unsupported(exc):
                await self.stream.progress(
                    self.pipeline._t(
                        "notices.tool_schema_fallback",
                        default="Provider rejected native tool schemas; retrying without tools.",
                    ),
                    source="chat",
                    stage=stage,
                    metadata=merge_trace_metadata(
                        trace_meta,
                        {"trace_kind": "warning", "tool_schema_fallback": True},
                    ),
                )
                retry_kwargs = dict(kwargs)
                retry_kwargs.pop("tools", None)
                retry_kwargs.pop("tool_choice", None)
                self.tool_schemas = None
                return await self.client.chat.completions.create(**retry_kwargs)
            if is_image_input_unsupported(exc) and should_degrade_to_text(
                self.pipeline.binding,
                self.pipeline.model,
                kwargs.get("messages") or [],
            ):
                strip_image_parts_inplace(kwargs["messages"])
                await self.stream.progress(
                    self.pipeline._t(
                        "notices.image_fallback",
                        default="Model does not support image input; retrying without images.",
                    ),
                    source="chat",
                    stage=stage,
                    metadata=merge_trace_metadata(
                        trace_meta,
                        {"trace_kind": "warning", "image_fallback": True},
                    ),
                )
                return await self.client.chat.completions.create(**kwargs)
            raise


def _last_context_checkpoint_summary(dispatch: DispatchOutcome) -> str:
    summary = ""
    for tool_message in dispatch.tool_messages:
        tool_call_id = str(tool_message.get("tool_call_id") or "")
        metadata = dispatch.tool_metadata_by_id.get(tool_call_id) or {}
        checkpoint = metadata.get("_context_checkpoint")
        if not isinstance(checkpoint, dict):
            continue
        candidate = str(checkpoint.get("summary") or "").strip()
        if candidate:
            summary = candidate
    return summary


def _source_provenance_for_turn(
    context: UnifiedContext,
    state: AgentLoopState,
) -> dict[str, Any]:
    """Classify the visible source basis for the final answer."""
    path_id = str(context.metadata.get("mastery_path_id") or "").strip()
    tools = [tool for tool in state.tools_used if tool]
    sources: list[str] = []
    used_mastery_grounding = (
        bool(context.metadata.get("mastery_status_injected"))
        or bool(context.metadata.get("plugin_graph_grounding_injected"))
        or any(tool.startswith("mastery_") for tool in tools)
    )
    if path_id.startswith("csphere-") and used_mastery_grounding:
        sources.extend(["local plugin pack", "Cognisphere materialized"])
    if any(tool == "web_search" for tool in tools):
        sources.append("web_search")
    if state.sources or any(tool in {"rag", "read_source"} for tool in tools):
        sources.append("Knowledge/RAG")
    if not sources:
        sources.append("model")
    elif context.metadata.get("mastery_mode") or path_id.startswith("csphere-"):
        sources.append("model wording")
    deduped = list(dict.fromkeys(sources))
    show_visible_label = bool(context.metadata.get("mastery_mode")) or path_id.startswith(
        "csphere-"
    )
    return {
        "sources": deduped,
        "mastery_path_id": path_id or None,
        "tools_used": tools,
        "visible_label": f"Source: {', '.join(deduped)}" if show_visible_label else "",
    }


_PLAIN_CHOICE_OPTION_RE = re.compile(r"(?im)^\s*(?:[-*]\s*)?([A-D])[\).:：]\s+\S+")
_PLAIN_TRUE_FALSE_RE = re.compile(
    r"(?i)\b(true\s*/\s*false|true or false|判断题|正确还是错误)\b"
)
_GENERIC_LEARNING_MENU_RE = re.compile(
    r"(?i)\b(what subject|what topic|would you like to learn|tell me what .*learn)\b"
    r"|想学.*什么|学习.*主题"
)
_QUIZ_FORMAT_NEGOTIATION_RE = re.compile(
    r"(?i)\b(would you prefer|do you prefer|prefer to answer|choose .*format|"
    r"multiple choice.*true\s*/\s*false|true\s*/\s*false.*multiple choice|"
    r"provide .*knowledge point|provide .*question|provide .*options)\b"
    r"|是否.*(选择题|判断题|自由回答)|选择.*(题型|形式)|请.*提供.*(题目|选项|知识点)"
)
_SENTENCE_BOUNDARY_RE = re.compile(r"[.!?。！？]\s+|[。！？]")


def _tool_call_names(tool_calls: list[dict[str, Any]]) -> set[str]:
    return {
        str(call.get("function", {}).get("name") or call.get("name") or "").strip()
        for call in tool_calls
    }


def _strip_inline_tool_markup(text: str) -> str:
    return _DSML_TOOL_BLOCK_RE.sub("", str(text or "")).strip()


def _parse_inline_tool_markup(text: str) -> list[dict[str, str]]:
    tool_calls: list[dict[str, str]] = []
    for block_match in _DSML_TOOL_BLOCK_RE.finditer(str(text or "")):
        block = block_match.group(0)
        for invoke_match in _DSML_INVOKE_RE.finditer(block):
            args: dict[str, str] = {}
            body = invoke_match.group("body") or ""
            for param_match in _DSML_PARAMETER_RE.finditer(body):
                value = re.sub(r"\s+", " ", param_match.group("value") or "").strip()
                args[param_match.group("name")] = value
            tool_calls.append(
                {
                    "id": f"inline_dsml_{len(tool_calls)}",
                    "name": invoke_match.group("name"),
                    "arguments": json.dumps(args, ensure_ascii=False),
                }
            )
    return tool_calls


def _needs_mastery_quiz_card_repair(
    *,
    context: UnifiedContext,
    final_text: str,
    enabled_tools: list[str],
    tools_used: list[str],
) -> bool:
    if not context.metadata.get("mastery_mode"):
        return False
    if "mastery_quiz" not in enabled_tools or "ask_user" not in enabled_tools:
        return False
    if any(tool in {"mastery_quiz", "ask_user", "mastery_grade"} for tool in tools_used):
        return False
    text = str(final_text or "").strip()
    if not text:
        return False
    option_labels = {match.group(1).upper() for match in _PLAIN_CHOICE_OPTION_RE.finditer(text)}
    has_choice_check = len(option_labels) >= 2 and bool(
        re.search(r"(?i)\b(question|quiz|select|choose|which|what)\b|问题|选择", text)
    )
    return bool(
        has_choice_check
        or _PLAIN_TRUE_FALSE_RE.search(text)
        or _GENERIC_LEARNING_MENU_RE.search(text)
        or _QUIZ_FORMAT_NEGOTIATION_RE.search(text)
    )


def _needs_mastery_ask_user_registration_repair(
    *,
    context: UnifiedContext,
    tool_calls: list[dict[str, Any]],
    enabled_tools: list[str],
    tools_used: list[str],
) -> bool:
    if not context.metadata.get("mastery_mode"):
        return False
    if "mastery_quiz" not in enabled_tools or "ask_user" not in enabled_tools:
        return False
    call_names = _tool_call_names(tool_calls)
    if "ask_user" not in call_names:
        return False
    if "mastery_quiz" in call_names or "mastery_grade" in call_names:
        return False
    if any(tool in {"mastery_quiz", "mastery_grade"} for tool in tools_used):
        return False
    return True


def _needs_mastery_grade_repair(
    *,
    context: UnifiedContext,
    enabled_tools: list[str],
    tools_used: list[str],
) -> bool:
    if not context.metadata.get("mastery_mode"):
        return False
    if "mastery_grade" not in enabled_tools:
        return False
    if "ask_user" not in tools_used:
        return False
    if "mastery_grade" in tools_used:
        return False
    return _has_pending_mastery_question(context)


def _needs_mastery_post_grade_lesson_repair(
    *,
    context: UnifiedContext,
    tool_calls: list[dict[str, Any]],
    enabled_tools: list[str],
    gate_cleared_this_turn: bool,
    pre_tool_text: str,
) -> bool:
    if not context.metadata.get("mastery_mode"):
        return False
    if not gate_cleared_this_turn:
        return False
    if "mastery_quiz" not in enabled_tools:
        return False
    if "mastery_quiz" not in _tool_call_names(tool_calls):
        return False
    return not _looks_like_mini_lesson(pre_tool_text)


def _needs_mastery_continue_wait_repair(
    *,
    context: UnifiedContext,
    final_text: str,
    gate_cleared_this_turn: bool,
) -> bool:
    if not context.metadata.get("mastery_mode"):
        return False
    if not gate_cleared_this_turn:
        return False
    text = re.sub(r"\s+", " ", str(final_text or "")).strip().lower()
    if not text:
        return False
    wait_patterns = (
        "say continue",
        "type continue",
        "ready to continue",
        "continue when you are",
        "when you're ready",
        "when you are ready",
        "just say continue",
        "reply continue",
        "回复继续",
        "输入继续",
        "说继续",
        "准备好后继续",
        "准备好了再继续",
    )
    return any(pattern in text for pattern in wait_patterns)


def _looks_like_mini_lesson(text: str) -> bool:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(compact) < 420:
        return False
    sentence_count = len([part for part in _SENTENCE_BOUNDARY_RE.split(compact) if part.strip()])
    has_structure = bool(re.search(r"(?m)^\s*(#{1,3}\s+|[-*]\s+|\d+[.)]\s+)", text))
    has_teaching_signal = bool(
        re.search(
            r"(?i)\b(means|because|for example|think of|key idea|in aws|"
            r"lesson|mini-lesson|what|why|how)\b|例如|意思是|关键|为什么|怎么|课程|学习",
            compact,
        )
    )
    return sentence_count >= 3 and (has_structure or has_teaching_signal)


def _dispatch_cleared_mastery_gate(dispatch: DispatchOutcome) -> bool:
    for meta in dispatch.tool_metadata_by_id.values():
        grade = meta.get("mastery_grade") if isinstance(meta, dict) else None
        if isinstance(grade, dict) and grade.get("mastered") is True:
            return True
    return False


def _has_pending_mastery_question(context: UnifiedContext) -> bool:
    path_id = str(context.metadata.get("mastery_path_id") or "").strip()
    if not path_id:
        return False
    try:
        from cognispheretutor.learning.service import LearningService
        from cognispheretutor.learning.storage import LearningStore

        progress = LearningService(LearningStore()).get_or_create(path_id)
        return progress.pending_question is not None
    except Exception:
        return False


def _mastery_quiz_card_repair_instruction(final_text: str) -> str:
    excerpt = str(final_text or "").strip()
    if len(excerpt) > 1800:
        excerpt = f"{excerpt[:1800].rstrip()}..."
    return (
        "You just wrote a mastery check as plain text. That is not allowed in "
        "mastery mode because it cannot be graded deterministically.\n\n"
        "Repair this now without teaching a new lesson:\n"
        "1. Register the same check with mastery_quiz, including the current "
        "knowledge_point_id from the deterministic mastery status. Do not ask "
        "the learner to provide it.\n"
        "2. For choice questions, set question_type='choice', pass full option "
        "bodies such as ['A: ...', 'B: ...'], and set expected_answer to the "
        "correct label.\n"
        "3. Immediately present the registered question with ask_user using "
        "matching short labels A/B/C/D or True/False.\n"
        "4. Do not answer the question, do not mark mastery, and do not advance "
        "to another objective until mastery_grade runs on the learner's reply.\n\n"
        f"Plain-text check to convert:\n{excerpt}"
    )


def _mastery_grade_repair_instruction() -> str:
    return (
        "The learner has answered an ask_user mastery card and a pending "
        "mastery_quiz question exists. You must grade that answer before any "
        "new teaching or generic response.\n\n"
        "Repair this now:\n"
        "1. Read the learner's answer from the latest ask_user tool result in "
        "this conversation.\n"
        "2. Call mastery_grade with that answer verbatim.\n"
        "3. Give feedback based on mastery_grade.is_correct and mastery_grade.mastered.\n"
        "4. If mastery_grade.mastered is false, reteach the same objective briefly "
        "and ask another registered mastery_quiz + ask_user check.\n"
        "5. If mastery_grade.mastered is true, do not immediately ask another "
        "question. First teach the next objective as a real mini-lesson; only "
        "after that lesson may you register the next quick-check card."
    )


def _mastery_lesson_before_quiz_instruction() -> str:
    return (
        "You just cleared the previous mastery gate and then attempted to register "
        "the next quiz before teaching the next objective. That turns learning into "
        "a chain of questions.\n\n"
        "Repair this now:\n"
        "1. Do not call mastery_quiz or ask_user until you have taught the next "
        "objective with a substantive mini-lesson.\n"
        "2. Start from the next objective reported by mastery_grade.next or the "
        "latest mastery_status result.\n"
        "3. Teach the next objective in beginner-friendly terms using the local "
        "plugin grounding; include enough explanation, examples, and key terms "
        "for the learner to actually learn before being checked.\n"
        "4. After that mini-lesson, you may register exactly one quick multiple-"
        "choice check with mastery_quiz and present it with ask_user. If you are "
        "not ready to teach the mini-lesson, finish with the lesson only."
    )


def _mastery_continue_wait_instruction() -> str:
    return (
        "You just cleared a mastery objective, but your last answer asked the "
        "learner to say continue. In mastery mode, do not wait for a chat command "
        "when the current path already has a next objective.\n\n"
        "Repair this now:\n"
        "1. Briefly acknowledge the cleared objective.\n"
        "2. Continue in sequence to the next objective from mastery_grade.next or "
        "the latest mastery_status result.\n"
        "3. Teach that next objective as a beginner-friendly mini-lesson using "
        "the local plugin grounding.\n"
        "4. Do not ask the learner to type continue. Do not register the next "
        "quiz until after the mini-lesson."
    )


def _mastery_ask_user_registration_repair_instruction() -> str:
    return (
        "You attempted to show an ask_user card in mastery mode without first "
        "registering the question with mastery_quiz. That creates an ungradable "
        "card and is not allowed.\n\n"
        "Repair this now without teaching new content:\n"
        "1. Call mastery_quiz for the current objective from Deterministic "
        "Mastery Status. Do not ask the learner for the knowledge_point_id, "
        "question, options, or preferred quiz format.\n"
        "2. Use question_type='choice' for multiple-choice checks.\n"
        "3. Pass full option bodies like ['A: ...', 'B: ...'] and set "
        "expected_answer to the correct label.\n"
        "4. Then call ask_user with matching option labels so the learner answers "
        "on an interactive card.\n"
        "5. Do not continue to another lesson until mastery_grade grades the reply."
    )


__all__ = [
    "AgentLoop",
    "AgentLoopState",
    "InlineThinkFilter",
    "InlineToolMarkupFilter",
    "LLMCallResult",
    "LOOP_STAGE",
    "LoopOutcome",
    "_has_pending_mastery_question",
    "_needs_mastery_ask_user_registration_repair",
    "_needs_mastery_grade_repair",
    "_needs_mastery_post_grade_lesson_repair",
    "_needs_mastery_quiz_card_repair",
    "_source_provenance_for_turn",
]
