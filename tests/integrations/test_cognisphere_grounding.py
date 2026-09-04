from __future__ import annotations

import json
from pathlib import Path


def test_build_plugin_grounding_seed_reads_local_package_knowledge(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from cognispheretutor.integrations.cognisphere import grounding

    plugin_path = tmp_path / "plugins" / "demo_domain"
    package_dir = plugin_path / "manifests" / "packages" / "demo_pack"
    knowledge_dir = package_dir / "knowledge"
    knowledge_dir.mkdir(parents=True)
    (package_dir / "package_manifest.json").write_text(
        json.dumps(
            {
                "package_id": "demo_pack",
                "original_knowledge_relpath": "knowledge/original.json",
            }
        ),
        encoding="utf-8",
    )
    (knowledge_dir / "original.json").write_text(
        json.dumps(
            {
                "units": [
                    {
                        "unit_id": "demo.iam.roles",
                        "title": "IAM roles for compute access",
                        "body": "Use temporary role credentials instead of long-term keys.",
                        "teaching_points": ["Prefer roles over embedded keys."],
                    },
                    {
                        "unit_id": "demo.networking",
                        "title": "VPC basics",
                        "body": "Networking material.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    class FakeRegistry:
        def get_plugin(self, domain: str):
            assert domain == "demo_domain"
            return {"plugin": {"path": str(plugin_path)}}

    monkeypatch.setattr(grounding, "PluginRegistryClient", FakeRegistry)
    monkeypatch.setattr(
        grounding,
        "resolve_import_cache_dir",
        lambda domain: tmp_path / "missing_import_cache" / domain,
    )

    seed = grounding.build_plugin_grounding_seed(
        domain="demo_domain",
        objective={
            "knowledge_point_id": "iam",
            "knowledge_point_name": "IAM roles",
            "module_name": "Security",
        },
    )

    assert "Cognisphere Plugin Graph Grounding" in seed
    assert "IAM roles for compute access" in seed
    assert "Prefer roles over embedded keys." in seed


def test_build_plugin_grounding_seed_uses_learner_goal_for_ranking(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from cognispheretutor.integrations.cognisphere import grounding

    plugin_path = tmp_path / "plugins" / "demo_domain"
    package_dir = plugin_path / "manifests" / "packages" / "demo_pack"
    knowledge_dir = package_dir / "knowledge"
    knowledge_dir.mkdir(parents=True)
    (package_dir / "package_manifest.json").write_text(
        json.dumps({"package_id": "demo_pack"}),
        encoding="utf-8",
    )
    (knowledge_dir / "items.json").write_text(
        json.dumps(
            {
                "units": [
                    {
                        "unit_id": "demo.cert.clf",
                        "title": "Cloud Practitioner CLF-C02 exam guide",
                        "body": "Foundational certificate overview.",
                    },
                    {
                        "unit_id": "demo.rds",
                        "title": "Multi-AZ RDS",
                        "body": "Reliability topic.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    class FakeRegistry:
        def get_plugin(self, _domain: str):
            return {"plugin": {"path": str(plugin_path)}}

    monkeypatch.setattr(grounding, "PluginRegistryClient", FakeRegistry)
    monkeypatch.setattr(grounding, "resolve_import_cache_dir", lambda domain: tmp_path / domain)

    seed = grounding.build_plugin_grounding_seed(
        domain="demo_domain",
        objective={"knowledge_point_name": "Cognisphere demo_domain"},
        learner_goal="I want the first certificate cloud practitioner clf c02",
    )

    assert "Cloud Practitioner CLF-C02 exam guide" in seed
    assert seed.index("Cloud Practitioner CLF-C02 exam guide") < seed.index("Multi-AZ RDS")


def test_build_plugin_grounding_seed_includes_course_overview_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from cognispheretutor.integrations.cognisphere import grounding

    plugin_path = tmp_path / "plugins" / "ai_infra"
    domain_dir = plugin_path / "manifests" / "domain"
    domain_dir.mkdir(parents=True)
    (domain_dir / "learning_surface.json").write_text(
        json.dumps(
            {
                "course_overview": {
                    "overview_id": "ai_infra.course_overview.v1",
                    "title": "AI Infrastructure Knowledge Platform and Digital Twin Course",
                    "teaching_purpose": (
                        "This course trains learners to operate AI infrastructure "
                        "with evidence-backed judgment."
                    ),
                    "learning_outcomes": [
                        "Connect operational claims to sources and lab evidence."
                    ],
                    "content_design_rationale": [
                        "Standard learning comes before Twin practice."
                    ],
                    "source_policy": "Course structure comes from the materialized plugin pack.",
                    "review_status": "source_backed_draft_review_required",
                },
                "course_guide": {
                    "guide_id": "ai_infra.course_guide.v1",
                    "title": "How to Learn AI Infrastructure with Tutor and the Twin",
                    "learner_contract": (
                        "The learner advances in order through mastery-gated objectives."
                    ),
                    "interface_principles": [
                        "Use Tutor's native chat and mastery path as the primary learning surface."
                    ],
                    "mastery_milestones": [
                        {
                            "milestone_id": "m0.orientation",
                            "label": "Orientation complete",
                            "learner_can": ["Use Continue as the default path action."],
                        }
                    ],
                    "claim_boundary_rules": [
                        "A benchmark claim requires workload shape, environment profile, run metadata, and evidence bundle."
                    ],
                    "leading_method_alignment": [
                        {
                            "method_id": "method.mastery-learning",
                            "method": "Mastery learning",
                            "implemented_as": [
                                "Tutor mastery gates block progression until evidence clears the current objective."
                            ],
                            "remaining_gap": "Add reviewer dashboard.",
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    class FakeRegistry:
        def get_plugin(self, domain: str):
            assert domain == "ai_infra"
            return {"plugin": {"path": str(plugin_path)}}

    monkeypatch.setattr(grounding, "PluginRegistryClient", FakeRegistry)
    monkeypatch.setattr(grounding, "resolve_import_cache_dir", lambda domain: tmp_path / domain)

    seed = grounding.build_plugin_grounding_seed(
        domain="ai_infra",
        objective={
            "knowledge_point_id": "ov-ai_infra-course_overview-v1",
            "knowledge_point_name": "AI Infrastructure Knowledge Platform and Digital Twin Course",
        },
    )

    assert "AI Infrastructure Knowledge Platform and Digital Twin Course" in seed
    assert "evidence-backed judgment" in seed
    assert "Standard learning comes before Twin practice" in seed
    assert "The learner advances in order through mastery-gated objectives" in seed
    assert "Tutor's native chat and mastery path" in seed
    assert "Orientation complete" in seed
    assert "benchmark claim requires workload shape" in seed
    assert "Mastery learning" in seed
    assert "Tutor mastery gates block progression" in seed
    assert "source_backed_draft_review_required" in seed


def test_build_plugin_grounding_seed_includes_materialized_lesson_cards(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from cognispheretutor.integrations.cognisphere import grounding

    cache_dir = tmp_path / "imports" / "california_electrical_career"
    cache_dir.mkdir(parents=True)
    (cache_dir / "bundle.json").write_text(
        json.dumps(
            {
                "domain": "california_electrical_career",
                "knowledge": {
                    "lesson_cards": [
                        {
                            "id": "cec-lesson-nec-navigation",
                            "title": "NEC navigation as a separate skill",
                            "body": (
                                "Open-book GE preparation requires classification, "
                                "article lookup, exception handling, calculation, "
                                "and answer verification."
                            ),
                            "teaching_points": [
                                "Open-book does not mean slow-book.",
                            ],
                            "quick_check_prompts": [
                                "What should happen before calculation?"
                            ],
                            "source_ref_ids": [
                                "ca_dir.electrician_certification_faq.2026-09-03"
                            ],
                        }
                    ],
                    "cognisphere_provenance_refs": [
                        {
                            "source_id": "ca_dir.electrician_certification_faq.2026-09-03",
                            "claim_summaries": [
                                "California electrician certification exams are open-book."
                            ],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    class FakeRegistry:
        def get_plugin(self, _domain: str):
            return {"plugin": {"path": str(tmp_path / "missing_plugin")}}

    monkeypatch.setattr(grounding, "PluginRegistryClient", FakeRegistry)
    monkeypatch.setattr(grounding, "resolve_import_cache_dir", lambda domain: cache_dir)

    seed = grounding.build_plugin_grounding_seed(
        domain="california_electrical_career",
        objective={
            "knowledge_point_name": "Open-book NEC navigation",
            "module_name": "California General Electrician",
        },
    )

    assert "NEC navigation as a separate skill" in seed
    assert "Open-book does not mean slow-book." in seed
    assert "What should happen before calculation?" in seed
    assert "ca_dir.electrician_certification_faq.2026-09-03" in seed


def test_build_plugin_grounding_seed_includes_learning_activity_templates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from cognispheretutor.integrations.cognisphere import grounding

    cache_dir = tmp_path / "imports" / "california_electrical_career"
    cache_dir.mkdir(parents=True)
    (cache_dir / "bundle.json").write_text(
        json.dumps(
            {
                "domain": "california_electrical_career",
                "knowledge": {
                    "learning_activity_templates": [
                        {
                            "id": "cec-activity-open-book-navigation-rehearsal",
                            "title": "Open-book NEC navigation rehearsal",
                            "summary": (
                                "Use for GE objectives where the learner must "
                                "look up code efficiently rather than rely only on memory."
                            ),
                            "activity_modes": [
                                "topic classification",
                                "article/table route planning",
                                "exception check",
                            ],
                            "steps": [
                                "Present an original code-style scenario without copyrighted code text.",
                                "Ask the learner to classify the topic.",
                            ],
                            "feedback_rule": [
                                "Track concept accuracy and lookup strategy separately."
                            ],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    class FakeRegistry:
        def get_plugin(self, _domain: str):
            return {"plugin": {"path": str(tmp_path / "missing_plugin")}}

    monkeypatch.setattr(grounding, "PluginRegistryClient", FakeRegistry)
    monkeypatch.setattr(grounding, "resolve_import_cache_dir", lambda domain: cache_dir)

    seed = grounding.build_plugin_grounding_seed(
        domain="california_electrical_career",
        objective={
            "knowledge_point_name": "GE NEC navigation",
            "module_name": "California General Electrician",
        },
    )

    assert "Open-book NEC navigation rehearsal" in seed
    assert "topic classification" in seed
    assert "without copyrighted code text" in seed
    assert "lookup strategy separately" in seed


def test_build_plugin_grounding_seed_includes_visual_prompts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from cognispheretutor.integrations.cognisphere import grounding

    cache_dir = tmp_path / "imports" / "california_electrical_career"
    cache_dir.mkdir(parents=True)
    (cache_dir / "bundle.json").write_text(
        json.dumps(
            {
                "domain": "california_electrical_career",
                "knowledge": {
                    "visual_prompts": [
                        {
                            "id": "cec-visual-entrance-one-fold-hole",
                            "title": "One-fold hole punch mirror",
                            "applies_to_objective_ids": [
                                "cec-apprentice-spatial"
                            ],
                            "visual_template": "paper_one_fold_hole",
                            "visual_mode": "mermaid_storyboard",
                            "prompt": (
                                "Show the folded state, punched mark, and backward "
                                "unfolding mirror result."
                            ),
                            "animation_steps": [
                                "Fold left over right.",
                                "Punch one mark near the folded edge.",
                                "Unfold backward and mirror the mark.",
                            ],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    class FakeRegistry:
        def get_plugin(self, _domain: str):
            return {"plugin": {"path": str(tmp_path / "missing_plugin")}}

    monkeypatch.setattr(grounding, "PluginRegistryClient", FakeRegistry)
    monkeypatch.setattr(grounding, "resolve_import_cache_dir", lambda domain: cache_dir)

    seed = grounding.build_plugin_grounding_seed(
        domain="california_electrical_career",
        objective={
            "knowledge_point_id": "cec-apprentice-spatial",
            "knowledge_point_name": "Spatial reasoning and paper folding",
            "module_name": "ETI / IBEW Local 11 Apprenticeship Entrance",
        },
        learner_goal="entrance exam spatial paper folding",
    )

    assert "One-fold hole punch mirror" in seed
    assert "paper_one_fold_hole" in seed
    assert "Fold left over right." in seed
    assert "Unfold backward and mirror the mark." in seed


def test_build_plugin_grounding_seed_includes_sequences_and_scenario_cards(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from cognispheretutor.integrations.cognisphere import grounding

    cache_dir = tmp_path / "imports" / "california_electrical_career"
    cache_dir.mkdir(parents=True)
    (cache_dir / "bundle.json").write_text(
        json.dumps(
            {
                "domain": "california_electrical_career",
                "knowledge": {
                    "study_sequences": [
                        {
                            "id": "cec-sequence-law-business",
                            "title": "Contractor Law and Business scenario path",
                            "summary": "A scenario-first route for Law and Business sections.",
                            "checkpoint_prompts": [
                                "Can the learner spot a public works clue?"
                            ],
                            "mastery_evidence": [
                                "public works recognition scenario"
                            ],
                        }
                    ],
                    "scenario_cards": [
                        {
                            "id": "cec-scenario-public-works-payroll",
                            "title": "Public works: certified payroll clue",
                            "scenario": [
                                "A contractor is working on a public project and the prompt mentions worker classifications, hours, and wage reporting."
                            ],
                            "choices": [
                                "A) Certified payroll / prevailing wage compliance"
                            ],
                            "correct_rationale": [
                                "Public project context plus worker classifications points to public works payroll."
                            ],
                        }
                    ],
                    "flashcard_decks": [
                        {
                            "id": "cec-flashcards-law-business",
                            "title": "Law and Business scenario cues",
                            "cards": [
                                "Certified payroll: public works record/reporting concept."
                            ],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    class FakeRegistry:
        def get_plugin(self, _domain: str):
            return {"plugin": {"path": str(tmp_path / "missing_plugin")}}

    monkeypatch.setattr(grounding, "PluginRegistryClient", FakeRegistry)
    monkeypatch.setattr(grounding, "resolve_import_cache_dir", lambda domain: cache_dir)

    seed = grounding.build_plugin_grounding_seed(
        domain="california_electrical_career",
        objective={
            "knowledge_point_name": "public works certified payroll",
            "module_name": "California Contractor Law and Business",
        },
    )

    assert "Contractor Law and Business scenario path" in seed
    assert "Public works: certified payroll clue" in seed
    assert "Law and Business scenario cues" in seed
    assert "public works record/reporting concept" in seed


def test_build_plugin_grounding_seed_reports_sparse_grounding(monkeypatch, tmp_path: Path) -> None:
    from cognispheretutor.integrations.cognisphere import grounding

    class FakeRegistry:
        def get_plugin(self, _domain: str):
            return {"plugin": {"path": str(tmp_path / "empty_plugin")}}

    monkeypatch.setattr(grounding, "PluginRegistryClient", FakeRegistry)
    monkeypatch.setattr(grounding, "resolve_import_cache_dir", lambda domain: tmp_path / domain)

    seed = grounding.build_plugin_grounding_seed(
        domain="demo_domain",
        objective={"knowledge_point_name": "missing topic"},
    )

    assert '"status": "missing"' in seed
    assert "local graph/pack grounding is sparse" in seed
