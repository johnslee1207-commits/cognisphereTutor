"""Fixture cognisphereTutor entrypoint for aws_certification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DOMAIN = "aws_certification"
_MANIFEST = Path(__file__).resolve().parents[3] / "plugin_manifest.json"


def _manifest() -> dict[str, Any]:
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


def export_deeptutor_package() -> dict[str, Any]:
    try:
        from fixture_plugins._common import export_package_for

        return export_package_for(DOMAIN)
    except ImportError:
        manifest = _manifest()
        return {
            "ok": True,
            "bundle": {
                "bundle_id": f"{DOMAIN}.deeptutor_handoff",
                "domain": DOMAIN,
                "plugin_id": manifest.get("plugin_id"),
                "exported_at": "2026-07-24T00:00:00+00:00",
                "learning_loop": ["plan", "teach", "assess", "memory"],
                "knowledge": {
                    "domains": [{"id": "saa", "name": "Solutions Architect Associate"}],
                    "skills": [{"id": "well-architected", "name": "Well-Architected"}],
                },
                "safety": {
                    "no_answer_keys": True,
                    "no_full_solution_dump": True,
                    "source_of_truth": "cognisphere_plugin_pack",
                },
            },
            "validation": {"ok": True, "issues": []},
        }


def validate_adapter() -> dict[str, Any]:
    return {"ok": True, "issues": [], "handoff_contract": {"ok": True, "issues": []}}


def negotiate_capabilities(request: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = _manifest()
    req = request or {}
    required = list(req.get("required_capabilities") or [])
    available = list(manifest.get("capabilities") or [])
    missing = [c for c in required if c not in available]
    return {
        "plugin": manifest.get("plugin_id"),
        "domain": DOMAIN,
        "available": available,
        "required": required,
        "missing": missing,
        "matched": not missing,
        "forbidden_in_plugin": list(manifest.get("forbidden_in_plugin") or []),
    }
