from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "publish_openmaic_electrical_entrance_courseware.py"
SPEC = importlib.util.spec_from_file_location(
    "publish_openmaic_electrical_entrance_courseware",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
courseware = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(courseware)


def test_write_seed_document_normalizes_timestamps(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(courseware, "SEED_DIR", tmp_path)
    document = {
        "stage": {"id": "course-1", "name": "Course", "createdAt": 123, "updatedAt": 456},
        "scenes": [
            {
                "id": "scene-1",
                "stageId": "course-1",
                "createdAt": 123,
                "updatedAt": 456,
            }
        ],
    }

    path = courseware.write_seed_document(document, "course-1")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["stage"]["createdAt"] == 0
    assert payload["stage"]["updatedAt"] == 0
    assert payload["scenes"][0]["createdAt"] == 0
    assert payload["scenes"][0]["updatedAt"] == 0
