"""Deterministic lesson-first flow for Cognisphere mastery paths.

This module handles the ordinary learner action path without asking the LLM to
decide tool order: pick objective -> teach mini-lesson -> pose card -> grade.
Domain facts still come from imported/local plugin pack grounding.
"""

import asyncio
import json
import re
import time
import uuid
from typing import Any

from cognispheretutor.capabilities.mastery.tools import (
    next_objective_for_start_point,
)
from cognispheretutor.core.context import UnifiedContext
from cognispheretutor.core.stream import StreamEvent, StreamEventType
from cognispheretutor.core.stream_bus import StreamBus
from cognispheretutor.integrations.cognisphere.grounding import (
    _load_domain_items,
    _objective_query,
    _rank_items,
    _render_item,
)
from cognispheretutor.learning.cognisphere_seed import domain_from_path_id
from cognispheretutor.learning.models import PendingQuestion
from cognispheretutor.learning.policy import find_knowledge_point, is_mastered, next_objective
from cognispheretutor.learning.scheduler import SpacedRepetitionScheduler
from cognispheretutor.learning.service import LearningService
from cognispheretutor.learning.storage import LearningStore
from cognispheretutor.tools.ask_user import build_ask_user_payload


_FLOW_MESSAGES = {
    "continue",
    "go on",
    "next",
    "start",
    "begin",
    "learn",
    "继续",
    "下一步",
    "下一课",
    "开始",
    "学习",
}
_ANSWER_RE = re.compile(r"(?i)^\s*(?:answer\s*)?(?:option\s*)?([a-h]|true|false|t|f|yes|no|对|错|正确|错误)\s*$")


async def maybe_run_deterministic_mastery_flow(
    context: UnifiedContext,
    stream: StreamBus,
) -> bool:
    """Run the deterministic mastery loop when this turn is a flow action."""

    path_id = str(context.metadata.get("mastery_path_id") or "").strip()
    domain = domain_from_path_id(path_id)
    if not path_id or not domain:
        return False

    service = LearningService(LearningStore())
    progress = service.get_or_create(path_id)
    if not any(module.knowledge_points for module in progress.modules):
        return False

    user_message = _plain_user_message(context.user_message)
    is_answer = bool(progress.pending_question and _extract_answer(user_message))
    is_flow = _looks_like_flow_request(user_message) or bool(
        context.metadata.get("mastery_start_action")
    )
    if not is_answer and not is_flow:
        return False

    await stream.emit(
        StreamEvent(
            type=StreamEventType.STAGE_START,
            source="mastery_path",
            stage="responding",
            content="",
            metadata={"deterministic_mastery_flow": True},
        )
    )
    try:
        await _run_flow_cycles(
            context=context,
            stream=stream,
            service=service,
            path_id=path_id,
            domain=domain,
            initial_answer=_extract_answer(user_message) if is_answer else "",
        )
    finally:
        await stream.emit(
            StreamEvent(
                type=StreamEventType.STAGE_END,
                source="mastery_path",
                stage="responding",
                content="",
                metadata={"deterministic_mastery_flow": True},
            )
        )
    return True


async def _run_flow_cycles(
    *,
    context: UnifiedContext,
    stream: StreamBus,
    service: LearningService,
    path_id: str,
    domain: str,
    initial_answer: str,
) -> None:
    answer = initial_answer
    max_cycles = 5
    for cycle in range(max_cycles):
        progress = service.get_or_create(path_id)
        if (
            cycle == 0
            and str(context.metadata.get("mastery_start_action") or "").strip().lower() == "start"
            and str(context.metadata.get("mastery_start_point") or "").strip()
            and progress.pending_question is not None
        ):
            service.clear_pending_question(progress)
            progress = service.get_or_create(path_id)
        if progress.pending_question is not None:
            answered = answer or await _ask_existing_pending(context, stream, progress.pending_question)
            if not answered:
                return
            grade = _grade_pending(
                service=service,
                progress=progress,
                answer=answered,
                session_id=str(context.session_id or ""),
                turn_id=str(context.metadata.get("turn_id") or ""),
            )
            await _emit_feedback(stream, grade)
            answer = ""
            if not grade["mastered"]:
                replacement = await _teach_and_ask(
                    context=context,
                    stream=stream,
                    service=service,
                    path_id=path_id,
                    domain=domain,
                    prefer_same_objective=grade["knowledge_point_id"],
                )
                reply = await _wait_for_reply(context, stream)
                await _emit_ask_user_resolved(stream, replacement.question_id, reply)
                answer = _answer_from_reply(reply)
                if not answer:
                    return
                continue
            if cycle < max_cycles - 1:
                continue
            return

        step = next_objective_for_start_point(
            progress,
            str(context.metadata.get("mastery_start_point") or "").strip(),
        )
        if step.action == "complete":
            scope = (
                "Selected learning area"
                if str(context.metadata.get("mastery_start_point") or "").strip()
                else "All objectives in this path"
            )
            await stream.content(
                f"{scope} is mastered. Source: local plugin pack, Cognisphere materialized\n",
                source="mastery_path",
                stage="responding",
            )
            return
        pending = await _teach_and_ask(
            context=context,
            stream=stream,
            service=service,
            path_id=path_id,
            domain=domain,
            prefer_same_objective=step.knowledge_point_id,
        )
        reply = await _wait_for_reply(context, stream)
        await _emit_ask_user_resolved(stream, pending.question_id, reply)
        answer = _answer_from_reply(reply)
        if not answer:
            return


async def _teach_and_ask(
    *,
    context: UnifiedContext,
    stream: StreamBus,
    service: LearningService,
    path_id: str,
    domain: str,
    prefer_same_objective: str,
) -> PendingQuestion:
    progress = service.get_or_create(path_id)
    kp, module_id, module_name = find_knowledge_point(progress, prefer_same_objective)
    if kp is None:
        return
    objective = {
        "module_id": module_id,
        "module_name": module_name,
        "knowledge_point_id": kp.id,
        "knowledge_point_name": kp.name,
        "knowledge_point_type": kp.type.value,
    }
    grounding = _grounding_items(domain, objective, context.user_message)
    lesson = _lesson_text(module_name=module_name, objective_name=kp.name, items=grounding)
    await stream.content(lesson, source="mastery_path", stage="responding")

    question = _question_from_grounding(kp.id, module_id, kp.name, grounding)
    service.set_pending_question(progress, question)
    await _emit_quiz_registration(stream, question)
    await _emit_ask_user(stream, question)
    return question


def _grade_pending(
    *,
    service: LearningService,
    progress: Any,
    answer: str,
    session_id: str,
    turn_id: str,
) -> dict[str, Any]:
    pending = progress.pending_question
    assert pending is not None
    is_correct = service.grade_and_record(
        progress,
        question_id=pending.question_id,
        knowledge_point_id=pending.knowledge_point_id,
        module_id=pending.module_id,
        user_answer=answer,
        expected_answer=pending.expected_answer,
        question_type=pending.question_type,
        scheduler=SpacedRepetitionScheduler(),
    )
    service.clear_pending_question(progress)
    kp, _, _ = find_knowledge_point(progress, pending.knowledge_point_id)
    if is_correct and kp is not None and kp.type.value in {"concept", "design"}:
        service.record_qualitative(
            progress,
            pending.knowledge_point_id,
            passed=True,
            evidence=f"Quick check answered correctly in turn {turn_id or 'unknown'}",
        )
    progress = service.get_or_create(progress.book_id)
    kp, _, _ = find_knowledge_point(progress, pending.knowledge_point_id)
    return {
        "is_correct": is_correct,
        "knowledge_point_id": pending.knowledge_point_id,
        "expected_answer": pending.expected_answer,
        "mastered": bool(kp and is_mastered(progress, kp)),
        "next": next_objective(progress).to_dict(),
        "session_id": session_id,
    }


async def _ask_existing_pending(
    context: UnifiedContext,
    stream: StreamBus,
    pending: PendingQuestion,
) -> str:
    await _emit_ask_user(stream, pending)
    reply = await _wait_for_reply(context, stream)
    await _emit_ask_user_resolved(stream, pending.question_id, reply)
    return _answer_from_reply(reply)


async def _emit_ask_user(stream: StreamBus, pending: PendingQuestion) -> None:
    labels = _option_labels(pending.options)
    options = [
        {"label": label, "description": body}
        for label, body in labels
    ]
    payload, err = build_ask_user_payload(
        questions=[
            {
                "id": pending.question_id,
                "header": "Quick check",
                "prompt": pending.prompt,
                "options": options,
                "allow_free_text": False,
            }
        ],
        intro="Quick check",
    )
    if payload is None:
        raise RuntimeError(err or "Unable to build mastery question card.")
    call_id = f"deterministic-ask-user-{pending.question_id}"
    await stream.tool_result(
        tool_name="ask_user",
        result=f"[awaiting user reply to: {pending.prompt}]",
        source="mastery_path",
        stage="responding",
        metadata={
            "tool_call_id": call_id,
            "tool_metadata": {"ask_user": payload.to_dict()},
        },
    )


async def _emit_ask_user_resolved(
    stream: StreamBus,
    question_id: str,
    reply: dict[str, Any] | None,
) -> None:
    answers = reply.get("answers") if isinstance(reply, dict) else None
    text = str(reply.get("text") or "") if isinstance(reply, dict) else ""
    await stream.progress(
        "Answer received",
        source="mastery_path",
        stage="responding",
        metadata={
            "ask_user_resolved": True,
            "ask_user_tool_call_id": f"deterministic-ask-user-{question_id}",
            "answers": answers or [{"questionId": question_id, "text": text}],
            "reply_preview": text,
        },
    )


async def _emit_quiz_registration(stream: StreamBus, pending: PendingQuestion) -> None:
    await stream.tool_result(
        tool_name="mastery_quiz",
        result=json.dumps(
            {
                "status": "registered",
                "knowledge_point_id": pending.knowledge_point_id,
                "question": pending.prompt,
                "options": pending.options,
            },
            ensure_ascii=False,
        ),
        source="mastery_path",
        stage="responding",
        metadata={"tool_metadata": {"mastery_quiz": {"question_id": pending.question_id}}},
    )


async def _emit_feedback(stream: StreamBus, grade: dict[str, Any]) -> None:
    if grade["is_correct"] and grade["mastered"]:
        text = "\nCorrect. This objective is now mastered, so we will move to the next lesson.\n\n"
    elif grade["is_correct"]:
        text = (
            "\nCorrect. This objective still needs a little more evidence before the mastery gate clears, "
            "so I will give you one tighter follow-up check.\n\n"
        )
    else:
        text = (
            "\nNot quite. I will keep us on the same objective and give you a tighter "
            f"replacement check. Correct answer: {grade['expected_answer']}.\n\n"
        )
    text += "Source: local plugin pack, Cognisphere materialized\n\n"
    await stream.content(text, source="mastery_path", stage="responding")


def _question_from_grounding(
    kp_id: str,
    module_id: str,
    objective_name: str,
    items: list[dict[str, Any]],
) -> PendingQuestion:
    for item in items:
        scenario = _first_text(item.get("scenario") or item.get("prompt") or item.get("question"))
        choices = _choice_strings(item.get("choices"))
        answer = _first_text(item.get("answer") or item.get("expected_answer"))
        if scenario and len(choices) >= 2 and answer:
            labels = _option_labels(choices)
            expected = _normalize_expected_answer(answer, labels)
            if expected:
                return PendingQuestion(
                    question_id=uuid.uuid4().hex,
                    knowledge_point_id=kp_id,
                    module_id=module_id,
                    prompt=scenario,
                    question_type="choice",
                    expected_answer=expected,
                    options=[f"{label}: {body}" for label, body in labels],
                    created_at=time.time(),
                )
    correct = f"{objective_name} is the current learning objective."
    return PendingQuestion(
        question_id=uuid.uuid4().hex,
        knowledge_point_id=kp_id,
        module_id=module_id,
        prompt=f"Which statement best matches this lesson's objective: {objective_name}?",
        question_type="choice",
        expected_answer="A",
        options=[
            f"A: {correct}",
            "B: It is unrelated to this learning path.",
            "C: It should be skipped before practice.",
            "D: It is only a model-generated chat topic.",
        ],
        created_at=time.time(),
    )


def _grounding_items(domain: str, objective: dict[str, Any], learner_goal: str) -> list[dict[str, Any]]:
    query = _objective_query(objective, learner_goal=learner_goal)
    ranked = _rank_items(_load_domain_items(domain), query)[:4]
    return [_render_item(item) for item in ranked]


def _lesson_text(*, module_name: str, objective_name: str, items: list[dict[str, Any]]) -> str:
    lines = [f"## {objective_name}", "", f"Area: {module_name}", ""]
    points = _lesson_points(items)
    if points:
        lines.append("Here is the core idea:")
        for point in points[:5]:
            lines.append(f"- {point}")
    else:
        lines.append(
            "The local pack has only sparse detail for this objective, so we will keep this lesson focused on the path definition and practice gate."
        )
    lines.extend(["", "Source: local plugin pack, Cognisphere materialized", "", "Now answer the quick check below."])
    return "\n".join(lines) + "\n\n"


def _lesson_points(items: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for item in items:
        for key in ("key_takeaways", "teaching_points", "learning_outcomes", "summary", "description", "body"):
            value = item.get(key)
            values = value if isinstance(value, list) else [value]
            for raw in values:
                text = _first_text(raw)
                if not text:
                    continue
                for sentence in re.split(r"(?<=[.!?。！？])\s+", text):
                    cleaned = re.sub(r"\s+", " ", sentence).strip(" -")
                    if 30 <= len(cleaned) <= 240 and cleaned not in out:
                        out.append(cleaned)
                        break
    return out


def _option_labels(options: list[str]) -> list[tuple[str, str]]:
    labels: list[tuple[str, str]] = []
    for idx, raw in enumerate(options):
        text = str(raw or "").strip()
        match = re.match(r"^\s*([A-Ha-h])\s*[:.)：、-]\s*(.+)$", text)
        if match:
            labels.append((match.group(1).upper(), match.group(2).strip()))
        else:
            labels.append((chr(ord("A") + idx), text))
    return [(label, body) for label, body in labels if body]


def _choice_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [f"{key}: {val}" for key, val in value.items() if str(val).strip()]
    return []


def _normalize_expected_answer(answer: str, labels: list[tuple[str, str]]) -> str:
    text = answer.strip()
    if re.fullmatch(r"(?i)[a-h]", text):
        return text.upper()
    for label, body in labels:
        if text.casefold() == body.casefold() or text.casefold() in body.casefold():
            return label
    return ""


def _first_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ("text", "prompt", "question", "answer", "summary", "description", "body"):
            if key in value:
                text = _first_text(value.get(key))
                if text:
                    return text
    if isinstance(value, list):
        for item in value:
            text = _first_text(item)
            if text:
                return text
    return ""


async def _wait_for_reply(
    context: UnifiedContext,
    stream: StreamBus,
) -> dict[str, Any] | None:
    waiter = context.metadata.get("wait_for_user_reply")
    if not callable(waiter):
        return None
    task = asyncio.create_task(waiter())
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=45.0)
            if task in done:
                reply = task.result()
                return reply if isinstance(reply, dict) else None
            await stream.progress(
                "Waiting for your answer",
                source="mastery_path",
                stage="responding",
                metadata={
                    "trace_kind": "call_status",
                    "call_state": "waiting_for_user",
                    "ask_user_waiting": True,
                },
            )
    finally:
        if not task.done():
            task.cancel()


def _answer_from_reply(reply: dict[str, Any] | None) -> str:
    if not isinstance(reply, dict):
        return ""
    answers = reply.get("answers")
    if isinstance(answers, list) and answers:
        first = answers[0]
        if isinstance(first, dict):
            return str(first.get("text") or "").strip()
    return str(reply.get("text") or "").strip()


def _extract_answer(message: str) -> str:
    match = _ANSWER_RE.match(message)
    if not match:
        return ""
    value = match.group(1)
    lowered = value.lower()
    if lowered in {"t", "true", "yes"} or value in {"对", "正确"}:
        return "true"
    if lowered in {"f", "false", "no"} or value in {"错", "错误"}:
        return "false"
    return value.upper()


def _looks_like_flow_request(message: str) -> bool:
    text = message.strip().casefold()
    if not text:
        return True
    if text in _FLOW_MESSAGES:
        return True
    return any(
        token in text
        for token in (
            "continue",
            "go on",
            "next",
            "start",
            "beginner",
            "from scratch",
            "one by one",
            "study plan",
            "继续",
            "下一",
            "开始学",
            "从头",
        )
    )


def _plain_user_message(message: str) -> str:
    text = str(message or "")
    marker = "[User Question]"
    if marker in text:
        text = text.rsplit(marker, 1)[-1]
    return text.strip()


__all__ = ["maybe_run_deterministic_mastery_flow"]
