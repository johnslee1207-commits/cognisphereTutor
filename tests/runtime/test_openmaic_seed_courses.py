from __future__ import annotations

import json
from pathlib import Path

from cognispheretutor.runtime import openmaic_seed_courses


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return b'{"url":"http://127.0.0.1:33100/classroom/course-1"}'


def test_seed_openmaic_courseware_posts_packaged_classroom(monkeypatch, tmp_path: Path) -> None:
    seed_dir = tmp_path / "courseware"
    seed_dir.mkdir()
    (seed_dir / "course-1.json").write_text(
        json.dumps(
            {
                "stage": {"id": "course-1", "name": "Course One"},
                "scenes": [{"id": "scene-1", "stageId": "course-1"}],
            }
        ),
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.get_method()
        seen["timeout"] = timeout
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse()

    monkeypatch.setattr(openmaic_seed_courses.urlrequest, "urlopen", fake_urlopen)

    result = openmaic_seed_courses.seed_openmaic_courseware(
        "http://127.0.0.1:33100/",
        courseware_dir=seed_dir,
        timeout=3,
    )

    assert result[0].ok is True
    assert result[0].course_id == "course-1"
    assert result[0].classroom_url == "http://127.0.0.1:33100/classroom/course-1"
    assert seen == {
        "url": "http://127.0.0.1:33100/api/classroom",
        "method": "POST",
        "timeout": 3,
        "body": {
            "stage": {"id": "course-1", "name": "Course One"},
            "scenes": [{"id": "scene-1", "stageId": "course-1"}],
        },
    }


def test_seed_openmaic_courseware_noops_when_no_seed_dir(tmp_path: Path) -> None:
    assert (
        openmaic_seed_courses.seed_openmaic_courseware(
            "http://127.0.0.1:33100",
            courseware_dir=tmp_path / "missing",
        )
        == []
    )
