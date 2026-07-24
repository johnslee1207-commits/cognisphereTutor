"""DT-P4/P5 — runtime callbacks for tutor / sandbox / memory / mastery."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cognispheretutor.integrations.cognisphere._contract import load_plugin_contract
from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError
from cognispheretutor.integrations.cognisphere.security_gates import assert_sandbox_authorized


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_runtime_state_dir(*, session_id: str | None = None) -> Path:
    contract = load_plugin_contract()
    rel = str(contract.get("runtime_state_relative_workspace_path") or "cognisphere_runtime")
    try:
        from cognispheretutor.services.path_service import get_path_service

        base = get_path_service().get_workspace_dir() / rel
    except Exception:  # noqa: BLE001
        base = Path.cwd() / "data" / "user" / "workspace" / rel
    if session_id:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in session_id)
        return (base / "sessions" / safe).resolve()
    return base.resolve()


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def on_tutor_session_event(session_id: str, event: dict[str, Any]) -> dict[str, Any]:
    """Accept Socratic tutor session events; persist for product binding (DT-P4)."""
    hint_level = event.get("hint_level")
    if hint_level is not None:
        try:
            level = int(hint_level)
        except (TypeError, ValueError) as exc:
            raise CognisphereIntegrationError(
                "tutor_must_ask_not_spoil",
                message=f"invalid hint_level: {hint_level!r}",
                details={"session_id": session_id},
            ) from exc
        if level < 0 or level > 4:
            raise CognisphereIntegrationError(
                "tutor_must_ask_not_spoil",
                message="hint_level must be 0–4",
                details={"session_id": session_id, "hint_level": level},
            )

    if event.get("full_solution_included") is True or event.get("spoilers") is True:
        raise CognisphereIntegrationError(
            "tutor_must_ask_not_spoil",
            details={"session_id": session_id, "event_type": event.get("type")},
        )

    record = {
        "session_id": session_id,
        "received_at": _utc_now(),
        "event": event,
        "phase": "DT-P4",
    }
    state_dir = resolve_runtime_state_dir(session_id=session_id)
    _append_jsonl(state_dir / "events.jsonl", record)

    stage = event.get("stage_id") or event.get("stage") or event.get("type")
    return {
        "ok": True,
        "phase": "DT-P4",
        "status": "accepted",
        "session_id": session_id,
        "event_type": event.get("type"),
        "stage": stage,
        "hint_level": hint_level,
        "artifact_path": str(state_dir),
        "product_binding": {
            "capability": "mastery_path",
            "notes": "Event logged for Guided Learning / Socratic loop binding",
        },
    }


def ingest_sandbox_result(result: dict[str, Any]) -> dict[str, Any]:
    """Only accept authorized live results or explicit offline simulations."""
    if result.get("offline_simulated") is True:
        mode = "offline_simulated"
    else:
        assert_sandbox_authorized()
        mode = "authorized_live"

    session_id = str(result.get("session_id") or result.get("slug") or "sandbox")
    state_dir = resolve_runtime_state_dir(session_id=session_id)
    record = {
        "received_at": _utc_now(),
        "mode": mode,
        "result": result,
        "phase": "DT-P4",
    }
    _append_jsonl(state_dir / "sandbox_results.jsonl", record)

    # DT-P5 hook: failed sandboxes become mistake-memory candidates.
    mistake_sync: dict[str, Any] | None = None
    if result.get("passed") is False or result.get("status") == "failed":
        mistake_sync = sync_mistake_memory(
            {
                "source": "sandbox",
                "mode": mode,
                "session_id": session_id,
                "slug": result.get("slug"),
                "error": result.get("error") or result.get("stderr") or result.get("message"),
                "offline_simulated": result.get("offline_simulated") is True,
            }
        )

    return {
        "ok": True,
        "mode": mode,
        "phase": "DT-P4",
        "result": result,
        "artifact_path": str(state_dir),
        "mistake_memory": mistake_sync,
    }


def sync_mistake_memory(payload: Any) -> dict[str, Any]:
    """Persist mistake-memory records under workspace (DT-P5 product binding)."""
    records = payload if isinstance(payload, list) else [payload]
    normalized: list[dict[str, Any]] = []
    for item in records:
        if isinstance(item, dict):
            normalized.append(dict(item))
        else:
            normalized.append({"value": item})

    focus_suggestions: list[str] = []
    for item in normalized:
        slug = item.get("slug") or item.get("skill_id") or item.get("concept_id")
        if slug:
            focus_suggestions.append(str(slug))
        if item.get("suggest_tutor_focus"):
            focus_suggestions.append(str(item["suggest_tutor_focus"]))

    state_dir = resolve_runtime_state_dir()
    memory_dir = state_dir / "mistake_memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    envelope = {
        "synced_at": _utc_now(),
        "phase": "DT-P5",
        "records": normalized,
        "suggest_tutor_focus": focus_suggestions,
    }
    out = memory_dir / f"sync_{_utc_now().replace(':', '').replace('+', '_')}.json"
    out.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    _append_jsonl(memory_dir / "index.jsonl", {"path": str(out), "count": len(normalized)})

    return {
        "ok": True,
        "phase": "DT-P5",
        "status": "synced",
        "record_count": len(normalized),
        "suggest_tutor_focus": focus_suggestions,
        "artifact_path": str(out),
        "product_binding": {
            "next_step": "Prefer suggested focus ids when recommending next practice item",
        },
    }


def apply_mastery_update(evidence: dict[str, Any]) -> dict[str, Any]:
    """Record mastery / skill-graph evidence for Guided Learning (DT-P5)."""
    if not isinstance(evidence, dict):
        raise CognisphereIntegrationError(
            "export_envelope_invalid",
            message="mastery evidence must be an object",
        )

    state_dir = resolve_runtime_state_dir()
    mastery_dir = state_dir / "mastery"
    mastery_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "applied_at": _utc_now(),
        "phase": "DT-P5",
        "evidence": evidence,
        "skill_ids": list(evidence.get("skill_ids") or evidence.get("skills") or []),
        "passed": evidence.get("passed"),
        "path_id": evidence.get("path_id") or evidence.get("mastery_path_id"),
    }
    out = mastery_dir / f"update_{_utc_now().replace(':', '').replace('+', '_')}.json"
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    # Soft product hook: when a mastery_path_id is present, note LearningStore binding.
    learning_store_note = None
    path_id = record.get("path_id")
    if path_id:
        learning_store_note = {
            "mastery_path_id": path_id,
            "binding": "cognispheretutor.learning.storage.LearningStore",
            "status": "evidence_recorded_for_path",
        }

    return {
        "ok": True,
        "phase": "DT-P5",
        "status": "applied",
        "evidence_keys": sorted(evidence.keys()),
        "artifact_path": str(out),
        "learning_store": learning_store_note,
        "product_binding": {
            "capability": "mastery_path",
            "notes": "Evidence cached; session UI may call MasteryStatusTool for live path state",
        },
    }


def require_authorized_or_simulated(result: dict[str, Any]) -> None:
    if result.get("offline_simulated") is True:
        return
    assert_sandbox_authorized()
