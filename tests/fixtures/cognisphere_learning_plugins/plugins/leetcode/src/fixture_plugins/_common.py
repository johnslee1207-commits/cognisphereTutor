"""Shared helpers for Cognisphere Learning Plugins test fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# .../plugins/leetcode/src/fixture_plugins/_common.py → fixture monorepo root
_FIXTURE_ROOT = Path(__file__).resolve().parents[4]

_DEFAULT_LOOP = [
    "Assessment",
    "Knowledge Gap",
    "Learning Plan",
    "Practice",
    "Mistake Memory",
    "Mastery Update",
]


def _manifest(domain: str) -> dict[str, Any]:
    path = _FIXTURE_ROOT / "plugins" / domain / "plugin_manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def plugin_info_for(domain: str) -> dict[str, Any]:
    manifest = _manifest(domain)
    return {
        "host": "cognisphere",
        "domain": domain,
        "plugin_id": manifest.get("plugin_id"),
        "version": manifest.get("version"),
        "capabilities": list(manifest.get("capabilities") or []),
        "forbidden_in_plugin": list(manifest.get("forbidden_in_plugin") or []),
    }


def negotiate_for(domain: str, request: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = _manifest(domain)
    req = request or {}
    required = list(req.get("required_capabilities") or [])
    available = list(manifest.get("capabilities") or [])
    missing = [cap for cap in required if cap not in available]
    return {
        "plugin": manifest.get("plugin_id"),
        "domain": domain,
        "available": available,
        "required": required,
        "missing": missing,
        "matched": not missing,
        "forbidden_in_plugin": list(manifest.get("forbidden_in_plugin") or []),
        "goal": req.get("goal"),
    }


def validate_adapter_for(domain: str) -> dict[str, Any]:
    manifest = _manifest(domain)
    return {
        "ok": True,
        "domain": domain,
        "plugin_id": manifest.get("plugin_id"),
        "issues": [],
        "handoff_contract": {
            "ok": True,
            "issues": [],
            "contract": {
                "bundle_schema_version": "1",
                "source_of_truth": "cognisphere_plugin_pack",
            },
            "plugin_id": manifest.get("plugin_id"),
            "domain": domain,
        },
    }


def export_package_for(domain: str) -> dict[str, Any]:
    manifest = _manifest(domain)
    if domain == "leetcode":
        knowledge: dict[str, Any] = {
            "problems": [{"slug": "two-sum", "title": "Two Sum", "difficulty": "Easy"}],
            "patterns": [{"pattern_id": "pattern:hash-map", "name": "Hash Map"}],
            "skills": [{"skill_id": "skill:array", "name": "Array"}],
        }
    elif domain == "ap_calculus":
        knowledge = {
            "concepts": [{"id": "limits", "name": "Limits"}],
            "skills": [{"id": "differentiate", "name": "Differentiate"}],
            "theorems": [{"id": "ftc", "name": "Fundamental Theorem of Calculus"}],
            "problem_patterns": [{"id": "related-rates", "name": "Related Rates"}],
            "catalog": [{"unit": "AB.1", "topic": "Limits"}],
        }
    else:
        knowledge = {
            "domains": [{"id": "saa", "name": "Solutions Architect Associate"}],
            "skills": [{"id": "well-architected", "name": "Well-Architected"}],
        }

    bundle = {
        "bundle_id": f"{domain}.deeptutor_handoff",
        "domain": domain,
        "plugin_id": manifest.get("plugin_id"),
        "exported_at": "2026-07-24T00:00:00+00:00",
        "bundle_schema_version": "1",
        "learning_loop": list(_DEFAULT_LOOP),
        "forbidden_in_export": ["verified_code_solutions", "full_official_problem_statements"],
        "knowledge": knowledge,
        "safety": {
            "no_answer_keys": True,
            "no_full_solution_dump": True,
            "source_of_truth": "cognisphere_plugin_pack",
            "tutor_asks_not_spoils": True,
        },
    }
    return {
        "ok": True,
        "bundle": bundle,
        "validation": {
            "ok": True,
            "issues": [],
            "contract": {"bundle_schema_version": "1"},
            "plugin_id": manifest.get("plugin_id"),
            "domain": domain,
        },
    }
