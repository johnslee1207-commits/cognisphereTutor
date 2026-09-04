"""Tests for the Mastery Path tools — the seam between the chat-loop tutor and
the engine. They drive the full loop the tutor uses: build a path, read the
gate, pose + grade questions, assess qualitative objectives, with the active
path id injected server-side (never by the model)."""

from __future__ import annotations

import json

import pytest

from cognispheretutor.learning.storage import LearningStore
from cognispheretutor.services.session.sqlite_store import SQLiteSessionStore
from cognispheretutor.tools.mastery_tool import (
    MasteryAssessTool,
    MasteryBuildTool,
    MasteryGradeTool,
    MasteryQuizTool,
    MasteryStatusTool,
    MasteryVisualTool,
)


@pytest.fixture
def path_id(tmp_path, monkeypatch):
    """Point the LearningStore at a temp workspace and yield a stable path id."""
    monkeypatch.setattr(LearningStore, "__init__", _store_init_factory(tmp_path))
    return "test_path"


@pytest.fixture
def session_store(tmp_path, monkeypatch):
    store = SQLiteSessionStore(db_path=tmp_path / "chat.db")
    monkeypatch.setattr("cognispheretutor.services.session.get_sqlite_session_store", lambda: store)
    return store


def _store_init_factory(root):
    def _init(self, root_arg=None):  # mirrors LearningStore.__init__ signature
        from pathlib import Path

        self._root = Path(root) / "learning"
        self._root.mkdir(parents=True, exist_ok=True)

    return _init


async def _build_basic(path_id):
    build = MasteryBuildTool()
    return await build.execute(
        _mastery_path_id=path_id,
        mode="replace",
        modules=[
            {
                "name": "Module 1",
                "knowledge_points": [
                    {"name": "Truth tables", "type": "memory"},
                    {"name": "Why XOR matters", "type": "concept"},
                ],
            }
        ],
    )


# ── build ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_creates_path(path_id):
    result = await _build_basic(path_id)
    assert result.success
    payload = json.loads(result.content)
    assert payload["knowledge_points_added"] == 2
    assert payload["map"]["counts"]["total"] == 2


@pytest.mark.asyncio
async def test_build_rejects_empty_modules(path_id):
    result = await MasteryBuildTool().execute(_mastery_path_id=path_id, modules=[])
    assert result.success is False


@pytest.mark.asyncio
async def test_build_append_keeps_existing(path_id):
    await _build_basic(path_id)
    result = await MasteryBuildTool().execute(
        _mastery_path_id=path_id,
        mode="append",
        modules=[
            {"name": "Module 2", "knowledge_points": [{"name": "Adders", "type": "procedure"}]}
        ],
    )
    payload = json.loads(result.content)
    assert payload["map"]["counts"]["total"] == 3  # 2 existing + 1 appended


@pytest.mark.asyncio
async def test_build_unknown_type_defaults_to_concept(path_id):
    result = await MasteryBuildTool().execute(
        _mastery_path_id=path_id,
        modules=[{"name": "M", "knowledge_points": [{"name": "Thing", "type": "nonsense"}]}],
    )
    kp = json.loads(result.content)["map"]["modules"][0]["knowledge_points"][0]
    assert kp["type"] == "concept"


# ── status ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_empty_path_asks_for_build(path_id):
    payload = json.loads((await MasteryStatusTool().execute(_mastery_path_id=path_id)).content)
    assert payload["status"] == "empty"


@pytest.mark.asyncio
async def test_status_points_at_first_objective(path_id):
    await _build_basic(path_id)
    payload = json.loads((await MasteryStatusTool().execute(_mastery_path_id=path_id)).content)
    assert payload["status"] == "active"
    assert payload["next"]["action"] == "probe"
    assert payload["next"]["knowledge_point_type"] == "memory"


@pytest.mark.asyncio
async def test_status_honors_selected_start_point(path_id):
    await MasteryBuildTool().execute(
        _mastery_path_id=path_id,
        mode="replace",
        modules=[
            {
                "name": "California Electrical Career Orientation",
                "knowledge_points": [{"name": "Choose a career goal", "type": "concept"}],
            },
            {
                "name": "ETI / IBEW Local 11 Apprenticeship Entrance",
                "knowledge_points": [{"name": "Baseline diagnostic", "type": "procedure"}],
            },
        ],
    )

    payload = json.loads(
        (
            await MasteryStatusTool().execute(
                _mastery_path_id=path_id,
                _mastery_start_point="apprenticeship_entry",
            )
        ).content
    )

    assert payload["requested_start_point"] == "apprenticeship_entry"
    assert payload["next"]["module_name"] == "ETI / IBEW Local 11 Apprenticeship Entrance"
    assert payload["next"]["knowledge_point_name"] == "Baseline diagnostic"


@pytest.mark.asyncio
async def test_status_honors_selected_apprenticeship_subtopic(path_id):
    await MasteryBuildTool().execute(
        _mastery_path_id=path_id,
        mode="replace",
        modules=[
            {
                "id": "csphere-california_electrical_career-apprenticeship",
                "name": "ETI / IBEW Local 11 Apprenticeship Entrance",
                "knowledge_points": [
                    {
                        "id": "cec-apprentice-math-reasoning",
                        "name": "Mathematical reasoning for aptitude testing",
                        "type": "procedure",
                    },
                    {
                        "id": "cec-apprentice-reading",
                        "name": "Reading comprehension for technical instructions",
                        "type": "procedure",
                    },
                ],
            },
        ],
    )

    payload = json.loads(
        (
            await MasteryStatusTool().execute(
                _mastery_path_id=path_id,
                _mastery_start_point="apprenticeship_reading",
            )
        ).content
    )

    assert payload["requested_start_point"] == "apprenticeship_reading"
    assert payload["next"]["knowledge_point_name"] == (
        "Reading comprehension for technical instructions"
    )


@pytest.mark.asyncio
async def test_status_start_action_clears_stale_pending_question(path_id):
    await MasteryBuildTool().execute(
        _mastery_path_id=path_id,
        mode="replace",
        modules=[
            {
                "name": "California Electrical Career Orientation",
                "knowledge_points": [{"name": "Choose a career goal", "type": "procedure"}],
            },
            {
                "name": "ETI / IBEW Local 11 Apprenticeship Entrance",
                "knowledge_points": [{"name": "Baseline diagnostic", "type": "procedure"}],
            },
        ],
    )
    first_status = json.loads(
        (await MasteryStatusTool().execute(_mastery_path_id=path_id)).content
    )
    await MasteryQuizTool().execute(
        _mastery_path_id=path_id,
        knowledge_point_id=first_status["next"]["knowledge_point_id"],
        question="Which career goal?",
        expected_answer="A",
        question_type="choice",
        options=["A: Apprenticeship", "B: Contractor"],
    )

    payload = json.loads(
        (
            await MasteryStatusTool().execute(
                _mastery_path_id=path_id,
                _mastery_start_point="apprenticeship_entry",
                _mastery_start_action="start",
            )
        ).content
    )

    assert payload["cleared_pending_question"] is True
    assert payload["next"]["action"] == "probe"
    assert payload["next"]["module_name"] == "ETI / IBEW Local 11 Apprenticeship Entrance"


@pytest.mark.asyncio
async def test_visual_tool_renders_requested_mechanical_template(path_id):
    await MasteryBuildTool().execute(
        _mastery_path_id=path_id,
        mode="replace",
        modules=[
            {
                "name": "ETI / IBEW Local 11 Apprenticeship Entrance",
                "knowledge_points": [
                    {
                        "name": (
                            "Mechanical reasoning: force, levers, pulleys, gears, "
                            "and motion"
                        ),
                        "type": "concept",
                    }
                ],
            },
        ],
    )

    result = await MasteryVisualTool().execute(
        _mastery_path_id=path_id,
        knowledge_point_id="test_path_m0_kp0",
        template="lever",
    )
    payload = json.loads(result.content)

    assert result.success is True
    assert payload["status"] == "ready"
    assert payload["template"] == "lever"
    assert "```mermaid" in payload["markdown"]
    assert "Effort: push down" in payload["markdown"]


@pytest.mark.asyncio
async def test_visual_tool_auto_selects_paper_folding_for_spatial_objective(path_id):
    await MasteryBuildTool().execute(
        _mastery_path_id=path_id,
        mode="replace",
        modules=[
            {
                "name": "ETI / IBEW Local 11 Apprenticeship Entrance",
                "knowledge_points": [
                    {
                        "name": "Spatial reasoning and paper folding",
                        "type": "procedure",
                    }
                ],
            },
        ],
    )

    result = await MasteryVisualTool().execute(
        _mastery_path_id=path_id,
        knowledge_point_id="test_path_m0_kp0",
        template="auto",
    )
    payload = json.loads(result.content)

    assert result.success is True
    assert payload["template"] == "paper_one_fold_hole"
    assert "Unfold backward" in payload["markdown"]


@pytest.mark.asyncio
async def test_quiz_rejects_numeric_choice_when_correct_value_missing(path_id):
    await _build_basic(path_id)
    status = json.loads((await MasteryStatusTool().execute(_mastery_path_id=path_id)).content)

    result = await MasteryQuizTool().execute(
        _mastery_path_id=path_id,
        knowledge_point_id=status["next"]["knowledge_point_id"],
        question=(
            "A job requires 250 feet of conduit. A crew installs 150 feet on the "
            "first day, then installs 25% of the remaining length on the second "
            "day. What is the total length of conduit installed after both days?"
        ),
        expected_answer="D",
        question_type="choice",
        options=["A: 140 feet", "B: 160 feet", "C: 180 feet", "D: 200 feet"],
    )

    assert result.success is False
    assert "no option matches the computed answer (175)" in result.content


@pytest.mark.asyncio
async def test_quiz_accepts_numeric_choice_when_expected_label_matches(path_id):
    await _build_basic(path_id)
    status = json.loads((await MasteryStatusTool().execute(_mastery_path_id=path_id)).content)

    result = await MasteryQuizTool().execute(
        _mastery_path_id=path_id,
        knowledge_point_id=status["next"]["knowledge_point_id"],
        question=(
            "A job requires 250 feet of conduit. A crew installs 150 feet on the "
            "first day, then installs 25% of the remaining length on the second "
            "day. What is the total length of conduit installed after both days?"
        ),
        expected_answer="C",
        question_type="choice",
        options=["A: 140 feet", "B: 160 feet", "C: 175 feet", "D: 200 feet"],
    )

    assert result.success is True


@pytest.mark.asyncio
async def test_no_path_id_fails_closed():
    result = await MasteryStatusTool().execute(_mastery_path_id="")
    assert result.success is False


# ── quiz + grade: the deterministic objective gate ───────────────────────────


@pytest.mark.asyncio
async def test_quiz_then_grade_drives_memory_gate(path_id):
    await _build_basic(path_id)
    status = json.loads((await MasteryStatusTool().execute(_mastery_path_id=path_id)).content)
    kp_id = status["next"]["knowledge_point_id"]

    quiz, grade = MasteryQuizTool(), MasteryGradeTool()
    mastered = False
    for _ in range(3):
        await quiz.execute(
            _mastery_path_id=path_id,
            knowledge_point_id=kp_id,
            question="2+2?",
            expected_answer="4",
            question_type="short",
        )
        result = json.loads((await grade.execute(_mastery_path_id=path_id, answer="4")).content)
        assert result["is_correct"] is True
        mastered = result["mastered"]
    # 0.5 -> 0.8 -> 1.0 ≥ 0.9: mastered only after the third correct answer.
    assert mastered is True


@pytest.mark.asyncio
async def test_grade_without_pending_fails(path_id):
    await _build_basic(path_id)
    result = await MasteryGradeTool().execute(_mastery_path_id=path_id, answer="x")
    assert result.success is False


@pytest.mark.asyncio
async def test_quiz_unknown_kp_fails(path_id):
    await _build_basic(path_id)
    result = await MasteryQuizTool().execute(
        _mastery_path_id=path_id,
        knowledge_point_id="nope",
        question="?",
        expected_answer="x",
    )
    assert result.success is False


@pytest.mark.asyncio
async def test_wrong_answer_does_not_master(path_id):
    await _build_basic(path_id)
    status = json.loads((await MasteryStatusTool().execute(_mastery_path_id=path_id)).content)
    kp_id = status["next"]["knowledge_point_id"]
    await MasteryQuizTool().execute(
        _mastery_path_id=path_id, knowledge_point_id=kp_id, question="2+2?", expected_answer="4"
    )
    result = json.loads(
        (await MasteryGradeTool().execute(_mastery_path_id=path_id, answer="5")).content
    )
    assert result["is_correct"] is False
    assert result["mastered"] is False


@pytest.mark.asyncio
async def test_grade_syncs_mastery_attempt_to_question_bank(path_id, session_store):
    session = await session_store.create_session(title="Mastery Session")
    await _build_basic(path_id)
    status = json.loads((await MasteryStatusTool().execute(_mastery_path_id=path_id)).content)
    kp_id = status["next"]["knowledge_point_id"]
    await MasteryQuizTool().execute(
        _mastery_path_id=path_id,
        knowledge_point_id=kp_id,
        question="2+2?",
        expected_answer="4",
        question_type="short",
    )

    result = json.loads(
        (
            await MasteryGradeTool().execute(
                _mastery_path_id=path_id,
                _session_id=session["id"],
                _turn_id="turn_mastery_1",
                answer="5",
            )
        ).content
    )

    assert result["is_correct"] is False
    wrong_entries = await session_store.list_notebook_entries(is_correct=False)
    assert wrong_entries["total"] == 1
    entry = wrong_entries["items"][0]
    assert entry["session_title"] == "Mastery Session"
    assert entry["turn_id"] == "turn_mastery_1"
    assert entry["question"] == "2+2?"
    assert entry["question_type"] == "short_answer"
    assert entry["user_answer"] == "5"
    assert entry["correct_answer"] == "4"
    assert entry["is_correct"] is False


@pytest.mark.asyncio
async def test_choice_quiz_rejects_bare_option_labels(path_id):
    await _build_basic(path_id)
    status = json.loads((await MasteryStatusTool().execute(_mastery_path_id=path_id)).content)
    kp_id = status["next"]["knowledge_point_id"]

    result = await MasteryQuizTool().execute(
        _mastery_path_id=path_id,
        knowledge_point_id=kp_id,
        question="Which order is correct?",
        expected_answer="A",
        question_type="choice",
        options=["A", "B", "C", "D"],
    )

    assert result.success is False
    assert "full option bodies" in result.content


@pytest.mark.asyncio
async def test_choice_quiz_preserves_bodies_and_normalizes_answer(path_id, session_store):
    session = await session_store.create_session(title="Choice Mastery")
    await _build_basic(path_id)
    status = json.loads((await MasteryStatusTool().execute(_mastery_path_id=path_id)).content)
    kp_id = status["next"]["knowledge_point_id"]

    quiz = await MasteryQuizTool().execute(
        _mastery_path_id=path_id,
        knowledge_point_id=kp_id,
        question="Where is the stop condition added?",
        expected_answer="Step 6",
        question_type="choice",
        options=[
            "A: Step 2 — write the first tool",
            "B: Step 4 — test one call",
            "C: Step 6 — add the stop condition",
            "D: Step 7 — add another tool",
        ],
    )
    assert quiz.success is True

    grade = json.loads(
        (
            await MasteryGradeTool().execute(
                _mastery_path_id=path_id,
                _session_id=session["id"],
                _turn_id="turn_choice_1",
                answer="C",
            )
        ).content
    )
    assert grade["is_correct"] is True

    entries = await session_store.list_notebook_entries()
    entry = entries["items"][0]
    assert entry["options"] == {
        "A": "Step 2 — write the first tool",
        "B": "Step 4 — test one call",
        "C": "Step 6 — add the stop condition",
        "D": "Step 7 — add another tool",
    }
    assert entry["correct_answer"] == "C"
    assert entry["user_answer"] == "C"
    assert entry["is_correct"] is True


# ── assess: the qualitative gate ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_assess_passes_concept(path_id):
    await _build_basic(path_id)
    # Drive past the memory objective so status reaches the concept one.
    status = json.loads((await MasteryStatusTool().execute(_mastery_path_id=path_id)).content)
    mem_kp = status["next"]["knowledge_point_id"]
    for _ in range(3):
        await MasteryQuizTool().execute(
            _mastery_path_id=path_id, knowledge_point_id=mem_kp, question="q", expected_answer="a"
        )
        await MasteryGradeTool().execute(_mastery_path_id=path_id, answer="a")

    status2 = json.loads((await MasteryStatusTool().execute(_mastery_path_id=path_id)).content)
    concept_kp = status2["next"]["knowledge_point_id"]
    assert status2["next"]["action"] == "probe"
    assert status2["next"]["knowledge_point_type"] == "concept"

    result = json.loads(
        (
            await MasteryAssessTool().execute(
                _mastery_path_id=path_id, knowledge_point_id=concept_kp, passed=True, feedback="ok"
            )
        ).content
    )
    assert result["mastered"] is True
    assert result["next"]["action"] == "complete"


@pytest.mark.asyncio
async def test_assess_rejects_quantitative_type(path_id):
    await _build_basic(path_id)
    status = json.loads((await MasteryStatusTool().execute(_mastery_path_id=path_id)).content)
    mem_kp = status["next"]["knowledge_point_id"]  # a memory objective
    result = await MasteryAssessTool().execute(
        _mastery_path_id=path_id, knowledge_point_id=mem_kp, passed=True
    )
    assert result.success is False
