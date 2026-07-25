"""Persona visibility helpers for multi-user workspaces.

Personas are behaviour/voice presets (not privileged workflows): every user
sees their own workspace personas; non-admins also see admin-authored presets
as read-only, with own names shadowing admin names. No grant gate applies.
"""

from __future__ import annotations

from typing import Any

from cognispheretutor.multi_user.context import get_current_user
from cognispheretutor.multi_user.paths import get_admin_path_service
from cognispheretutor.services.persona import (
    InvalidPersonaNameError,
    PersonaNotFoundError,
    PersonaService,
    get_persona_service,
)


def admin_persona_service() -> PersonaService:
    return PersonaService(root=get_admin_path_service().get_workspace_dir() / "personas")


def list_visible_personas() -> list[dict[str, Any]]:
    """Own personas; non-admins also get unread admin presets (shadowed by name)."""
    service = get_persona_service()
    own = [info.to_dict() for info in service.list_personas()]
    user = get_current_user()
    if user.is_admin:
        return own
    own_names = {item["name"] for item in own}
    merged = list(own)
    for preset in admin_persona_service().list_personas():
        if preset.name in own_names:
            continue
        entry = preset.to_dict()
        entry.update({"source": "admin", "read_only": True})
        merged.append(entry)
    return merged


def get_visible_persona_detail(name: str) -> dict[str, Any] | None:
    """Resolve persona detail: own workspace first, then admin preset for non-admins."""
    service = get_persona_service()
    try:
        return service.get_detail(name).to_dict()
    except PersonaNotFoundError:
        pass
    except InvalidPersonaNameError:
        raise

    user = get_current_user()
    if user.is_admin:
        return None
    try:
        detail = admin_persona_service().get_detail(name).to_dict()
        detail.update({"source": "admin", "read_only": True})
        return detail
    except (PersonaNotFoundError, InvalidPersonaNameError):
        return None


def load_persona_for_context(name: str) -> str:
    """Load persona markdown for chat context (own first, admin fallback)."""
    requested = str(name or "").strip()
    if not requested:
        return ""
    text = get_persona_service().load_for_context(requested)
    if text:
        return text
    user = get_current_user()
    if user.is_admin:
        return ""
    return admin_persona_service().load_for_context(requested)


def iter_visible_persona_entries() -> list[tuple[PersonaService, Any]]:
    """[(service, info)] for own + admin-preset personas (name-shadowed)."""
    entries: list[tuple[PersonaService, Any]] = []
    seen: set[str] = set()
    service = get_persona_service()
    for info in service.list_personas():
        entries.append((service, info))
        seen.add(info.name)
    user = get_current_user()
    if not user.is_admin:
        admin_service = admin_persona_service()
        for info in admin_service.list_personas():
            if info.name not in seen:
                entries.append((admin_service, info))
    return entries
