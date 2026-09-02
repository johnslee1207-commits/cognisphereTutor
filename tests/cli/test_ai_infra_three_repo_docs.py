from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_ai_infra_three_repo_docs_define_content_only_and_full_twin_modes() -> None:
    doc = (ROOT / "docs" / "AI_INFRA_THREE_REPO_DEPLOYMENT_ZH.md").read_text(
        encoding="utf-8"
    )

    assert "内容学习模式" in doc
    assert "完整安装" in doc
    assert "cognisphereTutor" in doc
    assert "CognisphereLearningPlugins" in doc
    assert "AetherAI-Infra-Twin" in doc
    assert "运行真实 lab" in doc
    assert "生成新的 evidence bundle" in doc


def test_ai_infra_env_example_points_to_plugin_and_twin_boundaries() -> None:
    example = (ROOT / "examples" / "ai_infra_three_repo.env.example").read_text(
        encoding="utf-8"
    )

    assert "COGNISPHERE_LEARNING_PLUGINS_ROOT" in example
    assert "AETHERINFRA_TWIN_BASE_URL" in example
    assert "AETHERINFRA_TWIN_EMBED_URL" in example
