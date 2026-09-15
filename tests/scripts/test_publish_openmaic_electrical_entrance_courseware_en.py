from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "publish_openmaic_electrical_entrance_courseware_en.py"
SPEC = importlib.util.spec_from_file_location(
    "publish_openmaic_electrical_entrance_courseware_en",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
courseware = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(courseware)


def test_write_seed_document_normalizes_english_courseware(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(courseware, "SEED_DIR", tmp_path)
    document = courseware.build_document("course-en")

    path = courseware.write_seed_document(document, "course-en")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["stage"]["id"] == "course-en"
    assert payload["stage"]["name"] == "California Electrical Entrance Exam Prep Courseware"
    assert payload["stage"]["languageDirective"] == "en-US"
    assert payload["stage"]["createdAt"] == 0
    assert payload["stage"]["updatedAt"] == 0
    assert len(payload["scenes"]) >= 120
    assert all(scene["createdAt"] == 0 for scene in payload["scenes"])
    assert all(scene["updatedAt"] == 0 for scene in payload["scenes"])
