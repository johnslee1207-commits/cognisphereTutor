from __future__ import annotations

import json
import re

from cognispheretutor.capabilities.mastery.lesson_contract import build_lesson_contract_seed
from cognispheretutor.learning.policy import NextStep


def _payload(seed: str) -> dict:
    match = re.search(r"```json\n(.*?)\n```", seed, re.S)
    assert match
    return json.loads(match.group(1))


def test_lesson_contract_guides_absolute_beginner_concept_flow() -> None:
    seed = build_lesson_contract_seed(
        domain="aws_certification",
        learner_goal="I am a complete beginner and want the full certificate path",
        next_step=NextStep(
            action="assess",
            knowledge_point_id="obj-cloud_concepts",
            knowledge_point_name="Cloud Concepts",
            knowledge_point_type="concept",
            status="learning",
        ),
        map_summary={
            "counts": {"total": 46, "mastered": 0, "learning": 1, "new": 45},
            "modules": [
                {
                    "id": "m1",
                    "name": "Learning objectives",
                    "total": 8,
                    "mastered": 0,
                    "knowledge_points": [{"name": "Cloud Concepts"}],
                }
            ],
        },
    )

    payload = _payload(seed)

    assert payload["learner_profile"]["level"] == "absolute_beginner"
    assert payload["learner_profile"]["requested_scope"] == "systematic_full_path"
    assert payload["lesson_mode"] == "teach_then_quick_check"
    assert "immediately register one quick multiple-choice" in payload["must_ask"]
    assert "Do not ask whether the learner wants a quiz" in payload["must_ask"]
    assert [item["mode"] for item in payload["check_options"]] == [
        "multiple_choice",
        "true_false",
        "free_response",
    ]
    assert payload["required_check"]["mode"] == "quick_check"
    assert payload["required_check"]["allowed_modes"] == ["multiple_choice"]
    assert payload["required_check"]["default_mode"] == "multiple_choice"
    assert payload["free_response_policy"]["optional_now"] is True
    assert payload["free_response_policy"]["required_now"] is False
    assert any("Do not end the turn" in item for item in payload["interaction_policy"])


def test_lesson_contract_uses_quiz_flow_for_procedure_objective() -> None:
    seed = build_lesson_contract_seed(
        domain="leetcode",
        learner_goal="practice arrays",
        next_step=NextStep(
            action="practice",
            knowledge_point_id="sk-array",
            knowledge_point_name="Array Basics",
            knowledge_point_type="procedure",
            status="learning",
        ),
        map_summary={"counts": {"total": 1}, "modules": []},
    )

    payload = _payload(seed)

    assert payload["lesson_mode"] == "quiz_then_grade"
    assert "mastery_quiz" in payload["must_ask"]
    assert "quantitative gate" in payload["advance_rule"]


def test_lesson_contract_teaches_before_quizzing_beginner_probe() -> None:
    seed = build_lesson_contract_seed(
        domain="aws_certification",
        learner_goal="I am a complete beginner",
        next_step=NextStep(
            action="probe",
            knowledge_point_id="sk-aws-clf-c02",
            knowledge_point_name="Cloud Practitioner",
            knowledge_point_type="procedure",
            status="new",
        ),
        map_summary={"counts": {"total": 46}, "modules": []},
    )

    payload = _payload(seed)

    assert payload["lesson_mode"] == "teach_then_quick_check"
    assert "After the mini-lesson" in payload["must_ask"]
    assert "mastery_quiz(question_type='choice')" in payload["must_ask"]
    assert "Do not ask the learner to choose the quiz format" in payload["must_ask"]
    assert payload["check_options"][0]["mode"] == "multiple_choice"
    assert payload["required_check"]["mode"] == "quick_check"
    assert payload["free_response_policy"]["optional_now"] is True


def test_lesson_contract_masks_materialized_overview_name() -> None:
    seed = build_lesson_contract_seed(
        domain="aws_certification",
        learner_goal="complete beginner",
        next_step=NextStep(
            action="assess",
            knowledge_point_id="ov-overview",
            knowledge_point_name="Cognisphere бд aws_certification",
            knowledge_point_type="concept",
            status="learning",
        ),
        map_summary={"counts": {"total": 46}, "modules": []},
    )

    payload = _payload(seed)

    assert payload["current_objective"]["display_name"] == "the learning path overview"
    assert "the learning path overview" in payload["must_ask"]
    assert "immediately register one quick multiple-choice" in payload["must_ask"]


def test_lesson_contract_requires_free_response_after_foundation_ramp() -> None:
    seed = build_lesson_contract_seed(
        domain="aws_certification",
        learner_goal="continue",
        next_step=NextStep(
            action="assess",
            knowledge_point_id="obj-security",
            knowledge_point_name="Security and Identity",
            knowledge_point_type="concept",
            status="learning",
        ),
        map_summary={"counts": {"total": 20, "mastered": 4, "learning": 1, "new": 15}},
    )

    payload = _payload(seed)

    assert payload["required_check"]["mode"] == "free_response"
    assert payload["free_response_policy"]["required_now"] is True
    assert payload["free_response_policy"]["optional_now"] is False
