"""Fixture cognisphereTutor entrypoint for ap_calculus."""

from __future__ import annotations

from typing import Any

# Reuse shared fixture helpers from the leetcode pack src layout when on path;
# otherwise build a local export (tests add each domain src separately).
DOMAIN = "ap_calculus"


def _export_local() -> dict[str, Any]:
    from pathlib import Path
    import json

    manifest = json.loads(
        (Path(__file__).resolve().parents[3] / "plugin_manifest.json").read_text(encoding="utf-8")
    )
    bundle = {
        "bundle_id": f"{DOMAIN}.deeptutor_handoff",
        "domain": DOMAIN,
        "plugin_id": manifest.get("plugin_id"),
        "exported_at": "2026-07-24T00:00:00+00:00",
        "learning_loop": [
            "Assessment",
            "Knowledge Gap",
            "Learning Plan",
            "Practice",
            "Mistake Memory",
            "Mastery Update",
        ],
        "knowledge": {
            "concepts": [{"id": "limits", "name": "Limits"}],
            "skills": [{"id": "differentiate", "name": "Differentiate"}],
            "theorems": [{"id": "ftc", "name": "Fundamental Theorem of Calculus"}],
            "problem_patterns": [{"id": "related-rates", "name": "Related Rates"}],
            "catalog": [{"unit": "AB.1", "topic": "Limits"}],
        },
        "safety": {
            "no_answer_keys": True,
            "no_full_solution_dump": True,
            "source_of_truth": "cognisphere_plugin_pack",
        },
    }
    return {
        "ok": True,
        "bundle": bundle,
        "validation": {"ok": True, "issues": [], "plugin_id": manifest.get("plugin_id")},
    }


def export_deeptutor_package() -> dict[str, Any]:
    try:
        from fixture_plugins._common import export_package_for

        return export_package_for(DOMAIN)
    except ImportError:
        return _export_local()


def validate_adapter() -> dict[str, Any]:
    try:
        from fixture_plugins._common import validate_adapter_for

        return validate_adapter_for(DOMAIN)
    except ImportError:
        exported = export_deeptutor_package()
        return {
            "ok": True,
            "issues": [],
            "handoff_contract": exported.get("validation") or {"ok": True, "issues": []},
        }


def negotiate_capabilities(request: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from fixture_plugins._common import negotiate_for

        return negotiate_for(DOMAIN, request)
    except ImportError:
        from pathlib import Path
        import json

        manifest = json.loads(
            (Path(__file__).resolve().parents[3] / "plugin_manifest.json").read_text(encoding="utf-8")
        )
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
