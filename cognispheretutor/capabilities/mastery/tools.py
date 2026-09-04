"""Mastery Path tools — the seam between the chat-loop tutor and the pure
mastery engine (:mod:`cognispheretutor.learning`).

These five tools are auto-mounted only when a mastery path is active on the
turn (via the chat loop mastery capability). The chat agent loop IS the tutor;
these tools let it read the gate and record outcomes, while the pedagogy —
what to teach, how to question, when to explain — stays the model's job. The
arithmetic (mastery, gate, spaced repetition) stays in the engine.

The active path id is injected server-side by the pipeline as
``_mastery_path_id``; the model never supplies it. Each call constructs a
fresh store + service (matching the REST router) so concurrent turns can't
race on a shared object.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any
import uuid

from cognispheretutor.capabilities.mastery.choices import (
    format_options,
    has_option_bodies,
    parse_options,
    recover_options_from_turn,
    resolve_answer,
)
from cognispheretutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

# ``learning.models`` and ``learning.policy`` only depend on pydantic — safe to
# import at module load. ``learning.service`` / ``storage`` / ``scheduler``
# reach the path service (and so the runtime + tool registry), so importing
# them here would close an import cycle through the built-in registry. They
# are imported lazily inside the call paths instead (same pattern as the other
# builtin tools).
from cognispheretutor.learning.models import (
    KnowledgePoint,
    KnowledgeType,
    LearningModule,
    PendingQuestion,
)
from cognispheretutor.learning.policy import (
    QUALITATIVE_TYPES,
    NextStep,
    display_mastery,
    due_reviews,
    find_knowledge_point,
    gate_threshold,
    is_mastered,
    map_summary,
    next_objective,
    objective_status,
)

if TYPE_CHECKING:
    from cognispheretutor.learning.service import LearningService

# Tool names the pipeline mounts together when a mastery path is active. Kept
# here so the mount policy and the registration list can't disagree.
MASTERY_TOOL_NAMES: tuple[str, ...] = (
    "mastery_status",
    "mastery_visual",
    "mastery_quiz",
    "mastery_grade",
    "mastery_assess",
    "mastery_build",
)

_QUESTION_TYPES = ("choice", "short", "open")
_VISUAL_TEMPLATES = (
    "auto",
    "lever",
    "fixed_pulley",
    "movable_pulley",
    "three_gears",
    "open_belt",
    "crossed_belt",
    "paper_one_fold_hole",
    "paper_two_fold_unfold",
    "rotation_vs_reflection",
)
_ALLOWED_KP_TYPES = {t.value for t in KnowledgeType}
logger = logging.getLogger(__name__)
_NUMBER_PATTERN = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")


def _new_service() -> LearningService:
    from cognispheretutor.learning.service import LearningService
    from cognispheretutor.learning.storage import LearningStore

    return LearningService(LearningStore())


def _resolve_path_id(kwargs: dict[str, Any]) -> str:
    return str(kwargs.get("_mastery_path_id") or "").strip()


def _resolve_session_id(kwargs: dict[str, Any]) -> str:
    return str(kwargs.get("_session_id") or "").strip()


def _resolve_turn_id(kwargs: dict[str, Any]) -> str:
    return str(kwargs.get("_turn_id") or "").strip()


def _resolve_start_point(kwargs: dict[str, Any]) -> str:
    return str(kwargs.get("_mastery_start_point") or "").strip().lower()


def _resolve_start_action(kwargs: dict[str, Any]) -> str:
    return str(kwargs.get("_mastery_start_action") or "").strip().lower()


_START_POINT_MODULE_SIGNALS: dict[str, tuple[str, ...]] = {
    "newcomer_sprint": (
        "california electrical career orientation",
        "career orientation",
        "shared electrical foundations",
    ),
    "apprenticeship_entry": ("apprenticeship entrance", "ibew", "eti"),
    "shared_foundations": ("shared electrical foundations",),
    "ge": ("general electrician",),
    "c10": ("c-10", "c10 electrical trade"),
    "law_business": ("law and business", "law & business", "contractor law"),
    "aws_beginner": ("cloud foundations", "cloud practitioner", "certification overview"),
}

_START_POINT_KP_IDS: dict[str, str] = {
    "apprenticeship_diagnostic": "cec-apprentice-baseline-diagnostic",
    "apprenticeship_math": "cec-apprentice-math-reasoning",
    "apprenticeship_numerical": "cec-apprentice-numerical-reasoning",
    "apprenticeship_reading": "cec-apprentice-reading",
    "apprenticeship_mechanical": "cec-apprentice-mechanical",
    "apprenticeship_spatial": "cec-apprentice-spatial",
    "apprenticeship_timed": "cec-apprentice-timed-practice",
    "apprenticeship_pef": "cec-apprentice-pef",
}

_START_POINT_KP_SIGNALS: dict[str, tuple[str, ...]] = {
    "apprenticeship_diagnostic": ("baseline diagnostic", "apprenticeship readiness"),
    "apprenticeship_math": ("mathematical reasoning", "aptitude testing"),
    "apprenticeship_numerical": ("numerical reasoning", "sequences", "data interpretation"),
    "apprenticeship_reading": ("reading comprehension", "technical instructions"),
    "apprenticeship_mechanical": ("mechanical reasoning", "levers", "pulleys", "gears"),
    "apprenticeship_spatial": ("spatial reasoning", "paper folding"),
    "apprenticeship_timed": ("timed mixed practice", "aptitude test"),
    "apprenticeship_pef": ("personal experience form", "evidence organization"),
}


def _module_matches_start_point(module: LearningModule, start_point: str) -> bool:
    signals = _START_POINT_MODULE_SIGNALS.get(start_point, ())
    if not signals:
        return False
    haystack = f"{module.id} {module.name}".lower()
    return any(signal in haystack for signal in signals)


def _step_for_selected_kp(progress: Any, kp_id: str) -> NextStep | None:
    selected_seen = False
    for module in sorted(progress.modules, key=lambda item: item.order):
        for kp in module.knowledge_points:
            if kp.id == kp_id:
                selected_seen = True
                if not is_mastered(progress, kp):
                    return _step_for_kp(progress, module, kp)
                continue
            if selected_seen and module.id == kp.module_id and not is_mastered(progress, kp):
                return _step_for_kp(progress, module, kp)
    return None


def _kp_matches_start_point(kp: KnowledgePoint, start_point: str) -> bool:
    if kp.id == _START_POINT_KP_IDS.get(start_point, ""):
        return True
    signals = _START_POINT_KP_SIGNALS.get(start_point, ())
    if not signals:
        return False
    haystack = f"{kp.id} {kp.name}".lower()
    return any(signal in haystack for signal in signals)


def _step_for_selected_start_point_kp(progress: Any, start_point: str) -> NextStep | None:
    selected_seen = False
    selected_module_id = ""
    for module in sorted(progress.modules, key=lambda item: item.order):
        for kp in module.knowledge_points:
            if _kp_matches_start_point(kp, start_point):
                selected_seen = True
                selected_module_id = module.id
                if not is_mastered(progress, kp):
                    return _step_for_kp(progress, module, kp)
                continue
            if selected_seen and module.id == selected_module_id and not is_mastered(progress, kp):
                return _step_for_kp(progress, module, kp)
    return None


def _step_for_kp(progress: Any, module: LearningModule, kp: KnowledgePoint) -> NextStep:
    status = objective_status(progress, kp)
    gate = "qualitative" if kp.type in QUALITATIVE_TYPES else "quantitative"
    action = "probe" if status == "new" else ("assess" if gate == "qualitative" else "practice")
    return NextStep(
        action=action,
        module_id=module.id,
        module_name=module.name,
        knowledge_point_id=kp.id,
        knowledge_point_name=kp.name,
        knowledge_point_type=kp.type.value,
        status=status,
        gate=gate,
        mastery=display_mastery(progress, kp),
        threshold=gate_threshold(kp.type),
        reason=(
            "Learner selected this start point; use the first unmastered objective "
            "inside the matching module instead of asking them to choose a scope."
        ),
    )


def next_objective_for_start_point(
    progress: Any,
    start_point: str,
    *,
    now: float | None = None,
) -> NextStep:
    """Select the next step within a learner-chosen module when possible."""
    normalized = str(start_point or "").strip().lower()
    if not normalized:
        return next_objective(progress, now=now)
    if normalized in _START_POINT_KP_IDS:
        selected_step = _step_for_selected_kp(
            progress,
            _START_POINT_KP_IDS.get(normalized, ""),
        ) or _step_for_selected_start_point_kp(progress, normalized)
        if selected_step is not None:
            return selected_step
    pending = progress.pending_question
    if pending is not None:
        module = next((m for m in progress.modules if m.id == pending.module_id), None)
        if module is not None and _module_matches_start_point(module, normalized):
            return next_objective(progress, now=now)
        return next_objective(progress, now=now)

    for review in due_reviews(progress, now=now):
        kp, module_id, _module_name = find_knowledge_point(progress, review.knowledge_point_id)
        module = next((m for m in progress.modules if m.id == module_id), None)
        if kp is not None and module is not None and _module_matches_start_point(module, normalized):
            return _step_for_kp(progress, module, kp)

    for module in sorted(progress.modules, key=lambda item: item.order):
        if not _module_matches_start_point(module, normalized):
            continue
        for kp in module.knowledge_points:
            if not is_mastered(progress, kp):
                return _step_for_kp(progress, module, kp)
    return next_objective(progress, now=now)


def _parse_number(value: str) -> float | None:
    match = _NUMBER_PATTERN.search(str(value or ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _numbers_close(left: float, right: float) -> bool:
    return abs(left - right) <= max(0.01, abs(right) * 0.001)


def _infer_numeric_answer(question: str) -> float | None:
    text = " ".join(str(question or "").lower().replace(",", "").split())
    match = re.search(
        r"requires\s+(\d+(?:\.\d+)?)\s+feet.*?"
        r"installs\s+(\d+(?:\.\d+)?)\s+feet.*?"
        r"installs\s+(\d+(?:\.\d+)?)\s*%\s+of\s+the\s+remaining",
        text,
    )
    if match:
        total, first, pct = (float(value) for value in match.groups())
        return first + (total - first) * (pct / 100.0)

    match = re.search(
        r"winds\s+(\d+(?:\.\d+)?)\s+feet\s+of\s+cable\s+in\s+(\d+(?:\.\d+)?)\s+minutes.*?"
        r"in\s+(\d+(?:\.\d+)?)\s+minutes",
        text,
    )
    if match:
        feet, minutes, target_minutes = (float(value) for value in match.groups())
        if minutes:
            return feet / minutes * target_minutes

    match = re.search(
        r"(\d+(?:\.\d+)?)\s+(?:electricians|workers).*?"
        r"in\s+(\d+(?:\.\d+)?)\s+hours.*?"
        r"in\s+(\d+(?:\.\d+)?)\s+hours",
        text,
    )
    if match:
        workers, hours, target_hours = (float(value) for value in match.groups())
        if target_hours:
            return workers * hours / target_hours

    return None


def _validate_numeric_choice_answer(
    *,
    question: str,
    expected_label: str,
    options: dict[str, str],
) -> str:
    expected_value = _parse_number(options.get(expected_label, ""))
    inferred = _infer_numeric_answer(question)
    if inferred is None or expected_value is None:
        return ""
    matching_labels: list[str] = []
    for label, body in options.items():
        value = _parse_number(body)
        if value is not None and _numbers_close(value, inferred):
            matching_labels.append(label)
    if not matching_labels:
        return (
            "The choice question appears to be a numeric word problem, but no option "
            f"matches the computed answer ({inferred:g}). Revise the answer choices "
            "before registering the quiz."
        )
    if expected_label not in matching_labels:
        return (
            f"The registered expected answer {expected_label} points to "
            f"{expected_value:g}, but the computed answer is {inferred:g} "
            f"({', '.join(matching_labels)}). Retry mastery_quiz with the correct label."
        )
    return ""


def _question_bank_type(question_type: str) -> str:
    qtype = str(question_type or "").strip().lower()
    if qtype == "choice":
        return "choice"
    if qtype == "open":
        return "written"
    return "short_answer"


async def _resolve_pending_choice(
    pending: PendingQuestion, turn_id: str
) -> tuple[dict[str, str], str]:
    """Resolve a pending choice question's ``({label: body}, expected_label)``.

    Re-parses the bodies stored at registration; for legacy paths that stored
    only ``["A", "B", ...]`` it recovers the real bodies from the turn's
    ``ask_user`` event. The expected answer is normalised to a stable label
    when it resolves, else left as registered.
    """
    options = parse_options(list(pending.options or []))
    if not has_option_bodies(options):
        try:
            from cognispheretutor.services.session import get_sqlite_session_store

            options = await recover_options_from_turn(
                get_sqlite_session_store(), turn_id, pending.prompt
            )
        except Exception:
            logger.warning("Failed to recover legacy mastery choice options", exc_info=True)
            options = {}
    return options, resolve_answer(pending.expected_answer, options) or pending.expected_answer


async def _sync_mastery_attempt_to_question_bank(
    *,
    session_id: str,
    turn_id: str,
    pending: PendingQuestion,
    user_answer: str,
    is_correct: bool,
    choice_options: dict[str, str] | None = None,
    correct_answer: str | None = None,
) -> None:
    if not session_id:
        return
    item = {
        "turn_id": turn_id,
        "question_id": pending.question_id,
        "question": pending.prompt,
        "question_type": _question_bank_type(pending.question_type),
        "options": choice_options or parse_options(list(pending.options or [])),
        "correct_answer": correct_answer or pending.expected_answer,
        "explanation": "",
        "difficulty": "",
        "user_answer": user_answer,
        "is_correct": is_correct,
    }
    try:
        from cognispheretutor.services.session import get_sqlite_session_store

        await get_sqlite_session_store().upsert_notebook_entries(session_id, [item])
    except Exception:
        logger.warning(
            "Failed to sync mastery question %s to question bank for session %s",
            pending.question_id,
            session_id,
            exc_info=True,
        )


def _json_result(payload: dict[str, Any], *, meta_key: str, success: bool = True) -> ToolResult:
    return ToolResult(
        content=json.dumps(payload, ensure_ascii=False),
        success=success,
        metadata={meta_key: payload},
    )


def _no_path_result() -> ToolResult:
    return ToolResult(
        content="No mastery path is active on this turn; mastery tools are unavailable.",
        success=False,
    )


class MasteryStatusTool(BaseTool):
    """Read the current objective + map snapshot. Call FIRST every turn."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="mastery_status",
            description=(
                "Read the learner's mastery path: the next objective to work on "
                "(decided by a hard mastery gate), any question awaiting an "
                "answer, due reviews, and a map of every objective's status "
                "(new / learning / mastered). Call this FIRST on every mastery "
                "turn — it tells you what to do; never guess the next objective."
            ),
            parameters=[],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        path_id = _resolve_path_id(kwargs)
        if not path_id:
            return _no_path_result()
        service = _new_service()
        progress = service.get_or_create(path_id)
        if not any(module.knowledge_points for module in progress.modules):
            return _json_result(
                {
                    "status": "empty",
                    "message": (
                        "No mastery path has been built yet. Design one from the "
                        "learner's materials and call mastery_build."
                    ),
                },
                meta_key="mastery_status",
            )
        payload = {
            "status": "active",
        }
        start_point = _resolve_start_point(kwargs)
        start_action = _resolve_start_action(kwargs)
        if start_point and progress.pending_question is not None:
            pending_module = next(
                (m for m in progress.modules if m.id == progress.pending_question.module_id),
                None,
            )
            should_clear_pending = start_action == "start" or (
                pending_module is not None
                and not _module_matches_start_point(pending_module, start_point)
            )
            if should_clear_pending:
                service.clear_pending_question(progress)
                payload["cleared_pending_question"] = True
        payload.update(
            {
                "next": next_objective_for_start_point(progress, start_point).to_dict(),
                "map": map_summary(progress),
            }
        )
        if start_point:
            payload["requested_start_point"] = start_point
        if start_action:
            payload["requested_start_action"] = start_action
        return _json_result(payload, meta_key="mastery_status")


class MasteryVisualTool(BaseTool):
    """Return deterministic visual aids for visual apprenticeship objectives."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="mastery_visual",
            description=(
                "Create a deterministic visual aid for a mastery mini-lesson. "
                "Use this for mechanical reasoning, levers, pulleys, gears, belts, "
                "spatial reasoning, paper folding, rotation, or reflection before "
                "teaching the lesson. The returned markdown is safe to include in "
                "the assistant reply and should be shown before the quick check."
            ),
            parameters=[
                ToolParameter(
                    name="knowledge_point_id",
                    type="string",
                    description="Objective id from mastery_status (verbatim).",
                    required=False,
                ),
                ToolParameter(
                    name="template",
                    type="string",
                    description="Visual template to render. Use 'auto' when unsure.",
                    required=False,
                    default="auto",
                    enum=list(_VISUAL_TEMPLATES),
                ),
                ToolParameter(
                    name="focus",
                    type="string",
                    description=(
                        "Optional plain-language focus, for example 'gear direction' "
                        "or 'one-fold hole punch'."
                    ),
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        path_id = _resolve_path_id(kwargs)
        if not path_id:
            return _no_path_result()
        kp_id = str(kwargs.get("knowledge_point_id") or "").strip()
        requested = str(kwargs.get("template") or "auto").strip().lower()
        if requested not in _VISUAL_TEMPLATES:
            requested = "auto"
        focus = str(kwargs.get("focus") or "").strip()

        service = _new_service()
        progress = service.get_or_create(path_id)
        kp: KnowledgePoint | None = None
        module_name = ""
        if kp_id:
            kp, _module_id, module_name = find_knowledge_point(progress, kp_id)
            if kp is None:
                return ToolResult(
                    content=f"Unknown objective {kp_id!r}; call mastery_status for valid ids.",
                    success=False,
                )
        if kp is None:
            step = next_objective_for_start_point(progress, _resolve_start_point(kwargs))
            kp, _module_id, module_name = find_knowledge_point(
                progress, step.knowledge_point_id
            )
            kp_id = step.knowledge_point_id
        objective_text = " ".join(
            part
            for part in (
                focus,
                kp_id,
                module_name,
                kp.name if kp else "",
            )
            if part
        )
        template = _resolve_visual_template(requested, objective_text)
        visual = _render_visual_template(template)
        payload = {
            "status": "ready",
            "knowledge_point_id": kp_id,
            "template": template,
            "title": visual["title"],
            "teaching_cue": visual["teaching_cue"],
            "markdown": visual["markdown"],
            "usage_instruction": (
                "Copy the markdown field exactly in the learner-facing reply before "
                "the quick quiz, including the opening and closing ```mermaid fences. "
                "Do not paraphrase, inline, or partially rewrite the diagram syntax. "
                "Treat it as a visual aid, then teach the mini-lesson and ask one "
                "registered mastery_quiz + ask_user check."
            ),
        }
        return _json_result(payload, meta_key="mastery_visual")


class MasteryQuizTool(BaseTool):
    """Register an objective-type question; the engine holds the answer."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="mastery_quiz",
            description=(
                "Pose a question for a MEMORY or PROCEDURE objective and register "
                "its expected answer with the engine (so grading is deterministic "
                "and you never re-state the answer later). After calling this, "
                "present the question with the ask_user tool so the learner answers "
                "on an interactive card (for choices, give ask_user options short "
                "labels like A/B/C, pass every full option body here, and set the "
                "correct label as expected_answer); "
                "then call mastery_grade with their answer. For CONCEPT / DESIGN "
                "objectives use mastery_assess instead."
            ),
            parameters=[
                ToolParameter(
                    name="knowledge_point_id",
                    type="string",
                    description="Objective id from mastery_status (verbatim).",
                ),
                ToolParameter(
                    name="question",
                    type="string",
                    description="The question text shown to the learner.",
                ),
                ToolParameter(
                    name="expected_answer",
                    type="string",
                    description="The correct answer, used only server-side for grading.",
                ),
                ToolParameter(
                    name="question_type",
                    type="string",
                    description=(
                        "'choice' (exact match), 'short' (exact / fuzzy for ≤30 "
                        "chars), or 'open' (keyword overlap). Default 'short'."
                    ),
                    required=False,
                    default="short",
                    enum=list(_QUESTION_TYPES),
                ),
                ToolParameter(
                    name="options",
                    type="array",
                    description=(
                        "For question_type='choice', every full option in label order, "
                        "for example ['A: first answer', 'B: second answer']. Never "
                        "pass bare labels such as ['A', 'B', 'C', 'D']. Use the same "
                        "bodies as the ask_user option descriptions."
                    ),
                    required=False,
                    items={"type": "string"},
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        path_id = _resolve_path_id(kwargs)
        if not path_id:
            return _no_path_result()
        kp_id = str(kwargs.get("knowledge_point_id") or "").strip()
        question = str(kwargs.get("question") or "").strip()
        expected = str(kwargs.get("expected_answer") or "").strip()
        if not kp_id or not question or not expected:
            return ToolResult(
                content="mastery_quiz needs knowledge_point_id, question, and expected_answer.",
                success=False,
            )
        q_type = str(kwargs.get("question_type") or "short").strip().lower()
        if q_type not in _QUESTION_TYPES:
            q_type = "short"
        options = [str(o) for o in (kwargs.get("options") or []) if str(o).strip()]
        if q_type == "choice":
            choice_options = parse_options(options)
            if not has_option_bodies(choice_options):
                return ToolResult(
                    content=(
                        "Choice questions need full option bodies in mastery_quiz.options "
                        "(for example ['A: first answer', 'B: second answer']), not only "
                        "the labels A/B/C/D. Retry mastery_quiz with the exact option "
                        "descriptions you will show through ask_user."
                    ),
                    success=False,
                )
            resolved_expected = resolve_answer(expected, choice_options)
            if not resolved_expected:
                return ToolResult(
                    content=(
                        "Choice expected_answer must be an option label such as A/B/C/D, "
                        "or uniquely match one full option body. Retry mastery_quiz with "
                        "the correct label."
                    ),
                    success=False,
                )
            numeric_error = _validate_numeric_choice_answer(
                question=question,
                expected_label=resolved_expected,
                options=choice_options,
            )
            if numeric_error:
                return ToolResult(content=numeric_error, success=False)
            expected = resolved_expected
            options = format_options(choice_options)

        service = _new_service()
        progress = service.get_or_create(path_id)
        kp, module_id, _ = find_knowledge_point(progress, kp_id)
        if kp is None:
            return ToolResult(
                content=f"Unknown objective {kp_id!r}; call mastery_status for valid ids.",
                success=False,
            )
        existing = progress.pending_question
        if existing is not None:
            if existing.knowledge_point_id == kp_id:
                return _json_result(
                    {
                        "status": "already_pending",
                        "knowledge_point_id": existing.knowledge_point_id,
                        "question": existing.prompt,
                        "options": existing.options,
                        "instruction": (
                            "A mastery question is already registered for this objective. "
                            "Present the existing question with ask_user if it has not been "
                            "shown yet; otherwise call mastery_grade with the learner's answer. "
                            "Do not create or ask a duplicate question."
                        ),
                    },
                    meta_key="mastery_quiz",
                )
            return ToolResult(
                content=(
                    "Another mastery question is already awaiting an answer. Grade or clear "
                    "the existing pending question before registering a new one."
                ),
                success=False,
            )
        pending = PendingQuestion(
            question_id=uuid.uuid4().hex,
            knowledge_point_id=kp_id,
            module_id=module_id,
            prompt=question,
            question_type=q_type,
            expected_answer=expected,
            options=options,
        )
        service.set_pending_question(progress, pending)
        return _json_result(
            {
                "status": "registered",
                "knowledge_point_id": kp_id,
                "question": question,
                "options": options,
                "instruction": (
                    "Present this question with the ask_user tool (use its options "
                    "for multiple choice; the option labels must match the "
                    "expected_answer you registered), then call mastery_grade with "
                    "the learner's answer."
                ),
            },
            meta_key="mastery_quiz",
        )


class MasteryGradeTool(BaseTool):
    """Grade the learner's answer to the pending question (deterministic)."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="mastery_grade",
            description=(
                "Grade the learner's answer to the question you registered with "
                "mastery_quiz. Grading is deterministic against the stored "
                "expected answer; this updates mastery, advances spaced "
                "repetition, and tells you whether the objective's gate is now "
                "cleared. Then give the learner feedback."
            ),
            parameters=[
                ToolParameter(
                    name="answer",
                    type="string",
                    description="The learner's answer, verbatim.",
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        path_id = _resolve_path_id(kwargs)
        if not path_id:
            return _no_path_result()
        from cognispheretutor.learning.scheduler import SpacedRepetitionScheduler

        answer = str(kwargs.get("answer") or "")
        service = _new_service()
        scheduler = SpacedRepetitionScheduler()
        progress = service.get_or_create(path_id)
        pending = progress.pending_question
        if pending is None:
            return ToolResult(
                content="No question is awaiting an answer. Pose one with mastery_quiz first.",
                success=False,
            )
        choice_options: dict[str, str] = {}
        expected_answer = pending.expected_answer
        if pending.question_type == "choice":
            choice_options, expected_answer = await _resolve_pending_choice(
                pending, _resolve_turn_id(kwargs)
            )

        is_correct = service.grade_and_record(
            progress,
            question_id=pending.question_id,
            knowledge_point_id=pending.knowledge_point_id,
            module_id=pending.module_id,
            user_answer=answer,
            expected_answer=expected_answer,
            question_type=pending.question_type,
            scheduler=scheduler,
        )
        await _sync_mastery_attempt_to_question_bank(
            session_id=_resolve_session_id(kwargs),
            turn_id=_resolve_turn_id(kwargs),
            pending=pending,
            user_answer=answer,
            is_correct=is_correct,
            choice_options=choice_options,
            correct_answer=expected_answer,
        )
        service.clear_pending_question(progress)
        kp, _, _ = find_knowledge_point(progress, pending.knowledge_point_id)
        mastered = bool(kp and is_mastered(progress, kp))
        payload = {
            "is_correct": is_correct,
            "knowledge_point_id": pending.knowledge_point_id,
            "mastery": round(display_mastery(progress, kp), 3) if kp else 0.0,
            "threshold": round(gate_threshold(kp.type), 3) if kp else 0.0,
            "mastered": mastered,
            "next": next_objective(progress).to_dict(),
        }
        return _json_result(payload, meta_key="mastery_grade")


class MasteryAssessTool(BaseTool):
    """Record the qualitative (CONCEPT / DESIGN) gate from a Feynman check."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="mastery_assess",
            description=(
                "Record your judgement of a CONCEPT or DESIGN objective after the "
                "learner explains it in their own words (a Feynman-style check). "
                "Pass passed=true only when the explanation is correct and "
                "complete enough to count as mastery — this is the gate for these "
                "objective types. For MEMORY / PROCEDURE objectives use "
                "mastery_quiz + mastery_grade instead."
            ),
            parameters=[
                ToolParameter(
                    name="knowledge_point_id",
                    type="string",
                    description="Objective id from mastery_status (verbatim).",
                ),
                ToolParameter(
                    name="passed",
                    type="boolean",
                    description="True if the explanation demonstrates mastery.",
                ),
                ToolParameter(
                    name="feedback",
                    type="string",
                    description="Short note on what was strong or missing (stored as evidence).",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        path_id = _resolve_path_id(kwargs)
        if not path_id:
            return _no_path_result()
        kp_id = str(kwargs.get("knowledge_point_id") or "").strip()
        if not kp_id:
            return ToolResult(content="mastery_assess needs a knowledge_point_id.", success=False)
        passed = bool(kwargs.get("passed"))
        feedback = str(kwargs.get("feedback") or "").strip()

        service = _new_service()
        progress = service.get_or_create(path_id)
        kp, _, _ = find_knowledge_point(progress, kp_id)
        if kp is None:
            return ToolResult(
                content=f"Unknown objective {kp_id!r}; call mastery_status for valid ids.",
                success=False,
            )
        if kp.type not in QUALITATIVE_TYPES:
            return ToolResult(
                content=(
                    f"Objective {kp.name!r} is a {kp.type.value} type — gate it with "
                    "mastery_quiz + mastery_grade, not mastery_assess."
                ),
                success=False,
            )
        service.record_qualitative(progress, kp_id, passed=passed, evidence=feedback)
        payload = {
            "knowledge_point_id": kp_id,
            "passed": passed,
            "mastered": is_mastered(progress, kp),
            "mastery": round(display_mastery(progress, kp), 3),
            "next": next_objective(progress).to_dict(),
        }
        return _json_result(payload, meta_key="mastery_assess")


class MasteryBuildTool(BaseTool):
    """Create / extend the skill map from objectives the tutor designed."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="mastery_build",
            description=(
                "Create or extend the learner's mastery path. Design modules and "
                "their knowledge points from the learner's materials (use rag / "
                "read_source first when materials are attached) and pass them "
                "here. Each knowledge point needs a 'type': memory (facts), "
                "procedure (step-by-step skills), concept (ideas to understand), "
                "or design (open-ended judgement). Use mode='replace' to start "
                "fresh or 'append' to add to an existing path."
            ),
            parameters=[
                ToolParameter(
                    name="modules",
                    type="array",
                    description=(
                        "Ordered modules: each {name, knowledge_points: [{name, "
                        "type}]}. type is one of memory/procedure/concept/design."
                    ),
                    items={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "knowledge_points": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "type": {
                                            "type": "string",
                                            "enum": sorted(_ALLOWED_KP_TYPES),
                                        },
                                    },
                                    "required": ["name"],
                                },
                            },
                        },
                        "required": ["name", "knowledge_points"],
                    },
                ),
                ToolParameter(
                    name="mode",
                    type="string",
                    description="'replace' (default) starts fresh; 'append' adds modules.",
                    required=False,
                    default="replace",
                    enum=["replace", "append"],
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        path_id = _resolve_path_id(kwargs)
        if not path_id:
            return _no_path_result()
        mode = str(kwargs.get("mode") or "replace").strip().lower()
        if mode not in {"replace", "append"}:
            mode = "replace"

        service = _new_service()
        progress = service.get_or_create(path_id)
        offset = len(progress.modules) if mode == "append" else 0
        new_modules, error = _parse_modules(kwargs.get("modules"), path_id, offset)
        if error:
            return ToolResult(content=error, success=False)

        combined = (list(progress.modules) + new_modules) if mode == "append" else new_modules
        service.replace_modules(progress, combined)
        progress.pending_question = None  # a rebuilt map invalidates any open question
        if combined:
            progress.current_module_id = combined[0].id
            progress.current_kp_index = 0
        service.save(progress)
        kp_count = sum(len(m.knowledge_points) for m in new_modules)
        return _json_result(
            {
                "status": "built",
                "mode": mode,
                "modules_added": len(new_modules),
                "knowledge_points_added": kp_count,
                "map": map_summary(progress),
            },
            meta_key="mastery_build",
        )


def _parse_modules(
    raw_modules: Any, path_id: str, offset: int
) -> tuple[list[LearningModule], str | None]:
    """Validate the model-designed module tree into engine models.

    Ids are generated server-side (``<path>_m<i>_kp<j>``) so the model never
    controls storage keys; unknown knowledge types fall back to 'concept'.
    """
    if not isinstance(raw_modules, list) or not raw_modules:
        return [], "mastery_build needs a non-empty 'modules' array."
    modules: list[LearningModule] = []
    for i, raw in enumerate(raw_modules):
        if not isinstance(raw, dict):
            continue
        index = offset + i
        name = str(raw.get("name") or "").strip()[:200]
        if not name:
            continue
        module_id = f"{path_id}_m{index}"
        kps: list[KnowledgePoint] = []
        for j, raw_kp in enumerate(raw.get("knowledge_points") or []):
            if not isinstance(raw_kp, dict):
                continue
            kp_name = str(raw_kp.get("name") or "").strip()[:200]
            if len(kp_name) < 2:
                continue
            kp_type = str(raw_kp.get("type") or "concept").strip().lower()
            if kp_type not in _ALLOWED_KP_TYPES:
                kp_type = "concept"
            kps.append(
                KnowledgePoint(
                    id=f"{module_id}_kp{j}",
                    name=kp_name,
                    type=KnowledgeType(kp_type),
                    module_id=module_id,
                )
            )
        if not kps:
            continue
        modules.append(LearningModule(id=module_id, name=name, order=index, knowledge_points=kps))
    if not modules:
        return [], "No valid modules: each module needs a name and at least one knowledge point."
    return modules, None


def _resolve_visual_template(requested: str, text: str) -> str:
    if requested and requested != "auto":
        return requested
    normalized = str(text or "").lower()
    if "reflection" in normalized or "rotation" in normalized:
        return "rotation_vs_reflection"
    if "paper" in normalized or "fold" in normalized or "spatial" in normalized:
        if "two" in normalized or "twice" in normalized:
            return "paper_two_fold_unfold"
        return "paper_one_fold_hole"
    if "lever" in normalized or "force" in normalized or "mechanical" in normalized:
        return "lever"
    if "movable" in normalized and "pulley" in normalized:
        return "movable_pulley"
    if "pulley" in normalized:
        return "fixed_pulley"
    if "cross" in normalized and "belt" in normalized:
        return "crossed_belt"
    if "belt" in normalized:
        return "open_belt"
    if "gear" in normalized:
        return "three_gears"
    return "lever"


def _render_visual_template(template: str) -> dict[str, str]:
    title_map = {
        "lever": "Lever: force, pivot, and load",
        "fixed_pulley": "Fixed pulley: direction change",
        "movable_pulley": "Movable pulley: less force, more rope movement",
        "three_gears": "Three gears: direction trace",
        "open_belt": "Open belt: same rotation direction",
        "crossed_belt": "Crossed belt: reversed rotation direction",
        "paper_one_fold_hole": "One-fold paper hole punch",
        "paper_two_fold_unfold": "Two-fold paper unfolding storyboard",
        "rotation_vs_reflection": "Rotation versus reflection",
    }
    cue_map = {
        "lever": "Trace support first, then compare the distance from effort and load to the pivot.",
        "fixed_pulley": "A fixed pulley changes pull direction but does not make the load weight disappear.",
        "movable_pulley": "A movable pulley can reduce effort force by making the rope move farther.",
        "three_gears": "Each touching gear pair reverses direction; count the reversals.",
        "open_belt": "An uncrossed belt usually carries the same rotation direction across pulleys.",
        "crossed_belt": "A crossed belt flips the rotation direction.",
        "paper_one_fold_hole": "Unfold backward; one fold creates a mirrored hole.",
        "paper_two_fold_unfold": "Undo the last fold first; each unfold mirrors marks across that fold line.",
        "rotation_vs_reflection": "Rotation turns a shape; reflection flips it across a line.",
    }
    diagrams = {
        "lever": """```mermaid
flowchart LR
    E["Effort: push down"] --> A["Long handle / effort arm"]
    A --> P(("Pivot / fulcrum"))
    P --> B["Short load arm"]
    B --> L["Load"]
    N["Longer effort arm means less effort force"] -.-> E
```""",
        "fixed_pulley": """```mermaid
flowchart TB
    S["Ceiling support"] --> P(("Fixed pulley"))
    H["Hand pulls down"] --> R["Rope over pulley"]
    R --> P
    P --> L["Load moves up"]
    N["Key idea: changes direction"] -.-> H
```""",
        "movable_pulley": """```mermaid
flowchart TB
    S["Ceiling anchor"] --> R["Rope"]
    R --> M(("Movable pulley attached to load"))
    M --> L["Load"]
    H["Hand pulls rope farther"] --> R
    N["Less effort force, more rope distance"] -.-> H
```""",
        "three_gears": """```mermaid
flowchart LR
    A(("Gear A ↻")) -- touches --> B(("Gear B ↺"))
    B -- touches --> C(("Gear C ↻"))
    N1["1st contact reverses"] -.-> B
    N2["2nd contact reverses again"] -.-> C
```""",
        "open_belt": """```mermaid
flowchart LR
    A(("Pulley A ↻")) == open belt ==> B(("Pulley B ↻"))
    N["Uncrossed belt keeps direction"] -.-> B
```""",
        "crossed_belt": """```mermaid
flowchart LR
    A(("Pulley A ↻")) == crossed belt ==> B(("Pulley B ↺"))
    N["Crossed belt reverses direction"] -.-> B
```""",
        "paper_one_fold_hole": """```mermaid
flowchart LR
    A["Flat paper"] --> B["Fold left over right"]
    B --> C["Punch one hole near folded edge"]
    C --> D["Unfold backward"]
    D --> E["Two mirrored holes"]
```""",
        "paper_two_fold_unfold": """```mermaid
sequenceDiagram
    participant P as Paper
    participant F1 as First fold
    participant F2 as Second fold
    participant H as Hole punch
    participant U as Unfold
    P->>F1: Fold horizontally
    F1->>F2: Fold vertically
    F2->>H: Punch mark through layers
    H->>U: Undo vertical fold first
    U->>U: Mirror holes across vertical fold
    U->>U: Undo horizontal fold second
    U->>P: Final pattern shows both mirror steps
```""",
        "rotation_vs_reflection": """```mermaid
flowchart TB
    A["Original shape"] --> R["Rotation: turn around a point"]
    A --> F["Reflection: flip across a line"]
    R --> R2["Orientation turns"]
    F --> F2["Left/right order reverses"]
```""",
    }
    resolved = template if template in diagrams else "lever"
    return {
        "title": title_map[resolved],
        "teaching_cue": cue_map[resolved],
        "markdown": diagrams[resolved],
    }


MASTERY_TOOL_TYPES: tuple[type[BaseTool], ...] = (
    MasteryStatusTool,
    MasteryVisualTool,
    MasteryQuizTool,
    MasteryGradeTool,
    MasteryAssessTool,
    MasteryBuildTool,
)


__all__ = [
    "MASTERY_TOOL_NAMES",
    "MASTERY_TOOL_TYPES",
    "MasteryStatusTool",
    "MasteryVisualTool",
    "MasteryQuizTool",
    "MasteryGradeTool",
    "MasteryAssessTool",
    "MasteryBuildTool",
]
