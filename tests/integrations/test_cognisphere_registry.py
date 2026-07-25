"""Cognisphere Learning Plugins integration tests (DT-P1…P6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cognispheretutor.integrations.cognisphere.capability_negotiator import (
    compose_contexts,
    import_benchmark_case,
    negotiate,
    query_cross_domain,
)
from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError
from cognispheretutor.integrations.cognisphere.plugin_importer import (
    export_and_import,
    import_bundle_json,
    map_learning_loop,
    validate_bundle_safety,
)
from cognispheretutor.integrations.cognisphere.registry_client import PluginRegistryClient
from cognispheretutor.integrations.cognisphere.runtime_callbacks import (
    apply_mastery_update,
    ingest_sandbox_result,
    on_tutor_session_event,
    sync_mistake_memory,
)
from cognispheretutor.integrations.cognisphere.security_gates import is_sandbox_authorized
from cognispheretutor.integrations.cognisphere.trusted_context_client import (
    fetch_trusted_context_package,
    import_trusted_context_into_workspace,
    validate_trusted_context_package,
)

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "cognisphere_learning_plugins"
)


@pytest.fixture
def client() -> PluginRegistryClient:
    return PluginRegistryClient(FIXTURE_ROOT)


def test_list_plugins_discovers_three_domains(client: PluginRegistryClient) -> None:
    result = client.list_plugins()
    domains = {item["domain"] for item in result["plugins"]}
    assert domains == {"leetcode", "ap_calculus", "aws_certification"}
    assert result["plugin_count"] == 3
    assert result["plugins_root"] == str(FIXTURE_ROOT.resolve())
    assert not any(i.startswith("missing_plugin_manifest") for i in result["issues"])


def test_negotiate_leetcode_deeptutor_export_matched(client: PluginRegistryClient) -> None:
    result = negotiate(
        "leetcode",
        {"required_capabilities": ["deeptutor_export"], "goal": "algorithm_mentor_loop"},
        client=client,
    )
    assert result["matched"] is True
    assert result["missing"] == []
    assert "deeptutor_export" in result["available"]
    assert result["domain"] == "leetcode"


def test_negotiate_missing_capability(client: PluginRegistryClient) -> None:
    result = negotiate(
        "ap_calculus",
        {"required_capabilities": ["socratic_tutor"]},
        client=client,
    )
    assert result["matched"] is False
    assert "socratic_tutor" in result["missing"]


def test_validate_adapter_structured_issues(client: PluginRegistryClient) -> None:
    result = client.validate_adapter("leetcode")
    assert result["ok"] is True
    assert isinstance(result["issues"], list)
    assert result["handoff_contract"]["ok"] is True
    assert result["production_ready"] is True


def test_validate_adapter_unknown_domain(client: PluginRegistryClient) -> None:
    result = client.validate_adapter("not_a_domain")
    assert result["ok"] is False
    assert "domain_not_found" in result["issues"]


def test_query_cross_domain_filters(client: PluginRegistryClient) -> None:
    result = query_cross_domain(
        {"required_capabilities": ["socratic_tutor"]},
        client=client,
    )
    assert result["match_count"] == 1
    assert result["matches"][0]["domain"] == "leetcode"


def test_import_rejects_verified_solutions() -> None:
    bad = {
        "bundle_id": "x",
        "domain": "leetcode",
        "plugin_id": "p",
        "exported_at": "2026-07-24T00:00:00+00:00",
        "knowledge": {},
        "safety": {
            "no_answer_keys": True,
            "no_full_solution_dump": True,
            "source_of_truth": "cognisphere_plugin_pack",
            "verified_code_solutions_included": True,
        },
    }
    report = validate_bundle_safety(bad)
    assert report["ok"] is False
    assert "forbidden_verified_code_solutions_included" in report["issues"]
    with pytest.raises(CognisphereIntegrationError) as exc:
        import_bundle_json(bad, persist=False)
    assert exc.value.code == "forbidden_verified_code_solutions_included"


def test_import_accepts_compliant_bundle(tmp_path: Path) -> None:
    good = {
        "bundle_id": "leetcode.deeptutor_handoff",
        "domain": "leetcode",
        "plugin_id": "cognisphere.domain.leetcode.plugin.v1",
        "exported_at": "2026-07-24T00:00:00+00:00",
        "learning_loop": [
            "Assessment",
            "Knowledge Gap",
            "Learning Plan",
            "Practice",
            "Mistake Memory",
            "Mastery Update",
        ],
        "knowledge": {
            "problems": [{"slug": "two-sum"}],
            "patterns": [{"pattern_id": "p1"}],
            "skills": [{"skill_id": "s1"}],
        },
        "safety": {
            "no_answer_keys": True,
            "no_full_solution_dump": True,
            "source_of_truth": "cognisphere_plugin_pack",
        },
    }
    receipt = import_bundle_json(good, persist=True, cache_dir=tmp_path)
    assert receipt["ok"] is True
    assert receipt["status"] == "imported"
    assert receipt["receipt"]["bundle_id"] == "leetcode.deeptutor_handoff"
    assert receipt["surfaces"]["assessment"]["pipeline_ids"]
    assert receipt["surfaces"]["plan"]["pipeline_ids"]
    assert receipt["surfaces"]["mastery"]["pipeline_ids"]
    assert (tmp_path / "leetcode" / "bundle.json").exists()
    assert (tmp_path / "leetcode" / "import_receipt.json").exists()


def test_map_learning_loop_aliases() -> None:
    mapped = map_learning_loop(["plan", "teach", "assess", "memory"])
    assert mapped["ok"] is True
    ids = [s["pipeline_id"] for s in mapped["stages"]]
    assert "learning_plan" in ids
    assert "practice" in ids
    assert "assessment" in ids
    assert "mistake_memory" in ids


def test_export_and_import_leetcode_fixture(client: PluginRegistryClient, tmp_path: Path) -> None:
    receipt = export_and_import(
        "leetcode",
        {"persist": True, "cache_dir": tmp_path},
        client=client,
    )
    assert receipt["ok"] is True
    assert receipt["phase"] == "DT-P2"
    summary = receipt["knowledge_summary"]
    assert summary["counts"]["problems"] >= 1
    assert summary["counts"]["patterns"] >= 1
    assert summary["counts"]["skills"] >= 1
    assert receipt["receipt"]["assessment"]
    assert receipt["receipt"]["plan"]
    assert receipt["receipt"]["mastery"]


def test_export_and_import_ap_calculus_fixture(client: PluginRegistryClient, tmp_path: Path) -> None:
    receipt = export_and_import(
        "ap_calculus",
        {"persist": True, "cache_dir": tmp_path},
        client=client,
    )
    assert receipt["ok"] is True
    knowledge = receipt["knowledge_summary"]["counts"]
    assert knowledge.get("concepts", 0) >= 1 or knowledge.get("catalog", 0) >= 1


def test_sandbox_gate_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("COGNISPHERE_SANDBOX_AUTHORIZED", raising=False)
    monkeypatch.delenv("COGNISPHERE_LEETCODE_SANDBOX_AUTHORIZED", raising=False)
    assert is_sandbox_authorized() is False
    with pytest.raises(CognisphereIntegrationError) as exc:
        ingest_sandbox_result({"passed": False})
    assert exc.value.code == "sandbox_unauthorized"

    ok = ingest_sandbox_result(
        {"passed": False, "offline_simulated": True, "session_id": "t1", "slug": "two-sum"}
    )
    assert ok["mode"] == "offline_simulated"
    assert ok["mistake_memory"]["ok"] is True

    # Primary generic env
    monkeypatch.setenv("COGNISPHERE_SANDBOX_AUTHORIZED", "1")
    live = ingest_sandbox_result({"passed": True, "session_id": "t2"})
    assert live["mode"] == "authorized_live"

    # One-release legacy alias still accepted
    monkeypatch.delenv("COGNISPHERE_SANDBOX_AUTHORIZED", raising=False)
    monkeypatch.setenv("COGNISPHERE_LEETCODE_SANDBOX_AUTHORIZED", "1")
    assert is_sandbox_authorized() is True


def test_tutor_session_and_mastery_callbacks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path))
    event = on_tutor_session_event(
        "sess-1",
        {"type": "hint", "hint_level": 2, "stage_id": "understand"},
    )
    assert event["ok"] is True
    assert event["hint_level"] == 2

    with pytest.raises(CognisphereIntegrationError):
        on_tutor_session_event("sess-1", {"type": "spoil", "full_solution_included": True})

    mem = sync_mistake_memory({"slug": "two-sum", "error": "TLE"})
    assert mem["ok"] is True
    assert "two-sum" in mem["suggest_tutor_focus"]
    assert mem["learning_store"]["status"] == "skipped_no_path"

    mastery = apply_mastery_update({"skill_ids": ["skill:array"], "passed": True, "path_id": "p1"})
    assert mastery["ok"] is True
    assert mastery["learning_store"]["mastery_path_id"] == "p1"
    assert mastery["learning_store"]["status"] == "path_not_found"


def test_runtime_feedback_updates_learning_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sandbox fail with domain+slug lowers mastery on a seeded Cognisphere path."""
    from cognispheretutor.integrations.cognisphere.runtime_callbacks import (
        bind_runtime_feedback_to_learning,
    )
    from cognispheretutor.learning.cognisphere_seed import (
        mastery_path_id_for_domain,
        modules_from_knowledge,
    )
    from cognispheretutor.learning.service import LearningService
    from cognispheretutor.learning.storage import LearningStore

    store_root = tmp_path / "learning"
    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path / "imports"))
    monkeypatch.setattr(
        "cognispheretutor.learning.service.LearningService",
        lambda store=None: LearningService(LearningStore(store_root)),
    )

    path_id = mastery_path_id_for_domain("fixture_domain")
    service = LearningService(LearningStore(store_root))
    modules = modules_from_knowledge(
        {
            "problems": [{"slug": "two-sum", "title": "Two Sum"}],
            "skills": [{"skill_id": "array", "name": "Array"}],
        },
        domain="fixture_domain",
        path_id=path_id,
    )
    progress = service.get_or_create(path_id)
    service.init_modules(progress, modules)
    for module in modules:
        for kp in module.knowledge_points:
            progress.mastery_levels[kp.id] = 0.8
    service.save(progress)

    fail = ingest_sandbox_result(
        {
            "passed": False,
            "offline_simulated": True,
            "session_id": "fb1",
            "slug": "two-sum",
            "domain": "fixture_domain",
            "error": "WA",
        }
    )
    assert fail["mistake_memory"]["ok"] is True
    bind = fail["learning_store"]
    assert bind["status"] == "applied"
    assert any("two-sum" in kid for kid in bind["updated_kp_ids"])

    reloaded = LearningService(LearningStore(store_root))._store.load(path_id)
    assert reloaded is not None
    updated_levels = [
        reloaded.mastery_levels[kid]
        for kid in bind["updated_kp_ids"]
        if kid in reloaded.mastery_levels
    ]
    assert updated_levels
    assert all(level <= 0.35 for level in updated_levels)

    pass_bind = bind_runtime_feedback_to_learning(
        {"domain": "fixture_domain", "slug": "two-sum", "passed": True},
        passed=True,
        source="test_pass",
    )
    assert pass_bind["status"] == "applied"
    reloaded2 = LearningService(LearningStore(store_root))._store.load(path_id)
    assert reloaded2 is not None
    assert any(
        reloaded2.mastery_levels.get(kid, 0) >= 1.0 for kid in pass_bind["updated_kp_ids"]
    )


def test_trusted_context_offline_import(tmp_path: Path) -> None:
    package = {
        "project_id": "demo-project",
        "payload_kind": "knowledge_pack",
        "exported_at": "2026-07-24T00:00:00+00:00",
        "knowledge": {"nodes": [{"id": "n1"}]},
        "safety": {
            "source_of_truth": "cognisphere_trusted_context",
            "no_answer_keys": True,
        },
    }
    report = validate_trusted_context_package(package)
    assert report["ok"] is True
    receipt = import_trusted_context_into_workspace(package, cache_dir=tmp_path)
    assert receipt["ok"] is True
    assert receipt["phase"] == "DT-P3"
    assert (tmp_path / "demo-project" / "package.json").exists()


def test_trusted_context_status_and_live_fetch_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cognispheretutor.integrations.cognisphere.trusted_context_client import (
        trusted_context_status,
    )

    monkeypatch.delenv("COGNISPHERE_TRUSTED_CONTEXT_BASE_URL", raising=False)
    status = trusted_context_status()
    assert status["phase"] == "DT-P3"
    assert status["kit_configured"] is False
    assert status["mode"] == "offline_only"
    assert status["blocker"]["code"] == "trusted_context_kit_unavailable"

    with pytest.raises(CognisphereIntegrationError) as exc:
        fetch_trusted_context_package("proj", "knowledge_pack")
    assert exc.value.code == "trusted_context_kit_unavailable"


def test_compose_contexts_local(client: PluginRegistryClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Prefer the local compose path so developer machines with the real SDK
    # installed do not divert into live plugin packing (fixture ap_calculus
    # cannot load under the SDK).
    import sys
    import types

    import cognispheretutor.integrations.cognisphere.capability_negotiator as negotiator

    monkeypatch.setattr(
        negotiator.PluginRegistryClient,
        "ensure_import_paths",
        lambda self, *args, **kwargs: None,
    )
    blocked = types.ModuleType("cognisphere_plugin_sdk.entrypoint_surface")

    def _blocked(*_a, **_k):
        raise ImportError("force local compose")

    blocked.compose_plugin_contexts = _blocked  # type: ignore[attr-defined]
    blocked.query_cross_domain_capabilities = _blocked  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cognisphere_plugin_sdk.entrypoint_surface", blocked)

    result = compose_contexts(
        ["leetcode", "ap_calculus"],
        required_capabilities=["deeptutor_export"],
        client=client,
    )
    assert result["phase"] == "DT-P6"
    assert result.get("source") == "local_compose"
    assert result["ok"] is True
    assert len(result["contexts"]) == 2


def test_benchmark_unavailable_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing interview runtime must raise — never a silent stubbed envelope."""
    from cognispheretutor.integrations.cognisphere import runtime_bridge as bridge

    def _missing(*_a, **_k):
        raise CognisphereIntegrationError(
            "benchmark_unavailable",
            message="forced missing runtime",
        )

    monkeypatch.setattr(bridge, "load_runtime_module", _missing)
    with pytest.raises(CognisphereIntegrationError) as exc:
        import_benchmark_case("leetcode", {"case_id": "case-x"})
    assert exc.value.code == "benchmark_unavailable"

def test_runtime_adapters_manifest_loaded() -> None:
    from cognispheretutor.integrations.cognisphere._contract import load_runtime_adapters

    adapters = load_runtime_adapters()
    assert adapters["contract_id"].endswith("runtime_adapters.v1")
    assert "default_domain" not in adapters
    assert "{domain}" in str(adapters.get("module_template") or "")
    for key in ("socratic_tutor", "code_verification", "mistake_memory", "skill_graph", "benchmark"):
        assert key in adapters["adapters"]
        assert adapters["adapters"][key].get("module_key")
        assert "leetcode" not in str(adapters["adapters"][key].get("module") or "")


def test_no_default_domain_hard_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    from cognispheretutor.integrations.cognisphere import runtime_bridge as bridge

    with pytest.raises(CognisphereIntegrationError) as exc:
        bridge.load_runtime_module("socratic_tutor", domain=None)
    assert exc.value.code == "domain_required"


def test_summarize_knowledge_no_domain_shaped_fallback() -> None:
    from cognispheretutor.integrations.cognisphere.plugin_importer import summarize_knowledge

    # aws-shaped pack: must not invent leetcode expected keys
    summary = summarize_knowledge(
        {
            "domain": "aws_certification",
            "knowledge": {"domains": [{"id": "d1"}], "skills": [{"id": "s1"}]},
            "safety": {},
        }
    )
    assert "problems" not in summary["expected_keys"] or "problems" in summary["counts"]
    assert "domains" in summary["expected_keys"]
    assert summary["counts"]["domains"] == 1

    # plugin-declared expected keys win
    declared = summarize_knowledge(
        {
            "domain": "ap_calculus",
            "expected_knowledge_keys": ["concepts", "theorems"],
            "knowledge": {"concepts": [{"id": "c1"}]},
        }
    )
    assert declared["expected_keys"] == ["concepts", "theorems"]
    assert "knowledge.theorems_empty" in declared["empty_reasons"] or (
        "knowledge.theorems_missing" in declared["empty_reasons"]
    )


def test_runtime_bridge_with_mock_modules(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Unit-test product binding without requiring the live plugins monorepo."""
    from types import SimpleNamespace

    import cognispheretutor.integrations.cognisphere.runtime_bridge as bridge

    monkeypatch.setenv("COGNISPHERE_IMPORT_CACHE_DIR", str(tmp_path))

    def fake_start(slug, *, hint_level=0, persist=True, **kwargs):
        return {
            "status": "ok",
            "session_id": f"p2:{slug}:test",
            "current_phase": "orient",
            "hint_level": hint_level,
            "safety": {"full_solution_included": False, "asks_not_spoils": True},
        }

    def fake_advance(session, *, event="advance", **kwargs):
        updated = dict(session)
        updated["current_phase"] = "probe"
        updated["status"] = "in_progress"
        return updated

    def fake_analyze(outcome, **kwargs):
        return {
            "status": "ok",
            "outcome": outcome.get("outcome"),
            "problem_slug": outcome.get("problem_slug"),
            "explanation": {"summary": "offline"},
        }

    def fake_suggest(*, problem_slug=None, **kwargs):
        return {
            "status": "ok",
            "suggestion": "skill_gap",
            "hint_level": 2,
            "problem_slug": problem_slug or "two-sum",
        }

    def fake_plan(learner_id=None, **kwargs):
        return {
            "status": "ok",
            "path_id": "path-1",
            "skill_ids": ["skill:hash-map"],
            "sequence": [{"skill_id": "skill:hash-map"}],
        }

    def fake_interview(**kwargs):
        return {
            "status": "ok",
            "session": {"session_id": "iv-test", "state": "problem_presentation"},
        }

    modules = {
        "socratic_tutor": SimpleNamespace(
            start_dialogue_session=fake_start,
            advance_dialogue=fake_advance,
        ),
        "code_verification": SimpleNamespace(
            run_categorized_verification=lambda **kw: {"status": "ok", "results": []},
            analyze_outcome=fake_analyze,
        ),
        "mistake_memory": SimpleNamespace(suggest_tutor_focus=fake_suggest),
        "skill_graph": SimpleNamespace(plan_learning_path=fake_plan),
        "benchmark": SimpleNamespace(
            start_interview_session=fake_interview,
            run_interview_flow=lambda responses, **kw: {
                "status": "ok",
                "session": {"state": "completed"},
                "report": {"overall": 0.8},
            },
            list_benchmark_cases=lambda **kw: {"status": "ok", "cases": [{"id": "c1"}]},
        ),
    }

    def fake_load(adapter_name, *, domain=None, root=None, client=None):
        assert domain == "leetcode"
        return modules[adapter_name]

    monkeypatch.setattr(bridge, "load_runtime_module", fake_load)

    started = bridge.start_tutor_session(
        "two-sum", domain="leetcode", hint_level=1, persist=False
    )
    assert started["ok"] is True
    assert started["domain"] == "leetcode"
    assert started["session"]["hint_level"] == 1
    assert started["callback"]["ok"] is True

    advanced = bridge.advance_tutor_session(
        started["session"], domain="leetcode", event="advance"
    )
    assert advanced["session"]["current_phase"] == "probe"

    verified = bridge.verify_submission(
        domain="leetcode",
        slug="two-sum",
        offline_simulated=True,
        outcome={"outcome": "WA", "problem_slug": "two-sum"},
    )
    assert verified["ok"] is True
    assert verified["ingest"]["mode"] == "offline_simulated"

    focus = bridge.suggest_tutor_focus(domain="leetcode", problem_slug="two-sum")
    assert focus["suggestion"]["suggestion"] == "skill_gap"
    assert "skill_gap" in focus["sync"]["suggest_tutor_focus"]

    plan = bridge.plan_skill_path(domain="leetcode", learner_id="learner-1")
    assert plan["mastery"]["learning_store"]["mastery_path_id"] == "path-1"

    interview = bridge.run_interview_session(domain="leetcode", learner_id="learner-1")
    assert interview["ok"] is True
    assert interview["live_llm"] is False


def test_plugins_root_missing() -> None:
    missing = PluginRegistryClient(Path("/nonexistent/cognisphere_plugins_root_xyz"))
    result = missing.list_plugins()
    assert result["ok"] is False
    assert "plugins_root_missing" in result["issues"]
