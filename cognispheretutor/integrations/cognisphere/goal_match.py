"""Domain-agnostic NL goal ↔ plugin manifest semantic matching.

Policy lives in ``manifests/goal_match_policy.json`` (stopwords, keys, thresholds).
Executable code only tokenizes / scores; it never hardcodes domain names.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_POLICY_NAME = "goal_match_policy.json"
_TOKEN_RE = re.compile(r"[a-z0-9]+|[^\W\d_]+", re.UNICODE)


@lru_cache(maxsize=1)
def load_goal_match_policy() -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "manifests" / _POLICY_NAME
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return data


def tokenize_goal(text: str, *, policy: dict[str, Any] | None = None) -> set[str]:
    cfg = policy or load_goal_match_policy()
    min_len = int(cfg.get("min_token_length") or 3)
    stop = {str(s).casefold() for s in (cfg.get("stopwords") or [])}
    tokens: set[str] = set()
    for raw in _TOKEN_RE.findall(str(text or "").casefold()):
        tok = raw.strip().casefold()
        if len(tok) < min_len or tok in stop:
            continue
        tokens.add(tok)
    return tokens


def _split_identifier(value: str) -> list[str]:
    text = str(value or "")
    parts = re.split(r"[^a-zA-Z0-9]+", text)
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        # camelCase / snake fragments already split; also split digit boundaries lightly
        out.append(part)
        for piece in re.findall(r"[a-z]+|[A-Z][a-z]*|\d+", part):
            if piece and piece.casefold() != part.casefold():
                out.append(piece)
    return out


def manifest_search_tokens(
    manifest: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
) -> set[str]:
    cfg = policy or load_goal_match_policy()
    min_len = int(cfg.get("min_token_length") or 3)
    stop = {str(s).casefold() for s in (cfg.get("stopwords") or [])}
    tokens: set[str] = set()

    def _add(text: Any) -> None:
        for piece in _split_identifier(str(text or "")):
            tok = piece.casefold()
            if len(tok) < min_len or tok in stop:
                continue
            tokens.add(tok)
        for tok in tokenize_goal(str(text or ""), policy=cfg):
            tokens.add(tok)

    for key in cfg.get("manifest_text_keys") or []:
        if key in manifest and manifest.get(key) is not None:
            _add(manifest.get(key))
    for key in cfg.get("manifest_list_keys") or []:
        values = manifest.get(key)
        if isinstance(values, list):
            for item in values:
                _add(item)
        elif values is not None:
            _add(values)
    return tokens


def score_goal_against_manifest(
    goal: str,
    manifest: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
) -> int:
    """Return overlap count between goal tokens and manifest searchable tokens."""
    cfg = policy or load_goal_match_policy()
    goal_tokens = tokenize_goal(goal, policy=cfg)
    if not goal_tokens:
        return 0
    haystack = manifest_search_tokens(manifest, policy=cfg)
    return len(goal_tokens & haystack)


def filter_matches_by_goal(
    matches: list[dict[str, Any]],
    goal: str,
    *,
    manifests_by_domain: dict[str, dict[str, Any]] | None = None,
    policy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Fail-closed semantic filter when ``goal`` is non-empty.

    When the goal has no usable tokens after stopword removal, returns an empty
    list (fail-closed) rather than falling back to capability-only matches.
    """
    cfg = policy or load_goal_match_policy()
    text = str(goal or "").strip()
    if not text:
        return list(matches)
    if not cfg.get("fail_closed_when_goal", True):
        return list(matches)

    min_score = int(cfg.get("min_score") or 1)
    goal_tokens = tokenize_goal(text, policy=cfg)
    if not goal_tokens:
        return []

    scored: list[dict[str, Any]] = []
    lookup = manifests_by_domain or {}
    for item in matches:
        manifest = dict(item.get("manifest") or {})
        if not manifest:
            domain = str(item.get("domain") or "")
            manifest = dict(lookup.get(domain) or {})
        # Allow match rows that already embed searchable fields.
        if not manifest:
            manifest = {
                "domain": item.get("domain"),
                "plugin_id": item.get("plugin_id"),
                "capabilities": item.get("available") or item.get("capabilities") or [],
                "keywords": item.get("keywords") or [],
                "tags": item.get("tags") or [],
                "aliases": item.get("aliases") or [],
                "display_name": item.get("display_name"),
                "description": item.get("description"),
            }
        score = score_goal_against_manifest(text, manifest, policy=cfg)
        if score < min_score:
            continue
        row = dict(item)
        row["goal_score"] = score
        scored.append(row)
    scored.sort(key=lambda row: (-int(row.get("goal_score") or 0), str(row.get("domain") or "")))
    return scored


__all__ = [
    "filter_matches_by_goal",
    "load_goal_match_policy",
    "manifest_search_tokens",
    "score_goal_against_manifest",
    "tokenize_goal",
]
