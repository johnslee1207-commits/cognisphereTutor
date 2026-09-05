from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_mastery_quiz_reuses_existing_pending_question(tmp_path, monkeypatch) -> None:
    from cognispheretutor.capabilities.mastery.tools import MasteryQuizTool
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
                id="m1",
                name="AI Infra",
                order=0,
                knowledge_points=[
                    KnowledgePoint(
                        id="kp-runtime",
                        name="Runtime readiness",
                        type=KnowledgeType.PROCEDURE,
                        module_id="m1",
                    )
                ],
            )
        ],
        knowledge_types={"kp-runtime": KnowledgeType.PROCEDURE},
    )
    store.save(progress)
    monkeypatch.setattr(storage_mod, "LearningStore", lambda: real_store_cls(tmp_path))

    tool = MasteryQuizTool()
    first = await tool.execute(
        _mastery_path_id="csphere-ai_infra",
        knowledge_point_id="kp-runtime",
        question="Which action comes first?",
        expected_answer="A",
        question_type="choice",
        options=["A: Inspect readiness", "B: Mutate the host"],
    )
    second = await tool.execute(
        _mastery_path_id="csphere-ai_infra",
        knowledge_point_id="kp-runtime",
        question="Which action comes first, again?",
        expected_answer="B",
        question_type="choice",
        options=["A: Mutate the host", "B: Inspect readiness"],
    )

    assert first.success is True
    assert second.success is True
    payload = json.loads(second.content)
    assert payload["status"] == "already_pending"
    assert payload["question"] == "Which action comes first?"
    assert "Do not create or ask a duplicate question" in payload["instruction"]
    updated = store.load("csphere-ai_infra")
    assert updated is not None
    assert updated.pending_question is not None
    assert updated.pending_question.expected_answer == "A"


@pytest.mark.asyncio
async def test_mastery_quiz_blocks_new_objective_while_question_pending(
    tmp_path,
    monkeypatch,
) -> None:
    from cognispheretutor.capabilities.mastery.tools import MasteryQuizTool
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
                id="m1",
                name="AI Infra",
                order=0,
                knowledge_points=[
                    KnowledgePoint(
                        id="kp-runtime",
                        name="Runtime readiness",
                        type=KnowledgeType.PROCEDURE,
                        module_id="m1",
                    ),
                    KnowledgePoint(
                        id="kp-observe",
                        name="Observability",
                        type=KnowledgeType.PROCEDURE,
                        module_id="m1",
                    ),
                ],
            )
        ],
        knowledge_types={
            "kp-runtime": KnowledgeType.PROCEDURE,
            "kp-observe": KnowledgeType.PROCEDURE,
        },
    )
    store.save(progress)
    monkeypatch.setattr(storage_mod, "LearningStore", lambda: real_store_cls(tmp_path))

    tool = MasteryQuizTool()
    first = await tool.execute(
        _mastery_path_id="csphere-ai_infra",
        knowledge_point_id="kp-runtime",
        question="Which action comes first?",
        expected_answer="A",
        question_type="choice",
        options=["A: Inspect readiness", "B: Mutate the host"],
    )
    blocked = await tool.execute(
        _mastery_path_id="csphere-ai_infra",
        knowledge_point_id="kp-observe",
        question="Which signal is best?",
        expected_answer="A",
        question_type="choice",
        options=["A: Correlated timeline", "B: One loud alert"],
    )

    assert first.success is True
    assert blocked.success is False
    assert "already awaiting an answer" in blocked.content
    updated = store.load("csphere-ai_infra")
    assert updated is not None
    assert updated.pending_question is not None
    assert updated.pending_question.knowledge_point_id == "kp-runtime"


@pytest.mark.asyncio
async def test_mastery_quiz_rejects_mismatched_sequence_answer(tmp_path, monkeypatch) -> None:
    from cognispheretutor.capabilities.mastery.tools import MasteryQuizTool
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
        book_id="csphere-california_electrical_career",
        modules=[
            LearningModule(
                id="m1",
                name="Entrance Exam",
                order=0,
                knowledge_points=[
                    KnowledgePoint(
                        id="cec-apprentice-numerical-reasoning",
                        name="Numerical reasoning, sequences, and data interpretation",
                        type=KnowledgeType.PROCEDURE,
                        module_id="m1",
                    )
                ],
            )
        ],
        knowledge_types={"cec-apprentice-numerical-reasoning": KnowledgeType.PROCEDURE},
    )
    store.save(progress)
    monkeypatch.setattr(storage_mod, "LearningStore", lambda: real_store_cls(tmp_path))

    result = await MasteryQuizTool().execute(
        _mastery_path_id="csphere-california_electrical_career",
        knowledge_point_id="cec-apprentice-numerical-reasoning",
        question="Find the next number: 2, 5, 11, 20, 32, ?",
        expected_answer="B",
        question_type="choice",
        options=["A: 44", "B: 95", "C: 47", "D: 64"],
    )

    assert result.success is False
    assert "computed answer is 47" in result.content
    updated = store.load("csphere-california_electrical_career")
    assert updated is not None
    assert updated.pending_question is None


@pytest.mark.asyncio
async def test_mastery_quiz_accepts_multiply_add_sequence_answer(tmp_path, monkeypatch) -> None:
    from cognispheretutor.capabilities.mastery.tools import MasteryQuizTool
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
        book_id="csphere-california_electrical_career",
        modules=[
            LearningModule(
                id="m1",
                name="Entrance Exam",
                order=0,
                knowledge_points=[
                    KnowledgePoint(
                        id="cec-apprentice-numerical-reasoning",
                        name="Numerical reasoning, sequences, and data interpretation",
                        type=KnowledgeType.PROCEDURE,
                        module_id="m1",
                    )
                ],
            )
        ],
        knowledge_types={"cec-apprentice-numerical-reasoning": KnowledgeType.PROCEDURE},
    )
    store.save(progress)
    monkeypatch.setattr(storage_mod, "LearningStore", lambda: real_store_cls(tmp_path))

    result = await MasteryQuizTool().execute(
        _mastery_path_id="csphere-california_electrical_career",
        knowledge_point_id="cec-apprentice-numerical-reasoning",
        question="Find the next number: 3, 7, 15, 31, 63, ?",
        expected_answer="C",
        question_type="choice",
        options=["A: 95", "B: 126", "C: 127", "D: 128"],
    )

    assert result.success is True
    updated = store.load("csphere-california_electrical_career")
    assert updated is not None
    assert updated.pending_question is not None
    assert updated.pending_question.expected_answer == "C"
