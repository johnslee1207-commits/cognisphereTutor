"""Tests for multi_user.persona_access visibility helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from cognispheretutor.multi_user import persona_access
from cognispheretutor.services.persona import PersonaService


@pytest.fixture()
def persona_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    user_root = tmp_path / "user" / "personas"
    admin_root = tmp_path / "admin" / "personas"
    user_root.mkdir(parents=True)
    admin_root.mkdir(parents=True)

    PersonaService(root=user_root).create("coach", description="user", content="Be a coach.")
    PersonaService(root=admin_root).create("mentor", description="admin", content="Be a mentor.")
    PersonaService(root=admin_root).create(
        "coach", description="admin-shadowed", content="Admin coach."
    )

    monkeypatch.setattr(
        persona_access,
        "get_persona_service",
        lambda: PersonaService(root=user_root),
    )
    monkeypatch.setattr(
        persona_access,
        "admin_persona_service",
        lambda: PersonaService(root=admin_root),
    )
    return user_root, admin_root


def test_list_visible_personas_admin_sees_own_only(persona_roots, as_user) -> None:
    with as_user("admin", role="admin"):
        names = {p["name"] for p in persona_access.list_visible_personas()}
    assert names == {"coach"}


def test_list_visible_personas_user_sees_admin_presets(persona_roots, as_user) -> None:
    with as_user("u1", role="user"):
        personas = persona_access.list_visible_personas()
    by_name = {p["name"]: p for p in personas}
    assert set(by_name) == {"coach", "mentor"}
    assert by_name["coach"].get("source") != "admin"  # own shadows admin
    assert by_name["mentor"].get("source") == "admin"
    assert by_name["mentor"].get("read_only") is True


def test_load_persona_for_context_falls_back_to_admin(persona_roots, as_user) -> None:
    with as_user("u1", role="user"):
        text = persona_access.load_persona_for_context("mentor")
    assert "Be a mentor" in text
