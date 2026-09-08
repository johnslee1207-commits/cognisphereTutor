from __future__ import annotations

import json
from pathlib import Path


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
