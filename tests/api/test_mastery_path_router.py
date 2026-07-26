from __future__ import annotations

from pathlib import Path

import pytest

from cognispheretutor.api.routers import mastery_path
from cognispheretutor.learning.models import (
    KnowledgePoint,
    KnowledgeType,
    LearningModule,
    LearningProgress,
)
from cognispheretutor.learning.storage import LearningStore


class _FakePathService:
    def __init__(self, root: Path) -> None:
        self._root = root

    def get_workspace_dir(self) -> Path:
        return self._root / "workspace"


@pytest.mark.asyncio
async def test_redo_progress_creates_restorable_backup(tmp_path, monkeypatch) -> None:
    import cognispheretutor.learning.storage as storage_mod

    async def fake_cancel(_book_id: str) -> None:
        return None

    fake_paths = _FakePathService(tmp_path)
    monkeypatch.setattr(storage_mod, "get_path_service", lambda: fake_paths)
    monkeypatch.setattr(mastery_path, "get_path_service", lambda: fake_paths)
    monkeypatch.setattr(mastery_path, "_cancel_active_learning_turn", fake_cancel)

    store = LearningStore()
    progress = LearningProgress(
        book_id="csphere-aws_certification",
        modules=[
            LearningModule(
                id="aws-overview",
                name="AWS overview",
                order=0,
                knowledge_points=[
                    KnowledgePoint(
                        id="aws-cloud",
                        name="Cloud foundations",
                        type=KnowledgeType.CONCEPT,
                        module_id="aws-overview",
                    )
                ],
            )
        ],
        current_module_id="aws-overview",
        mastery_levels={"aws-cloud": 1.0},
        qualitative_mastery={"aws-cloud": True},
    )
    store.save(progress)

    redo_result = await mastery_path.redo_progress("csphere-aws_certification")
    redone = store.load("csphere-aws_certification")

    assert redo_result["status"] == "ok"
    assert redo_result["backup"]["backup_id"]
    assert redone is not None
    assert redone.mastery_levels == {}
    assert redone.qualitative_mastery == {}

    restore_result = await mastery_path.restore_progress("csphere-aws_certification")
    restored = store.load("csphere-aws_certification")

    assert restore_result["status"] == "ok"
    assert restored is not None
    assert restored.mastery_levels == {"aws-cloud": 1.0}
    assert restored.qualitative_mastery == {"aws-cloud": True}
