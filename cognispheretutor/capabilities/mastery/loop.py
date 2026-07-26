"""Mastery path loop-capability hooks."""

from __future__ import annotations

from importlib import resources
import json
import re
import sqlite3
from typing import Any

from cognispheretutor.capabilities.mastery.tools import MASTERY_TOOL_NAMES
from cognispheretutor.capabilities.protocol import PromptBlock
from cognispheretutor.core.context import UnifiedContext
from cognispheretutor.learning.cognisphere_seed import domain_from_path_id


class MasteryLoopCapability:
    """Turn-scoped integration for mastery-path tutoring.

    Reuses the full chat tool surface (rag / read_source / ask_user / … under
    the same user toggles as chat) and adds the mastery engine tools on top.
    """

    name = "mastery"
    owned_tools = MASTERY_TOOL_NAMES

    def is_active(self, context: UnifiedContext) -> bool:
        return bool(context.metadata.get("mastery_mode"))

    def system_block(
        self,
        context: UnifiedContext,
        *,
        language: str,
        prompts: dict[str, Any],
    ) -> PromptBlock | None:
        if not self.is_active(context):
            return None
        override = _prompt_text(prompts, ("mastery", "system"))
        content = override or _load_system_prompt(language)
        guard = _cognisphere_pack_guard(context, language)
        if guard:
            content = f"{content}\n\n{guard}"
        return PromptBlock("mastery_tutor", content)

    def augment_kwargs(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        context: UnifiedContext,
    ) -> dict[str, Any]:
        if self.is_active(context) and tool_name in MASTERY_TOOL_NAMES:
            updated = dict(kwargs)
            updated["_mastery_path_id"] = str(context.metadata.get("mastery_path_id") or "").strip()
            updated["_session_id"] = str(context.session_id or "").strip()
            updated["_turn_id"] = str(context.metadata.get("turn_id") or "").strip()
            return updated
        return kwargs

    def pre_loop_seed(self, context: UnifiedContext) -> str:
        if not self.is_active(context):
            return ""
        auto_advance = _auto_advance_overview_if_ready(context)
        stale_pending = _clear_unpresented_pending_after_failed_turn(context)
        status = _deterministic_mastery_status(context)
        if not status:
            return ""
        grounding = _deterministic_plugin_grounding(context)
        if grounding:
            context.metadata["plugin_graph_grounding_injected"] = True
        lesson_contract = _deterministic_lesson_contract(context)
        if lesson_contract:
            context.metadata["mastery_lesson_contract_injected"] = True
        context.metadata["mastery_status_injected"] = True
        orphan_answer = _orphan_quiz_answer_guard(context)
        pending_answer = _pending_text_answer_guard(context)
        directive = _mastery_turn_directive(context)
        return "\n\n".join(
            block
            for block in (
                auto_advance,
                stale_pending,
                status,
                grounding,
                lesson_contract,
                orphan_answer,
                pending_answer,
                directive,
            )
            if block
        )


def _prompt_text(prompts: dict[str, Any], path: tuple[str, ...]) -> str:
    value: Any = prompts
    for key in path:
        if not isinstance(value, dict):
            return ""
        value = value.get(key)
    return value if isinstance(value, str) and value else ""


def _load_system_prompt(language: str) -> str:
    lang = "zh" if language.lower().startswith("zh") else "en"
    prompt = resources.files(__package__).joinpath("prompts", lang, "system.md")
    return prompt.read_text(encoding="utf-8").strip()


def _cognisphere_pack_guard(context: UnifiedContext, language: str) -> str:
    path_id = str(context.metadata.get("mastery_path_id") or "").strip()
    if not path_id.startswith("csphere-"):
        return ""
    domain = path_id.removeprefix("csphere-") or "unknown"
    plugin_policy = _plugin_mastery_prompt_contract(domain, language)
    if language.lower().startswith("zh"):
        guard = (
            "### Cognisphere 学习插件绑定\n"
            f"- 当前学习路径是 `{path_id}`，对应本地插件域 `{domain}`。\n"
            "- 你的教学内容必须优先来自当前 Mastery Path、Cognisphere Learning Plugin "
            "导入的 pack 知识、以及该插件运行时工具返回的结果。\n"
            "- 需要确认进度、下一个知识点、测验或记录掌握度时，调用 mastery 工具；不要另建 "
            "`unified_*` 或临时学习路径。\n"
            "- 不要把 AWS/AP/LeetCode 的学习内容说成来自模型训练数据；若用户询问来源，说明它来自"
            "本地 Cognisphere Learning Plugin pack/运行时。如果 pack 内容不足，只说明缺口并引导"
            "补充或刷新 pack。\n"
            "- 通用语言组织、鼓励、提问方式可以由你完成；事实性教学点、路径顺序、评测口径必须服从"
            "本地 pack 和工具结果。"
        )
        if plugin_policy:
            guard = f"{guard}\n\n### Plugin 教学契约\n{plugin_policy}"
        return guard
    guard = (
        "### Cognisphere Learning Plugin Binding\n"
        f"- The active learning path is `{path_id}`, backed by the local plugin domain `{domain}`.\n"
        "- Teaching content must first come from the current Mastery Path, the imported "
        "Cognisphere Learning Plugin pack knowledge, and results returned by that plugin runtime.\n"
        "- Use mastery tools to check status, pick the next item, quiz, or record mastery; do "
        "not create a new `unified_*` or ad-hoc learning path.\n"
        "- Do not describe AWS/AP/LeetCode learning content as coming from model training data. "
        "If the user asks about sources, say it comes from the local Cognisphere Learning Plugin "
        "pack/runtime. If the pack is sparse, identify the gap and guide them to refresh or extend it.\n"
        "- You may provide generic wording, encouragement, and Socratic scaffolding, but factual "
        "learning points, path order, and assessment criteria must follow the local pack and tool results."
    )
    if plugin_policy:
        guard = f"{guard}\n\n### Plugin Teaching Contract\n{plugin_policy}"
    return guard


def _plugin_mastery_prompt_contract(domain: str, language: str) -> str:
    try:
        from cognispheretutor.integrations.cognisphere.registry_client import list_plugins

        discovery = list_plugins()
    except Exception:
        return ""
    plugin = next(
        (
            item
            for item in list(discovery.get("plugins") or [])
            if isinstance(item, dict) and item.get("domain") == domain
        ),
        None,
    )
    if not plugin:
        return ""
    tutor_pack = plugin.get("tutor_pack") or {}
    if not isinstance(tutor_pack, dict):
        return ""
    contract = tutor_pack.get("mastery_prompt_contract") or tutor_pack.get("teaching_policy")
    if not isinstance(contract, dict):
        return ""
    lang_key = "zh" if language.lower().startswith("zh") else "en"
    lines = contract.get(lang_key) or contract.get("instructions") or []
    if isinstance(lines, str):
        return lines.strip()
    if not isinstance(lines, list):
        return ""
    rendered = [f"- {str(line).strip()}" for line in lines if str(line).strip()]
    return "\n".join(rendered)


def _deterministic_mastery_status(context: UnifiedContext) -> str:
    path_id = str(context.metadata.get("mastery_path_id") or "").strip()
    if not path_id:
        return ""
    try:
        from cognispheretutor.learning.policy import map_summary, next_objective
        from cognispheretutor.learning.service import LearningService
        from cognispheretutor.learning.storage import LearningStore

        progress = LearningService(LearningStore()).get_or_create(path_id)
        if not any(module.knowledge_points for module in progress.modules):
            payload: dict[str, Any] = {
                "status": "empty",
                "message": "No mastery path has been built yet.",
            }
        else:
            full_map = map_summary(progress)
            payload = {
                "status": "active",
                "next": next_objective(progress).to_dict(),
                "map": _compact_mastery_map(full_map, next_objective(progress).to_dict()),
            }
    except Exception:
        return ""
    return (
        "### Deterministic Mastery Status\n"
        "This block was loaded from the local mastery engine before the LLM "
        "answered. Use it as the source of truth for the current objective, "
        "path order, and whether a plan exists. Do not claim the plan is "
        "missing unless this block says status is empty.\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"
    )


def _compact_mastery_map(
    full_map: dict[str, Any],
    next_step: dict[str, Any],
) -> dict[str, Any]:
    """Keep prompt grounding small while preserving graph-driven path order."""

    current_module_id = str(next_step.get("module_id") or "")
    current_kp_id = str(next_step.get("knowledge_point_id") or "")
    modules: list[dict[str, Any]] = []
    for module in list(full_map.get("modules") or []):
        if not isinstance(module, dict):
            continue
        compact_module: dict[str, Any] = {
            "id": module.get("id"),
            "name": module.get("name"),
            "order": module.get("order"),
            "mastered": module.get("mastered"),
            "total": module.get("total"),
        }
        if str(module.get("id") or "") == current_module_id:
            kps = [kp for kp in list(module.get("knowledge_points") or []) if isinstance(kp, dict)]
            current_idx = next(
                (
                    idx
                    for idx, kp in enumerate(kps)
                    if str(kp.get("id") or "") == current_kp_id
                ),
                0,
            )
            start = max(0, current_idx - 1)
            compact_module["knowledge_points_window"] = kps[start : current_idx + 4]
        modules.append(compact_module)
    return {
        "counts": full_map.get("counts"),
        "complete": full_map.get("complete"),
        "due_reviews": full_map.get("due_reviews"),
        "modules": modules,
        "note": (
            "Prompt map is compact. Use mastery_status for the full 46-objective "
            "graph when detailed path inspection is needed."
        ),
    }


def _deterministic_plugin_grounding(context: UnifiedContext) -> str:
    path_id = str(context.metadata.get("mastery_path_id") or "").strip()
    domain = domain_from_path_id(path_id)
    if not domain:
        return ""
    try:
        from cognispheretutor.integrations.cognisphere.grounding import (
            build_plugin_grounding_seed,
        )
        from cognispheretutor.learning.policy import next_objective
        from cognispheretutor.learning.service import LearningService
        from cognispheretutor.learning.storage import LearningStore

        progress = LearningService(LearningStore()).get_or_create(path_id)
        if not any(module.knowledge_points for module in progress.modules):
            objective: dict[str, Any] = {}
        else:
            objective = next_objective(progress).to_dict()
        return build_plugin_grounding_seed(
            domain=domain,
            objective=objective,
            learner_goal=context.user_message,
        )
    except Exception:
        return ""


def _deterministic_lesson_contract(context: UnifiedContext) -> str:
    path_id = str(context.metadata.get("mastery_path_id") or "").strip()
    domain = domain_from_path_id(path_id) or ""
    try:
        from cognispheretutor.capabilities.mastery.lesson_contract import (
            build_lesson_contract_seed,
        )
        from cognispheretutor.learning.policy import map_summary, next_objective
        from cognispheretutor.learning.service import LearningService
        from cognispheretutor.learning.storage import LearningStore

        progress = LearningService(LearningStore()).get_or_create(path_id)
        if not any(module.knowledge_points for module in progress.modules):
            return ""
        return build_lesson_contract_seed(
            domain=domain,
            learner_goal=context.user_message,
            next_step=next_objective(progress),
            map_summary=map_summary(progress),
        )
    except Exception:
        return ""


def _orphan_quiz_answer_guard(context: UnifiedContext) -> str:
    path_id = str(context.metadata.get("mastery_path_id") or "").strip()
    if not path_id or not _looks_like_quiz_answer(context.user_message):
        return ""
    try:
        from cognispheretutor.learning.policy import next_objective
        from cognispheretutor.learning.service import LearningService
        from cognispheretutor.learning.storage import LearningStore

        progress = LearningService(LearningStore()).get_or_create(path_id)
        step = next_objective(progress).to_dict()
    except Exception:
        return ""
    if step.get("action") == "answer_pending":
        return ""
    payload = {
        "status": "orphan_quiz_answer",
        "learner_answer": str(context.user_message or "").strip(),
        "next": step,
        "required_repair": [
            "Do not treat this answer as correct or incorrect because no pending mastery question is registered.",
            "Do not advance to the next lesson.",
            "Briefly say the previous quiz was not registered as an interactive mastery card.",
            "Re-register one equivalent quick check for the same current objective using mastery_quiz, then present it with ask_user.",
        ],
    }
    return (
        "### Mastery Orphan Quiz Answer Guard\n"
        "The learner appears to be answering a multiple-choice or true/false quiz, "
        "but the local mastery engine has no pending question to grade. This means "
        "the prior question was likely written as plain text instead of being "
        "registered with mastery_quiz + ask_user. Follow the repair instructions; "
        "never advance on an ungraded orphan answer.\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"
    )


def _pending_text_answer_guard(context: UnifiedContext) -> str:
    path_id = str(context.metadata.get("mastery_path_id") or "").strip()
    if not path_id:
        return ""
    answer = _extract_quiz_answer(context.user_message)
    if not answer:
        return ""
    try:
        from cognispheretutor.learning.policy import next_objective
        from cognispheretutor.learning.service import LearningService
        from cognispheretutor.learning.storage import LearningStore

        progress = LearningService(LearningStore()).get_or_create(path_id)
        step = next_objective(progress).to_dict()
    except Exception:
        return ""
    if step.get("action") != "answer_pending":
        return ""
    payload = {
        "status": "pending_text_answer",
        "extracted_answer": answer,
        "next": step,
        "required_action": [
            f"First call mastery_grade with answer={answer!r}.",
            "Do not ask the learner to answer the same question again.",
            "If mastery_grade.mastered is true, teach the next mini-lesson before any new quiz.",
            "If mastery_grade.mastered is false, give brief feedback and ask one replacement quick check.",
        ],
    }
    return (
        "### Mastery Pending Text Answer Guard\n"
        "The learner answered a pending mastery question in ordinary chat text. "
        "Treat the extracted answer as the learner's answer and grade it before "
        "doing anything else.\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"
    )


def _looks_like_quiz_answer(message: str) -> bool:
    return bool(_extract_quiz_answer(message))


def _extract_quiz_answer(message: str) -> str:
    text = str(message or "").strip()
    if not text:
        return ""
    exact = re.fullmatch(r"(?i)([a-d]|true|false|t|f|yes|no|对|错|正确|错误)", text)
    if exact:
        return _normalize_quiz_answer(exact.group(1))
    patterns = (
        r"(?i)\b(?:answer|option|choice|选项|答案)\s*(?:is|=|:|：)?\s*([a-d])\b",
        r"(?i)\b(?:answer|option|choice)\b.{0,80}?\b(?:is|=|:)\s*([a-d])\b",
        r"(?i)\bmy\s+(?:answer|option|choice)\s*(?:is|=|:)?\s*([a-d])\b",
        r"(?i)\b([a-d])\s*(?:is my answer|is correct|should be correct)\b",
        r"(?i)\b(?:answer|option|choice)\s*(?:is|=|:)?\s*(true|false|yes|no)\b",
        r"(?:答案|选项)\s*(?:是|为|=|:|：)?\s*(对|错|正确|错误)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _normalize_quiz_answer(match.group(1))
    return ""


def _normalize_quiz_answer(value: str) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if lowered in {"t", "true", "yes"} or text in {"对", "正确"}:
        return "true"
    if lowered in {"f", "false", "no"} or text in {"错", "错误"}:
        return "false"
    if re.fullmatch(r"(?i)[a-d]", text):
        return text.upper()
    return text


def _clear_unpresented_pending_after_failed_turn(context: UnifiedContext) -> str:
    path_id = str(context.metadata.get("mastery_path_id") or "").strip()
    session_id = str(context.session_id or "").strip()
    if not path_id or not session_id:
        return ""
    try:
        from cognispheretutor.learning.service import LearningService
        from cognispheretutor.learning.storage import LearningStore
        from cognispheretutor.services.path_service import get_path_service

        service = LearningService(LearningStore())
        progress = service.get_or_create(path_id)
        pending = progress.pending_question
        if pending is None:
            return ""
        db_path = get_path_service().get_chat_history_db()
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            last_assistant = conn.execute(
                """
                SELECT created_at FROM messages
                WHERE session_id = ? AND role = 'assistant'
                ORDER BY created_at DESC LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            last_turn = conn.execute(
                """
                SELECT status, error FROM turns
                WHERE session_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        last_assistant_at = float(last_assistant["created_at"]) if last_assistant else 0.0
        latest_failed = bool(last_turn and str(last_turn["status"] or "") == "failed")
        if not latest_failed or float(pending.created_at or 0.0) <= last_assistant_at:
            return ""
        cleared = {
            "question": pending.prompt,
            "knowledge_point_id": pending.knowledge_point_id,
            "created_at": pending.created_at,
            "last_assistant_at": last_assistant_at,
            "failed_turn_error": str(last_turn["error"] or "") if last_turn else "",
        }
        service.clear_pending_question(progress)
    except Exception:
        return ""
    return (
        "### Mastery Stale Pending Cleanup\n"
        "Tutor cleared a pending mastery question that was created after the last "
        "successful assistant message by a failed/interrupted turn, so it was never "
        "shown as an answerable card. Continue from the current objective in "
        "lesson-first order.\n"
        f"```json\n{json.dumps(cleared, ensure_ascii=False)}\n```"
    )


def _auto_advance_overview_if_ready(context: UnifiedContext) -> str:
    path_id = str(context.metadata.get("mastery_path_id") or "").strip()
    if not path_id:
        return ""
    try:
        from cognispheretutor.learning.policy import next_objective
        from cognispheretutor.learning.service import LearningService
        from cognispheretutor.learning.storage import LearningStore

        service = LearningService(LearningStore())
        progress = service.get_or_create(path_id)
        step = next_objective(progress)
        if not _is_generated_overview_step(step.to_dict()):
            return ""
        answer = str(context.user_message or "").strip()
        if not _looks_like_overview_understanding(answer):
            return ""
        service.record_qualitative(
            progress,
            step.knowledge_point_id,
            passed=True,
            evidence=f"Auto-advanced generated overview after learner response: {answer[:240]}",
        )
        context.metadata["mastery_overview_auto_advanced"] = True
        next_step = next_objective(progress).to_dict()
    except Exception:
        return ""
    return (
        "### Mastery Auto Advance\n"
        "Tutor marked the generated learning-path overview as mastered because "
        "the learner already explained its purpose. Do not repeat methodology; "
        "begin the next real content objective now.\n"
        f"```json\n{json.dumps({'advanced': True, 'next': next_step}, ensure_ascii=False)}\n```"
    )


def _is_generated_overview_step(step: dict[str, Any]) -> bool:
    kp_id = str(step.get("knowledge_point_id") or "")
    module_id = str(step.get("module_id") or "")
    name = str(step.get("knowledge_point_name") or "").lower()
    return (
        kp_id.startswith("ov-")
        or module_id.endswith("-overview")
        or ("cognisphere" in name and "certification" in name)
    )


def _looks_like_overview_understanding(answer: str) -> bool:
    text = answer.strip().lower()
    if len(text) < 12:
        return False
    tokens = set(re.findall(r"[a-zA-Z0-9]{2,}|[\u4e00-\u9fff]+", text))
    signals = {
        "apply",
        "assess",
        "big",
        "content",
        "direction",
        "exam",
        "level",
        "overview",
        "pass",
        "picture",
        "plan",
        "specific",
        "study",
        "systematically",
        "understand",
        "理解",
        "系统",
        "方向",
        "考试",
        "内容",
        "掌握",
        "学习",
    }
    return bool(tokens & signals)


def _mastery_turn_directive(context: UnifiedContext) -> str:
    language = str(context.language or "en").lower()
    if language.startswith("zh"):
        return (
            "### Mastery Turn Directive\n"
            "- 本轮必须进入教学流，不要再用“你想学哪个/请选择方向”的菜单式反问来结束。\n"
            "- 不要询问学习者想用选择题、判断题还是自由回答；默认每个 mini-lesson 后直接出一个"
            " multiple-choice quick quiz 卡片。\n"
            "- 如果用户已理解学习路径概览，或出现 `Mastery Auto Advance`，不要继续解释平台方法论；"
            "直接开始 `next` 指向的 AWS/AP/LeetCode 内容知识点。\n"
            "- 开场最多 2 句话，随后进入内容讲解；不要反复介绍 Cognisphere、Mastery Path 或学习循环。\n"
            "- 每轮只推进一个知识点。对 concept/design：先给一个适合新手的短讲解，再要求学习者"
            "完成一个默认 multiple-choice quick quiz 卡片；自由复述只有在 lesson contract 要求时才必答。\n"
            "- 对 memory/procedure：使用 mastery_quiz + ask_user 出题；不要把题目做成普通文本菜单，"
            "也不要让学习者提供 knowledge_point_id、题目或选项。\n"
            "- 如果刚刚通过 mastery_grade/mastery_assess 掌握了上一知识点，下一步必须先讲解 next "
            "指向的新知识点；不要把多个 quick quiz 卡片连续串起来。\n"
            "- 如果 grounding 的 `status` 是 missing，明确说本地图谱/pack 对当前点还稀疏，并只给"
            "路径层面的引导，不要补充未经本地 grounding 支持的事实。"
        )
    return (
        "### Mastery Turn Directive\n"
        "- This turn must enter the tutoring flow; do not finish with a menu asking "
        "what the learner wants to study.\n"
        "- Do not ask whether the learner wants multiple choice, true/false, or free "
        "response. After every mini-lesson, default to one multiple-choice quick "
        "quiz card.\n"
        "- If the learner already understands the path overview, or a `Mastery Auto "
        "Advance` block is present, do not explain platform methodology again; "
        "start the AWS/AP/LeetCode content objective named by `next`.\n"
        "- Use at most 2 opening sentences, then teach content. Do not repeatedly "
        "explain Cognisphere, Mastery Path, or the learning loop.\n"
        "- Advance only one objective per turn. For concept/design objectives: give "
        "a beginner-friendly mini-lesson, then complete one default multiple-choice "
        "quick quiz card; free response is required only when the lesson contract "
        "requires it.\n"
        "- For memory/procedure objectives: use mastery_quiz + ask_user; do not turn "
        "the quiz into a plain text menu, and do not ask the learner to provide "
        "knowledge_point_id, question text, or options.\n"
        "- If mastery_grade/mastery_assess just marked the previous objective mastered, "
        "the next step must teach the new objective named by `next` before any "
        "new quick quiz; do not chain quiz cards back-to-back.\n"
        "- If grounding `status` is missing, say the local graph/pack is sparse for "
        "this objective and limit the answer to path-level guidance instead of "
        "adding ungrounded factual claims."
    )


__all__ = ["MasteryLoopCapability"]
