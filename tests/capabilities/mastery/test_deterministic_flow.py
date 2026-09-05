from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_deterministic_flow_teaches_asks_and_grades_without_llm(tmp_path, monkeypatch) -> None:
    import cognispheretutor.capabilities.mastery.deterministic_flow as flow
    import cognispheretutor.learning.storage as storage_mod
    from cognispheretutor.core.context import UnifiedContext
    from cognispheretutor.core.stream_bus import StreamBus
    from cognispheretutor.learning.models import (
        KnowledgePoint,
        KnowledgeType,
        LearningModule,
        LearningProgress,
    )

    real_store_cls = storage_mod.LearningStore
    store = real_store_cls(tmp_path)
    progress = LearningProgress(
        book_id="csphere-test_domain",
        modules=[
            LearningModule(
                id="m1",
                name="Test Module",
                order=0,
                knowledge_points=[
                    KnowledgePoint(
                        id="kp1",
                        name="Test concept",
                        type=KnowledgeType.CONCEPT,
                        module_id="m1",
                    )
                ],
            )
        ],
        knowledge_types={"kp1": KnowledgeType.CONCEPT},
    )
    store.save(progress)
    monkeypatch.setattr(flow, "LearningStore", lambda: real_store_cls(tmp_path))

    async def waiter():
        return {"text": "A", "answers": [{"questionId": "q", "text": "A"}]}

    context = UnifiedContext(
        session_id="s1",
        user_message="continue",
        active_capability="mastery_path",
        metadata={
            "mastery_path_id": "csphere-test_domain",
            "turn_id": "t1",
            "wait_for_user_reply": waiter,
        },
    )
    bus = StreamBus()

    handled = await flow.maybe_run_deterministic_mastery_flow(context, bus)
    await bus.close()
    events = [event async for event in bus.subscribe()]
    updated = store.load("csphere-test_domain")

    assert handled is True
    assert updated is not None
    assert updated.pending_question is None
    assert updated.qualitative_mastery["kp1"] is True
    assert any(event.type == "content" and "## Test concept" in event.content for event in events)
    assert any(
        event.type == "tool_result"
        and (event.metadata.get("tool_metadata") or {}).get("ask_user")
        for event in events
    )
    assert any(
        event.type == "progress"
        and event.metadata.get("ask_user_resolved") is True
        for event in events
    )


@pytest.mark.asyncio
async def test_explicit_start_point_clears_stale_pending_question(tmp_path, monkeypatch) -> None:
    import time

    import cognispheretutor.capabilities.mastery.deterministic_flow as flow
    import cognispheretutor.learning.storage as storage_mod
    from cognispheretutor.core.context import UnifiedContext
    from cognispheretutor.core.stream_bus import StreamBus
    from cognispheretutor.learning.models import (
        KnowledgePoint,
        KnowledgeType,
        LearningModule,
        LearningProgress,
        PendingQuestion,
    )

    real_store_cls = storage_mod.LearningStore
    store = real_store_cls(tmp_path)
    progress = LearningProgress(
        book_id="csphere-test_domain",
        modules=[
            LearningModule(
                id="m1",
                name="Old Module",
                order=0,
                knowledge_points=[
                    KnowledgePoint(
                        id="old-kp",
                        name="Old pending topic",
                        type=KnowledgeType.PROCEDURE,
                        module_id="m1",
                    )
                ],
            ),
            LearningModule(
                id="m2",
                name="Entrance Exam",
                order=1,
                knowledge_points=[
                    KnowledgePoint(
                        id="new-kp",
                        name="Mathematical reasoning for aptitude testing",
                        type=KnowledgeType.CONCEPT,
                        module_id="m2",
                    )
                ],
            ),
        ],
        knowledge_types={
            "old-kp": KnowledgeType.PROCEDURE,
            "new-kp": KnowledgeType.CONCEPT,
        },
        pending_question=PendingQuestion(
            question_id="old-question",
            knowledge_point_id="old-kp",
            module_id="m1",
            prompt="Old question?",
            question_type="choice",
            expected_answer="A",
            options=["A: old", "B: stale"],
            created_at=time.time(),
        ),
    )
    store.save(progress)
    monkeypatch.setattr(flow, "LearningStore", lambda: real_store_cls(tmp_path))
    monkeypatch.setattr(
        flow,
        "next_objective_for_start_point",
        lambda current, start_point: type(
            "Step",
            (),
            {"action": "practice", "knowledge_point_id": "new-kp"},
        )(),
    )

    async def waiter():
        return {"text": "A", "answers": [{"questionId": "q", "text": "A"}]}

    context = UnifiedContext(
        session_id="s1",
        user_message="Start from math reasoning.",
        active_capability="mastery_path",
        metadata={
            "mastery_path_id": "csphere-test_domain",
            "mastery_start_point": "apprenticeship_math",
            "mastery_start_action": "start",
            "turn_id": "t1",
            "wait_for_user_reply": waiter,
        },
    )
    bus = StreamBus()

    handled = await flow.maybe_run_deterministic_mastery_flow(context, bus)
    await bus.close()
    events = [event async for event in bus.subscribe()]

    assert handled is True
    assert any(
        event.type == "content"
        and "## Mathematical reasoning for aptitude testing" in event.content
        for event in events
    )
    assert not any(event.type == "tool_result" and "Old question?" in event.content for event in events)
