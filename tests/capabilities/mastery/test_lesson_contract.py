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
    assert any("teach a substantive mini-lesson before" in item for item in payload["interaction_policy"])


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
    assert "lesson_first" in payload["post_grade_policy"]


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
    assert any("do not chain directly into another quiz" in item for item in payload["interaction_policy"])


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


def test_lesson_contract_teaches_course_overview_as_system_introduction() -> None:
    seed = build_lesson_contract_seed(
        domain="ai_infra",
        learner_goal="systematic beginner path",
        next_step=NextStep(
            action="assess",
            knowledge_point_id="ov-ai_infra-course_overview-v1",
            knowledge_point_name="AI Infrastructure Knowledge Platform and Digital Twin Course",
            knowledge_point_type="concept",
            status="learning",
        ),
        map_summary={"counts": {"total": 76}, "modules": []},
    )

    payload = _payload(seed)

    assert payload["current_objective"]["display_name"] == (
        "AI Infrastructure Knowledge Platform and Digital Twin Course"
    )
    assert any("course purpose" in item for item in payload["must_teach"])
    assert any("standard-learning-before-Twin" in item for item in payload["must_teach"])
    assert any("source boundary" in item for item in payload["must_teach"])


def test_lesson_contract_teaches_course_guide_as_learning_method() -> None:
    seed = build_lesson_contract_seed(
        domain="ai_infra",
        learner_goal="systematic beginner path",
        next_step=NextStep(
            action="assess",
            knowledge_point_id="guide-ai_infra-course_guide-v1",
            knowledge_point_name="How to Learn AI Infrastructure with Tutor and the Twin",
            knowledge_point_type="concept",
            status="learning",
        ),
        map_summary={"counts": {"total": 77}, "modules": []},
    )

    payload = _payload(seed)

    assert payload["current_objective"]["display_name"] == (
        "How to Learn AI Infrastructure with Tutor and the Twin"
    )
    guide_items = [item for item in payload["must_teach"] if "course guide" in item]
    assert guide_items
    assert "advances in order" in guide_items[0]
    assert "Continue" in guide_items[0]
    assert "when chat is appropriate" in guide_items[0]
    assert "when Twin labs open" in guide_items[0]
    assert "lab-backed evidence" in guide_items[0]


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


def test_lesson_contract_requires_visual_aid_for_mechanical_spatial_objective() -> None:
    seed = build_lesson_contract_seed(
        domain="california_electrical_career",
        learner_goal="entrance exam mechanical reasoning",
        next_step=NextStep(
            action="probe",
            knowledge_point_id="cec-apprentice-mechanical",
            knowledge_point_name=(
                "Mechanical reasoning: force, levers, pulleys, gears, and motion"
            ),
            knowledge_point_type="concept",
            status="new",
            module_id="csphere-california_electrical_career-apprenticeship",
            module_name="ETI / IBEW Local 11 Apprenticeship Entrance",
        ),
        map_summary={"counts": {"total": 39}, "modules": []},
    )

    payload = _payload(seed)

    assert payload["visual_aid"]["required"] is True
    assert payload["visual_aid"]["tool"] == "mastery_visual"
    assert payload["visual_aid"]["knowledge_point_id"] == "cec-apprentice-mechanical"
    assert any("mastery_visual" in item for item in payload["must_teach"])
