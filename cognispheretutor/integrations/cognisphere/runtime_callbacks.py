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
    receipt = {
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
    _publish_tutor_bus_event(session_id, event, receipt)
    return receipt


def _publish_tutor_bus_event(
    session_id: str,
    event: dict[str, Any],
    receipt: dict[str, Any],
) -> None:
    """Best-effort fan-out to EventBus for SSE / product subscribers."""
    try:
        import asyncio

        from cognispheretutor.events.event_bus import Event, EventType, get_event_bus

        bus = get_event_bus()
        payload = Event(
            type=EventType.COGNISPHERE_TUTOR,
            task_id=session_id,
            user_input=str(event.get("type") or "tutor_event"),
            agent_output=str(receipt.get("stage") or ""),
            metadata={
                "session_id": session_id,
                "event": event,
                "receipt": receipt,
                "capability": "mastery_path",
            },
        )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(bus.publish(payload))
    except Exception:  # noqa: BLE001 — never fail the product binding write path
        pass


def _resolve_mastery_path_id(payload: dict[str, Any]) -> str | None:
    """Resolve LearningStore book_id from explicit path or domain (no invented defaults)."""
    path_id = payload.get("path_id") or payload.get("mastery_path_id")
    if path_id:
        text = str(path_id).strip()
        return text or None
    domain = payload.get("domain")
    if domain and str(domain).strip():
        from cognispheretutor.learning.cognisphere_seed import mastery_path_id_for_domain

        return mastery_path_id_for_domain(str(domain).strip())
    return None


def _candidate_focus_ids(payload: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    for key in ("slug", "skill_id", "concept_id", "knowledge_point_id", "kp_id"):
        value = payload.get(key)
        if value:
            candidates.append(str(value))
    for skill in payload.get("skill_ids") or payload.get("skills") or []:
        if skill:
            candidates.append(str(skill))
    if payload.get("suggest_tutor_focus"):
        candidates.append(str(payload["suggest_tutor_focus"]))
    # De-dupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for item in candidates:
        text = item.strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _match_knowledge_point_ids(progress: Any, candidates: list[str]) -> list[str]:
    kp_ids = [kp.id for m in progress.modules for kp in m.knowledge_points]
    matched: list[str] = []
    for cand in candidates:
        bare = cand.split(":")[-1].strip().lower()
        if not bare:
            continue
        for kid in kp_ids:
            kl = kid.lower()
            if (
                kl == cand.lower()
                or kl == bare
                or kl.endswith(f"-{bare}")
                or f"-{bare}-" in f"-{kl}-"
                or bare in kl
            ):
                if kid not in matched:
                    matched.append(kid)
    return matched


def bind_runtime_feedback_to_learning(
    payload: dict[str, Any],
    *,
    passed: bool | None = None,
    stage: str | None = None,
    source: str = "runtime_callback",
) -> dict[str, Any]:
    """Update LearningService mastery/stage when a path exists and evidence is clear.

    Fail-closed: missing path → skipped; missing progress file → path_not_found;
    no matching KP → recorded but unbound. Never invents a domain or path.
    """
    path_id = _resolve_mastery_path_id(payload)
    if not path_id:
        return {
            "status": "skipped_no_path",
            "binding": "cognispheretutor.learning.service.LearningService",
            "reason": "path_id/mastery_path_id/domain required for LearningService bind",
            "source": source,
        }

    try:
        from cognispheretutor.learning.models import LearningStage
        from cognispheretutor.learning.service import LearningService
        from cognispheretutor.learning.storage import LearningStore

        service = LearningService(LearningStore())
        progress = service._store.load(path_id)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "bind_error",
            "mastery_path_id": path_id,
            "binding": "cognispheretutor.learning.service.LearningService",
            "error": str(exc),
            "source": source,
        }

    if progress is None:
        return {
            "status": "path_not_found",
            "mastery_path_id": path_id,
            "binding": "cognispheretutor.learning.service.LearningService",
            "reason": "No seeded Mastery Path for this id; import-and-seed first",
            "source": source,
        }

    candidates = _candidate_focus_ids(payload)
    matched = _match_knowledge_point_ids(progress, candidates)
    updated: list[str] = []
    outcome = passed if passed is not None else payload.get("passed")
    if isinstance(outcome, bool) and matched:
        for kp_id in matched:
            if outcome:
                service.record_qualitative(
                    progress,
                    kp_id,
                    passed=True,
                    evidence=f"cognisphere:{source}",
                )
            else:
                current = float(progress.mastery_levels.get(kp_id, 0.0) or 0.0)
                service.update_mastery(progress, kp_id, min(current, 0.35))
                progress.qualitative_mastery[kp_id] = False
            updated.append(kp_id)

    stage_raw = stage or payload.get("stage") or payload.get("stage_id")
    stage_applied = None
    if stage_raw:
        try:
            progress.current_stage = LearningStage(str(stage_raw))
            stage_applied = progress.current_stage.value
        except ValueError:
            stage_applied = None

    if matched and isinstance(outcome, bool):
        # Prefer first matched KP as current focus after sandbox/mistake feedback.
        for module in progress.modules:
            for idx, kp in enumerate(module.knowledge_points):
                if kp.id == matched[0]:
                    progress.current_module_id = module.id
                    progress.current_kp_index = idx
                    break
        service.save(progress)
    elif stage_applied:
        service.save(progress)

    return {
        "status": "applied" if updated or stage_applied else "path_found_no_kp_match",
        "mastery_path_id": path_id,
        "binding": "cognispheretutor.learning.service.LearningService",
        "matched_kp_ids": matched,
        "updated_kp_ids": updated,
        "passed": outcome if isinstance(outcome, bool) else None,
        "stage": stage_applied,
        "candidates": candidates,
        "source": source,
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

    learning_bind: dict[str, Any] | None = None
    mistake_sync: dict[str, Any] | None = None
    passed = result.get("passed")
    failed = passed is False or result.get("status") == "failed"

    if failed:
        # DT-P5 hook: failed sandboxes become mistake-memory candidates + Learning bind.
        mistake_sync = sync_mistake_memory(
            {
                "source": "sandbox",
                "mode": mode,
                "session_id": session_id,
                "slug": result.get("slug"),
                "domain": result.get("domain"),
                "path_id": result.get("path_id") or result.get("mastery_path_id"),
                "error": result.get("error") or result.get("stderr") or result.get("message"),
                "offline_simulated": result.get("offline_simulated") is True,
                "passed": False,
            }
        )
        learning_bind = (mistake_sync or {}).get("learning_store")
    elif passed is True:
        learning_bind = bind_runtime_feedback_to_learning(
            {
                "domain": result.get("domain"),
                "path_id": result.get("path_id") or result.get("mastery_path_id"),
                "slug": result.get("slug"),
                "skill_ids": list(result.get("skill_ids") or []),
                "passed": True,
            },
            passed=True,
            source="sandbox_pass",
        )

    return {
        "ok": True,
        "mode": mode,
        "phase": "DT-P4",
        "result": result,
        "artifact_path": str(state_dir),
        "mistake_memory": mistake_sync,
        "learning_store": learning_bind,
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

    # Bind only when outcome is explicit (or sandbox/error failure). Never mutate
    # mastery from a bare suggest-focus sync without pass/fail evidence.
    bind_payload = next((r for r in normalized if isinstance(r, dict)), {})
    explicit_passed = bind_payload.get("passed")
    if isinstance(explicit_passed, bool):
        bind_passed: bool | None = explicit_passed
    elif bind_payload.get("source") == "sandbox" or bind_payload.get("error"):
        bind_passed = False
    else:
        bind_passed = None
    learning_store = bind_runtime_feedback_to_learning(
        bind_payload,
        passed=bind_passed,
        source="mistake_memory",
    )

    return {
        "ok": True,
        "phase": "DT-P5",
        "status": "synced",
        "record_count": len(normalized),
        "suggest_tutor_focus": focus_suggestions,
        "artifact_path": str(out),
        "learning_store": learning_store,
        "product_binding": {
            "next_step": "Prefer suggested focus ids when recommending next practice item",
            "capability": "mastery_path",
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

    learning_store_note = bind_runtime_feedback_to_learning(
        evidence,
        passed=evidence.get("passed") if isinstance(evidence.get("passed"), bool) else None,
        source="mastery_update",
    )

    return {
        "ok": True,
        "phase": "DT-P5",
        "status": "applied",
        "evidence_keys": sorted(evidence.keys()),
        "artifact_path": str(out),
        "learning_store": learning_store_note,
        "product_binding": {
            "capability": "mastery_path",
            "notes": "Evidence cached; LearningService updated when path+KP match",
        },
    }


def require_authorized_or_simulated(result: dict[str, Any]) -> None:
    if result.get("offline_simulated") is True:
        return
    assert_sandbox_authorized()
