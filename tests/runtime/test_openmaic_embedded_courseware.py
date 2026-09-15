from __future__ import annotations

import json
from pathlib import Path
import re


def test_embedded_openmaic_electrical_courseware_is_packaged() -> None:
    path = (
        Path("cognispheretutor")
        / "vendor"
        / "openmaic-courseware"
        / "california-electrical-entrance-courseware-v5.json"
    )

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["stage"]["id"] == "california-electrical-entrance-courseware-v5"
    assert payload["stage"]["name"] == "电工入门考试详细讲课课件"
    assert len(payload["scenes"]) >= 100
    assert sum(1 for scene in payload["scenes"] if scene["type"] == "quiz") >= 60


def test_embedded_openmaic_electrical_courseware_has_english_seed() -> None:
    path = (
        Path("cognispheretutor")
        / "vendor"
        / "openmaic-courseware"
        / "california-electrical-entrance-courseware-en-v1.json"
    )

    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)

    assert payload["stage"]["id"] == "california-electrical-entrance-courseware-en-v1"
    assert payload["stage"]["name"] == "California Electrical Entrance Exam Prep Courseware"
    assert payload["stage"]["languageDirective"] == "en-US"
    assert len(payload["scenes"]) >= 120
    assert sum(1 for scene in payload["scenes"] if scene["type"] == "quiz") >= 20
    assert re.search(r"[\u4e00-\u9fff]", raw) is None
