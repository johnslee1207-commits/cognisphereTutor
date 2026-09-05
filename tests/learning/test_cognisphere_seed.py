"""Tests for Cognisphere → Guided Learning seed + API binding."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from cognispheretutor.api.routers import cognisphere_learning
from cognispheretutor.learning.cognisphere_seed import (
    is_cognisphere_path_id,
    mastery_path_id_for_domain,
    modules_from_knowledge,
    seed_payload_from_import_receipt,
)
from cognispheretutor.learning.storage import LearningStore

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "cognisphere_learning_plugins"
)


def test_mastery_path_id_helpers() -> None:
    from cognispheretutor.learning.cognisphere_seed import domain_from_path_id

    assert mastery_path_id_for_domain("leetcode") == "csphere-leetcode"
    assert mastery_path_id_for_domain("ap_calculus") == "csphere-ap_calculus"
    assert mastery_path_id_for_domain("aws_certification") == "csphere-aws_certification"
    assert is_cognisphere_path_id("csphere-leetcode")
    assert not is_cognisphere_path_id("book-1")
    assert domain_from_path_id("csphere-leetcode") == "leetcode"
    assert domain_from_path_id("book-1") is None


def test_ability_radar_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(FIXTURE_ROOT))
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path / "imports"))

    store_root = tmp_path / "learning"
    monkeypatch.setattr(
        cognisphere_learning,
        "_service",
        lambda: __import__(
            "cognispheretutor.learning.service", fromlist=["LearningService"]
        ).LearningService(LearningStore(store_root)),
    )
    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix="/api/v1/learning/cognisphere")
    client = TestClient(app)

    empty = client.get("/api/v1/learning/cognisphere/ability-radar")
    assert empty.status_code == 200, empty.text
    assert empty.json()["domain_count"] == 0

    seeded = client.post(
        "/api/v1/learning/cognisphere/import-and-seed",
        json={"domain": "leetcode", "seed_mastery_path": True},
    )
    assert seeded.status_code == 200, seeded.text

    radar = client.get(
        "/api/v1/learning/cognisphere/ability-radar",
        params={"path_id": "csphere-leetcode", "include_skill_graph": False},
    )
    assert radar.status_code == 200, radar.text
    body = radar.json()
    assert body["ok"] is True
    assert body["domain_count"] >= 1
    assert any(d.get("path_id") == "csphere-leetcode" for d in body["domains"])
    selected = body["selected"]
    assert selected is not None
    assert selected["path_id"] == "csphere-leetcode"
    assert isinstance(selected["axes"], list)
    assert isinstance(selected["weak_areas"], list)
    assert selected["mastered_pct"] >= 0
    # Fresh seed → all objectives open → weak areas populated when KPs exist.
    assert selected["counts"]["total"] >= 1
    assert len(selected["weak_areas"]) >= 1


def test_ability_radar_path_detail_keeps_weak_domains_scoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path / "imports"))

    store_root = tmp_path / "learning"
    monkeypatch.setattr(
        cognisphere_learning,
        "_service",
        lambda: __import__(
            "cognispheretutor.learning.service", fromlist=["LearningService"]
        ).LearningService(LearningStore(store_root)),
    )
    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix="/api/v1/learning/cognisphere")
    client = TestClient(app)

    for domain in ("aws_certification", "california_electrical_career"):
        seeded = client.post(
            "/api/v1/learning/cognisphere/import-and-seed",
            json={"domain": domain, "seed_mastery_path": True},
        )
        assert seeded.status_code == 200, seeded.text

    radar = client.get(
        "/api/v1/learning/cognisphere/ability-radar",
        params={
            "path_id": "csphere-california_electrical_career",
            "include_skill_graph": False,
        },
    )
    assert radar.status_code == 200, radar.text
    body = radar.json()
    assert body["selected"]["path_id"] == "csphere-california_electrical_career"
    assert body["weak_domains"]
    assert {
        item["path_id"] for item in body["weak_domains"]
    } == {"csphere-california_electrical_career"}


def test_seed_payload_requires_domain() -> None:
    from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError

    with pytest.raises(CognisphereIntegrationError) as exc:
        seed_payload_from_import_receipt({"knowledge": {}})
    assert exc.value.code == "domain_required"
    payload = seed_payload_from_import_receipt(
        {"domain": "ap_calculus", "knowledge": {"concepts": [{"id": "c1"}]}}
    )
    assert payload["domain"] == "ap_calculus"


def test_modules_from_knowledge_groups() -> None:
    modules = modules_from_knowledge(
        {
            "patterns": [{"pattern_id": "two-pointers", "name": "Two Pointers"}],
            "skills": [{"skill_id": "hash-map", "name": "Hash Map"}],
            "problems": [{"slug": "two-sum", "title": "Two Sum"}],
        },
        domain="leetcode",
    )
    names = [m.name for m in modules]
    assert names[0].startswith("Cognisphere")
    assert "Patterns" in names
    assert "Skills" in names
    assert "Practice problems" in names
    assert sum(len(m.knowledge_points) for m in modules) >= 4


def test_modules_from_knowledge_uses_course_overview_as_first_module() -> None:
    modules = modules_from_knowledge(
        {
            "learning_surface": {
                "course_overview": {
                    "overview_id": "ai_infra.course_overview.v1",
                    "title": "AI Infrastructure Knowledge Platform and Digital Twin Course",
                    "teaching_purpose": "Explain why standard learning comes before Twin practice.",
                },
                "course_guide": {
                    "guide_id": "ai_infra.course_guide.v1",
                    "title": "How to Learn AI Infrastructure with Tutor and the Twin",
                    "learner_contract": "The learner advances in order.",
                }
            },
            "learning_loop": ["orient", "concept"],
        },
        domain="ai_infra",
    )

    assert modules[0].name == "AI Infrastructure Knowledge Platform and Digital Twin Course"
    assert modules[0].knowledge_points[0].id == "ov-ai_infra-course_overview-v1"
    assert modules[0].knowledge_points[0].name == (
        "AI Infrastructure Knowledge Platform and Digital Twin Course"
    )
    assert modules[1].name == "Course guide"
    assert modules[1].knowledge_points[0].id == "guide-ai_infra-course_guide-v1"
    assert modules[1].knowledge_points[0].name == (
        "How to Learn AI Infrastructure with Tutor and the Twin"
    )


def test_modules_from_knowledge_maps_assessments_and_references() -> None:
    modules = modules_from_knowledge(
        {
            "assessments": [
                {
                    "assessment_id": "apcalc.assess.related_rates",
                    "pattern_hint": "Related Rates FRQ",
                }
            ],
            "problem_patterns": [{"pattern_id": "optimization", "label": "Optimization"}],
            "theorems": [{"theorem_id": "ftc", "label": "Fundamental Theorem"}],
            "ontology_classes": [{"class_id": "concept", "purpose": "Concept taxonomy"}],
        },
        domain="ap_calculus",
    )

    by_name = {module.name: module for module in modules}
    assert by_name["Practice problems"].knowledge_points[0].id.endswith(
        "apcalc-assess-related_rates"
    )
    assert by_name["Practice problems"].knowledge_points[0].name == "Related Rates FRQ"
    assert by_name["Patterns"].knowledge_points[0].name == "Optimization"
    assert by_name["Reference rules"].knowledge_points[0].name == "Fundamental Theorem"
    assert by_name["Concepts"].knowledge_points[0].name == "Concept taxonomy"


def test_modules_from_knowledge_maps_lightweight_learning_loop() -> None:
    modules = modules_from_knowledge(
        {"learning_loop": ["plan", "teach", "assess", "memory"]},
        domain="aws_certification",
    )

    by_name = {module.name: module for module in modules}
    assert "Learning loop" in by_name
    assert [kp.name for kp in by_name["Learning loop"].knowledge_points] == [
        "plan",
        "teach",
        "assess",
        "memory",
    ]


def test_modules_from_knowledge_maps_thin_certification_surface() -> None:
    modules = modules_from_knowledge(
        {
            "certification_tracks": [
                {"track_id": "aws.clf-c02", "label": "Cloud Practitioner"}
            ],
            "topic_families": [
                {"topic_family_id": "security", "label": "Security and Identity"}
            ],
            "learning_fixture": {
                "excerpts": [
                    {
                        "excerpt_id": "rel.iam_roles_s3",
                        "title": "IAM roles instead of long-term credentials",
                    }
                ]
            },
            "original_knowledge": {
                "units": [
                    {
                        "unit_id": "aws.concept.certification-home",
                        "title": "AWS Certification Home",
                    }
                ]
            },
        },
        domain="aws_certification",
    )

    by_name = {module.name: module for module in modules}
    assert by_name["Skills"].knowledge_points[0].name == "Cloud Practitioner"
    assert by_name["Learning objectives"].knowledge_points[0].name == "Security and Identity"
    assert by_name["Concepts"].knowledge_points[0].name == (
        "IAM roles instead of long-term credentials"
    )
    assert by_name["Reference rules"].knowledge_points[0].name == "AWS Certification Home"


def test_modules_from_knowledge_orders_foundational_tracks_first() -> None:
    modules = modules_from_knowledge(
        {
            "certification_tracks": [
                {
                    "track_id": "aws.saa-c03",
                    "label": "Solutions Architect Associate",
                    "level": "associate",
                },
                {
                    "track_id": "aws.clf-c02",
                    "label": "Cloud Practitioner",
                    "level": "foundational",
                },
            ]
        },
        domain="aws_certification",
    )

    skills = next(module for module in modules if module.name == "Skills")
    assert [kp.name for kp in skills.knowledge_points[:2]] == [
        "Cloud Practitioner",
        "Solutions Architect Associate",
    ]


def test_modules_from_knowledge_prefers_tutor_ready_modules() -> None:
    modules = modules_from_knowledge(
        {
            "mastery_modules": [
                {
                    "id": "csphere-leetcode-runtime",
                    "name": "Plugin runtime plan",
                    "order": 0,
                    "pass_threshold": 0.7,
                    "knowledge_points": [
                        {
                            "id": "lc-p2",
                            "name": "Two pointers",
                            "type": "procedure",
                            "module_id": "csphere-leetcode-runtime",
                        }
                    ],
                }
            ],
            "skills": [{"skill_id": "ignored", "name": "Ignored"}],
        },
        domain="leetcode",
        path_id="csphere-custom",
    )

    assert len(modules) == 1
    assert modules[0].id == "csphere-custom-runtime"
    assert modules[0].knowledge_points[0].module_id == "csphere-custom-runtime"
    assert modules[0].knowledge_points[0].name == "Two pointers"


def test_import_and_seed_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(FIXTURE_ROOT))
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path / "imports"))

    store_root = tmp_path / "learning"
    monkeypatch.setattr(
        cognisphere_learning,
        "_service",
        lambda: __import__(
            "cognispheretutor.learning.service", fromlist=["LearningService"]
        ).LearningService(LearningStore(store_root)),
    )

    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix="/api/v1/learning/cognisphere")
    client = TestClient(app)

    status = client.get("/api/v1/learning/cognisphere/status")
    assert status.status_code == 200
    body = status.json()
    assert body["ok"] is True
    assert body["defaults"]["chat_capability"] == "mastery_path"
    assert "trusted_context" in body["gates"]
    assert body["gates"]["trusted_context"]["phase"] == "DT-P3"
    assert "aws_twin_mastery" in body["gates"]
    assert body["gates"]["aws_twin_mastery"]["path"] == "aws_digital_twin_mastery"
    assert body["tutor_pack"]["defaults"]["check_command"]
    domains = {p["domain"] for p in body["plugins"]}
    assert "leetcode" in domains
    leetcode = next(p for p in body["plugins"] if p["domain"] == "leetcode")
    assert leetcode.get("kind") == "learning"
    assert leetcode["distribution"]["package_name"] == "cognisphere-plugins-leetcode"
    assert leetcode["tutor_pack"]["check_command"]

    seeded = client.post(
        "/api/v1/learning/cognisphere/import-and-seed",
        json={"domain": "leetcode", "seed_mastery_path": True},
    )
    assert seeded.status_code == 200, seeded.text
    payload = seeded.json()
    assert payload["ok"] is True
    assert payload["mastery_path"]["path_id"] == "csphere-leetcode"
    assert payload["mastery_path"]["kp_count"] >= 1
    assert "capability=mastery_path" in (payload.get("continue_in_chat") or "")
    assert (store_root / "csphere-leetcode.json").exists()


def test_bundled_pack_status_and_import_without_external_plugins(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_root = tmp_path / "missing_plugins"
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(missing_root))
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path / "imports"))

    store_root = tmp_path / "learning"
    monkeypatch.setattr(
        cognisphere_learning,
        "_service",
        lambda: __import__(
            "cognispheretutor.learning.service", fromlist=["LearningService"]
        ).LearningService(LearningStore(store_root)),
    )

    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix="/api/v1/learning/cognisphere")
    client = TestClient(app)

    status = client.get("/api/v1/learning/cognisphere/status")
    assert status.status_code == 200, status.text
    status_body = status.json()
    assert status_body["ok"] is True
    assert status_body["bundled_distribution"]["available"] >= 4
    bundled = {p["domain"]: p for p in status_body["plugins"]}
    assert bundled["aws_certification"]["source"] == "bundled_pack"
    assert bundled["aws_certification"]["valid"] is True
    assert bundled["california_electrical_career"]["source"] == "bundled_pack"
    assert bundled["california_electrical_career"]["valid"] is True

    seeded = client.post(
        "/api/v1/learning/cognisphere/import-and-seed",
        json={"domain": "aws_certification", "seed_mastery_path": True},
    )
    assert seeded.status_code == 200, seeded.text
    payload = seeded.json()
    assert payload["import"]["distribution_source"] == "bundled_pack"
    assert payload["mastery_path"]["path_id"] == "csphere-aws_certification"
    assert payload["mastery_path"]["kp_count"] == 46
    assert (store_root / "csphere-aws_certification.json").exists()

    recommended = client.post(
        "/api/v1/learning/cognisphere/recommend-from-goal",
        json={
            "goal": "I want to learn AWS certification from scratch",
            "required_capabilities": ["deeptutor_export"],
            "compose_and_seed": False,
        },
    )
    assert recommended.status_code == 200, recommended.text
    assert "aws_certification" in recommended.json()["recommended_domains"]

    electrical = client.post(
        "/api/v1/learning/cognisphere/import-and-seed",
        json={"domain": "california_electrical_career", "seed_mastery_path": True},
    )
    assert electrical.status_code == 200, electrical.text
    electrical_payload = electrical.json()
    assert electrical_payload["import"]["distribution_source"] == "bundled_pack"
    assert electrical_payload["mastery_path"]["path_id"] == "csphere-california_electrical_career"
    assert electrical_payload["mastery_path"]["kp_count"] == 39
    assert (store_root / "csphere-california_electrical_career.json").exists()

    electrical_recommended = client.post(
        "/api/v1/learning/cognisphere/recommend-from-goal",
        json={
            "goal": "I want to become a California electrician and prepare for GE and C-10",
            "required_capabilities": ["deeptutor_export"],
            "compose_and_seed": False,
        },
    )
    assert electrical_recommended.status_code == 200, electrical_recommended.text
    assert (
        "california_electrical_career"
        in electrical_recommended.json()["recommended_domains"]
    )


def test_bundled_pack_status_reports_import_update_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_root = tmp_path / "missing_plugins"
    import_root = tmp_path / "imports"
    domain = "california_electrical_career"
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(missing_root))
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(import_root))

    from cognispheretutor.integrations.cognisphere.pack_distribution import (
        get_bundled_pack,
    )

    bundled = get_bundled_pack(domain)
    assert bundled is not None
    old_bundle = dict(bundled["bundle"])
    old_bundle["knowledge"] = {
        **old_bundle["knowledge"],
        "lesson_cards": [],
        "scenario_cards": [],
    }
    cache_dir = import_root / domain
    cache_dir.mkdir(parents=True)
    (cache_dir / "bundle.json").write_text(
        json.dumps(old_bundle, ensure_ascii=False),
        encoding="utf-8",
    )

    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix="/api/v1/learning/cognisphere")
    client = TestClient(app)

    status = client.get("/api/v1/learning/cognisphere/status")
    assert status.status_code == 200, status.text
    plugin = {
        item["domain"]: item for item in status.json()["plugins"]
    }["california_electrical_career"]
    import_status = plugin["distribution"]["import_status"]
    assert import_status["installed"] is True
    assert import_status["update_available"] is True
    assert "more_lesson_cards" in import_status["reasons"]
    assert import_status["bundled"]["counts"]["lesson_cards"] > 0
    assert import_status["imported"]["counts"]["lesson_cards"] == 0


def test_bundled_pack_radar_axes_are_domain_specific(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_root = tmp_path / "missing_plugins"
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(missing_root))
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path / "imports"))

    store_root = tmp_path / "learning"
    monkeypatch.setattr(
        cognisphere_learning,
        "_service",
        lambda: __import__(
            "cognispheretutor.learning.service", fromlist=["LearningService"]
        ).LearningService(LearningStore(store_root)),
    )

    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix="/api/v1/learning/cognisphere")
    client = TestClient(app)

    expected = {
        "aws_certification": {
            "path_id": "csphere-aws_certification",
            "kp_count": 46,
            "axis": "CLF-C02 Technology Services",
        },
        "ap_calculus": {
            "path_id": "csphere-ap_calculus",
            "kp_count": 22,
            "axis": "AP Calculus Derivatives",
        },
        "leetcode": {
            "path_id": "csphere-leetcode",
            "kp_count": 18,
            "axis": "Two Pointers and Sliding Window",
        },
        "california_electrical_career": {
            "path_id": "csphere-california_electrical_career",
            "kp_count": 39,
            "axis": "ETI / IBEW Local 11 Apprenticeship Entrance",
        },
    }

    for domain, meta in expected.items():
        seeded = client.post(
            "/api/v1/learning/cognisphere/import-and-seed",
            json={"domain": domain, "seed_mastery_path": True},
        )
        assert seeded.status_code == 200, seeded.text
        assert seeded.json()["mastery_path"]["kp_count"] == meta["kp_count"]

        radar = client.get(
            "/api/v1/learning/cognisphere/ability-radar",
            params={"path_id": meta["path_id"], "include_skill_graph": False},
        )
        assert radar.status_code == 200, radar.text
        body = radar.json()
        selected = body["selected"]
        labels = [axis["label"] for axis in selected["axes"]]
        assert selected["counts"]["total"] == meta["kp_count"]
        assert meta["axis"] in labels
        assert all(not label.startswith("Cognisphere ·") for label in labels)
        assert [d["path_id"] for d in body["weak_domains"]] == [meta["path_id"]]


def test_california_electrical_pack_metadata_counts_match_content() -> None:
    pack_path = (
        Path("cognispheretutor/integrations/cognisphere/bundled_packs")
        / "california_electrical_career_bundle.json"
    )
    knowledge = json.loads(pack_path.read_text(encoding="utf-8"))["knowledge"]
    metadata = knowledge["pack_metadata"]
    count_fields = {
        "lesson_card_count": "lesson_cards",
        "practice_blueprint_count": "practice_blueprints",
        "learning_activity_template_count": "learning_activity_templates",
        "study_sequence_count": "study_sequences",
        "scenario_card_count": "scenario_cards",
        "flashcard_deck_count": "flashcard_decks",
        "readiness_checkpoint_count": "readiness_checkpoints",
        "error_taxonomy_count": "error_taxonomy",
        "visual_prompt_count": "visual_prompts",
    }
    for metadata_key, content_key in count_fields.items():
        assert metadata[metadata_key] == len(knowledge[content_key])

    entrance_scenarios = [
        item
        for item in knowledge["scenario_cards"]
        if "entrance" in json.dumps(item).lower()
        or "apprentice" in json.dumps(item).lower()
    ]
    entrance_lessons = [
        item
        for item in knowledge["lesson_cards"]
        if "entrance" in json.dumps(item).lower()
        or "apprentice" in json.dumps(item).lower()
    ]

    assert metadata["scenario_card_count"] >= 123
    assert metadata["lesson_card_count"] >= 99
    assert metadata["visual_prompt_count"] == 10
    assert {item["visual_template"] for item in knowledge["visual_prompts"]} >= {
        "lever",
        "paper_one_fold_hole",
        "three_gears",
    }
    assert len(entrance_scenarios) >= 100
    assert len(entrance_lessons) >= 55


def test_runtime_plan_fallback_seeds_sparse_domain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import cognispheretutor.integrations.cognisphere as cognisphere_integration

    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(FIXTURE_ROOT))
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path / "imports"))

    store_root = tmp_path / "learning"
    monkeypatch.setattr(
        cognisphere_learning,
        "_service",
        lambda: __import__(
            "cognispheretutor.learning.service", fromlist=["LearningService"]
        ).LearningService(LearningStore(store_root)),
    )
    real_modules_from_knowledge = modules_from_knowledge
    monkeypatch.setattr(
        cognisphere_learning,
        "modules_from_knowledge",
        lambda _knowledge, *, domain, path_id=None: real_modules_from_knowledge(
            {},
            domain=domain,
            path_id=path_id,
        ),
    )

    def fake_plan_skill_path(*, domain: str, learner_id: str = "offline-learner"):
        return {
            "ok": True,
            "domain": domain,
            "plan": {
                "next_sequence": [
                    {"skill_id": "skill:a", "name": "Skill A"},
                    {"skill_id": "skill:b", "name": "Skill B"},
                ]
            },
        }

    monkeypatch.setattr(cognisphere_integration, "plan_skill_path", fake_plan_skill_path)

    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix="/api/v1/learning/cognisphere")
    client = TestClient(app)

    seeded = client.post(
        "/api/v1/learning/cognisphere/import-and-seed",
        json={"domain": "aws_certification", "seed_mastery_path": True},
    )
    assert seeded.status_code == 200, seeded.text
    path = seeded.json()["mastery_path"]
    assert path["runtime_plan_fallback"] is True
    assert any(module["name"] == "Plugin runtime plan" for module in path["modules"])


def test_cross_domain_and_compose_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(FIXTURE_ROOT))
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path / "imports"))

    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix="/api/v1/learning/cognisphere")
    client = TestClient(app)

    cross = client.post(
        "/api/v1/learning/cognisphere/cross-domain",
        json={"required_capabilities": ["socratic_tutor"], "goal": "practice algorithms"},
    )
    assert cross.status_code == 200, cross.text
    cross_body = cross.json()
    assert cross_body["match_count"] >= 1
    assert any(m.get("domain") == "leetcode" for m in cross_body.get("matches") or [])

    composed = client.post(
        "/api/v1/learning/cognisphere/compose",
        json={"domains": ["leetcode"], "required_capabilities": ["deeptutor_export"]},
    )
    assert composed.status_code == 200, composed.text
    compose_body = composed.json()
    assert compose_body.get("phase") == "DT-P6"
    assert any(
        (c.get("domain") == "leetcode") for c in (compose_body.get("contexts") or [])
    )


def test_recommend_from_goal_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(FIXTURE_ROOT))
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path / "imports"))

    store_root = tmp_path / "learning"
    monkeypatch.setattr(
        cognisphere_learning,
        "_service",
        lambda: __import__(
            "cognispheretutor.learning.service", fromlist=["LearningService"]
        ).LearningService(LearningStore(store_root)),
    )

    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix="/api/v1/learning/cognisphere")
    client = TestClient(app)

    preview = client.post(
        "/api/v1/learning/cognisphere/recommend-from-goal",
        json={
            "goal": "practice algorithms with coding interview packs",
            "required_capabilities": ["deeptutor_export"],
            "compose_and_seed": False,
        },
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["match_count"] >= 1
    assert "leetcode" in body["recommended_domains"]
    assert "aws_certification" not in body["recommended_domains"]

    seeded = client.post(
        "/api/v1/learning/cognisphere/recommend-from-goal",
        json={
            "goal": "practice algorithms with coding interview packs",
            "required_capabilities": ["deeptutor_export"],
            "compose_and_seed": True,
        },
    )
    assert seeded.status_code == 200, seeded.text
    seeded_body = seeded.json()
    assert seeded_body["compose_seed"] is not None
    assert seeded_body["compose_seed"]["seeded_count"] >= 1
    assert (store_root / "csphere-leetcode.json").exists()


def test_compose_and_seed_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNISPHERE_LEARNING_PLUGINS_ROOT", str(FIXTURE_ROOT))
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path / "imports"))

    store_root = tmp_path / "learning"
    monkeypatch.setattr(
        cognisphere_learning,
        "_service",
        lambda: __import__(
            "cognispheretutor.learning.service", fromlist=["LearningService"]
        ).LearningService(LearningStore(store_root)),
    )

    app = FastAPI()
    app.include_router(cognisphere_learning.router, prefix="/api/v1/learning/cognisphere")
    client = TestClient(app)

    result = client.post(
        "/api/v1/learning/cognisphere/compose-and-seed",
        json={"domains": ["leetcode"], "seed_mastery_path": True},
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["seeded_count"] >= 1
    assert any(s.get("domain") == "leetcode" and s.get("ok") for s in body["seeds"])
    assert (store_root / "csphere-leetcode.json").exists()
