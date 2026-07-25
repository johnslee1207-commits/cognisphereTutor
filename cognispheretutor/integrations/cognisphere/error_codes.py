"""Product-facing error codes for Cognisphere plugin integration."""

from __future__ import annotations

from typing import Any

from cognispheretutor.integrations.cognisphere._contract import load_error_code_catalog


class CognisphereIntegrationError(Exception):
    """Structured integration failure with a stable ``code``."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        catalog = load_error_code_catalog().get("codes") or {}
        meta = catalog.get(code) or {}
        self.code = code
        self.details = details or {}
        self.meaning = str(meta.get("meaning") or "")
        self.handling = str(meta.get("handling") or "")
        resolved = message or self.meaning or code
        super().__init__(resolved)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": False,
            "code": self.code,
            "message": str(self),
            "meaning": self.meaning,
            "handling": self.handling,
            "details": self.details,
        }


def describe_error(code: str) -> dict[str, Any]:
    catalog = load_error_code_catalog().get("codes") or {}
    meta = catalog.get(code) or {}
    return {
        "code": code,
        "meaning": meta.get("meaning"),
        "handling": meta.get("handling"),
        "known": code in catalog,
    }


def format_issue(code: str, suffix: str | None = None) -> str:
    """Build SDK-aligned issue tokens such as ``missing_plugin_manifest:{domain}``."""
    if suffix:
        return f"{code}:{suffix}"
    return code
