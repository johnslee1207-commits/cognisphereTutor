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
    assert "source_backed_draft_review_required" in seed


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
