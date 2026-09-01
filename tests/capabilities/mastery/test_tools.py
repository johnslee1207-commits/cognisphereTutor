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

