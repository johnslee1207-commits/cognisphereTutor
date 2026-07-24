"""DT-P3 — Cognisphere trusted-context package client (fail-closed live path)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cognispheretutor.integrations.cognisphere._contract import load_trusted_context_contract
from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError, format_issue


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def production_candidate_ready(*, env: dict[str, str] | None = None) -> bool:
    contract = load_trusted_context_contract()
    env_name = str(contract.get("production_candidate_env") or "")
    expected = str(contract.get("production_candidate_ready_value") or "1")
    source = env if env is not None else os.environ
    if not env_name:
        return False
    return (source.get(env_name) or "").strip() == expected


def kit_configured(*, env: dict[str, str] | None = None) -> bool:
    contract = load_trusted_context_contract()
    source = env if env is not None else os.environ
    base = (source.get(str(contract.get("kit_base_url_env") or "")) or "").strip()
    return bool(base)


def resolve_trusted_context_cache_dir(
    *,
    project_id: str | None = None,
    cache_dir: str | Path | None = None,
) -> Path:
    contract = load_trusted_context_contract()
    if cache_dir is not None:
        base = Path(cache_dir)
    else:
        try:
            from cognispheretutor.services.path_service import get_path_service

            rel = str(contract.get("cache_relative_workspace_path") or "cognisphere_trusted_context")
            base = get_path_service().get_workspace_dir() / rel
        except Exception:  # noqa: BLE001
            base = Path.cwd() / "data" / "user" / "workspace" / "cognisphere_trusted_context"
    if project_id:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in project_id)
        return (base / safe).resolve()
    return base.resolve()


def validate_trusted_context_package(package: dict[str, Any]) -> dict[str, Any]:
    contract = load_trusted_context_contract()
    issues: list[str] = []
    for key in list(contract.get("required_package_keys") or []):
        if key not in package:
            issues.append(format_issue("missing_top_level", key))

    safety = package.get("safety") if isinstance(package.get("safety"), dict) else {}
    for key in list(contract.get("required_safety_keys") or []):
        if key not in safety:
            issues.append(format_issue("missing_safety", key))

    sot = safety.get("source_of_truth")
    allowed = set(contract.get("allowed_source_of_truth") or [])
    if sot is not None and sot not in allowed:
        issues.append("unexpected_source_of_truth")

    if safety.get("no_answer_keys") is False:
        issues.append(format_issue("missing_safety", "no_answer_keys"))

    return {
        "ok": not issues,
        "issues": issues,
        "phase": "DT-P3",
        "contract_id": contract.get("contract_id"),
        "package_keys": sorted(package.keys()),
        "project_id": package.get("project_id"),
        "payload_kind": package.get("payload_kind"),
    }


def fetch_trusted_context_package(
    project_id: str,
    payload_kind: str,
    *,
    readiness: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
    timeout_s: float = 15.0,
) -> dict[str, Any]:
    """Fetch project package from Cognisphere kit when configured; else fail-closed."""
    contract = load_trusted_context_contract()
    source = env if env is not None else os.environ

    if readiness is not None and readiness.get("blocked"):
        raise CognisphereIntegrationError(
            "production_candidate_blocked",
            details={"project_id": project_id, "payload_kind": payload_kind, "readiness": readiness},
        )

    if not production_candidate_ready(env=source) and (
        (source.get(str(contract.get("require_write_api_key_env") or "")) or "").strip() in {"1", "true", "yes"}
    ):
        # Explicit production write gate without candidate readiness.
        raise CognisphereIntegrationError(
            "production_candidate_blocked",
            details={"project_id": project_id, "payload_kind": payload_kind},
        )

    base = (source.get(str(contract.get("kit_base_url_env") or "")) or "").strip().rstrip("/")
    if not base:
        blocker = dict(contract.get("blocker") or {})
        raise CognisphereIntegrationError(
            str(blocker.get("code") or "trusted_context_kit_unavailable"),
            message=str(blocker.get("meaning") or "Trusted-context kit not configured"),
            details={
                "project_id": project_id,
                "payload_kind": payload_kind,
                "phase": "DT-P3",
                "env": contract.get("kit_base_url_env"),
                "handling": blocker.get("handling"),
                "offline_path": "Pass a local package dict to import_trusted_context_into_workspace",
            },
        )

    url = f"{base}/trusted-context/packages/{project_id}?payload_kind={payload_kind}"
    headers = {"Accept": "application/json"}
    api_key = (source.get(str(contract.get("api_key_env") or "")) or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 — operator-configured URL
            raw = resp.read().decode("utf-8")
            package = json.loads(raw)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        raise CognisphereIntegrationError(
            "trusted_context_kit_unavailable",
            message=str(exc),
            details={"project_id": project_id, "payload_kind": payload_kind, "url": url},
        ) from exc

    if not isinstance(package, dict):
        raise CognisphereIntegrationError(
            "trusted_context_invalid",
            details={"project_id": project_id, "type": type(package).__name__},
        )
    package.setdefault("project_id", project_id)
    package.setdefault("payload_kind", payload_kind)
    report = validate_trusted_context_package(package)
    if not report["ok"]:
        raise CognisphereIntegrationError(
            "trusted_context_invalid",
            details=report,
        )
    return package


def import_trusted_context_into_workspace(
    package: dict[str, Any],
    *,
    persist: bool = True,
    cache_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Validate and cache an offline or fetched trusted-context package."""
    report = validate_trusted_context_package(package)
    if not report["ok"]:
        raise CognisphereIntegrationError(
            "trusted_context_invalid",
            details=report,
        )

    imported_at = _utc_now()
    receipt: dict[str, Any] = {
        "ok": True,
        "status": "imported",
        "phase": "DT-P3",
        "validation": report,
        "receipt": {
            "project_id": package.get("project_id"),
            "payload_kind": package.get("payload_kind"),
            "exported_at": package.get("exported_at"),
            "imported_at": imported_at,
            "source_of_truth": (package.get("safety") or {}).get("source_of_truth"),
        },
    }

    if persist:
        target = resolve_trusted_context_cache_dir(
            project_id=str(package.get("project_id") or "unknown"),
            cache_dir=cache_dir,
        )
        target.mkdir(parents=True, exist_ok=True)
        (target / "package.json").write_text(
            json.dumps(package, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (target / "import_receipt.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        receipt["artifact_path"] = str(target)
        receipt["receipt"]["artifact_path"] = str(target)

    return receipt
