"""Verify Tutor can load the AWS Digital Twin demo pack (fail-closed).

Does not copy LP engines into Tutor. Expects:
- process env ``COGNISPHERE_LEARNING_PLUGINS_ROOT`` (or sibling monorepo), and
- ``cognisphere_plugins.aws_certification_twin`` importable (wheel or editable).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from cognispheretutor.integrations.cognisphere.aws_digital_twin_mastery_client import (
    aws_digital_twin_mastery_status,
)
from cognispheretutor.integrations.cognisphere.registry_client import PluginRegistryClient

CONTRACT_ID = "cognisphere.tutor.aws_dt_demo_pack.v1"
TWIN_DOMAIN = "aws_certification_twin"
TUTOR_CLI = "cognispheretutor cognisphere aws-twin-mastery"
LP_DEMO_DOC = (
    "CognisphereLearningPlugins/docs/DEMO_AWS_CLOUD_PRACTITIONER_TWIN.md"
    "#tutor-加载演示包wheel--不指向-monorepo-源码"
)


def verify_aws_dt_demo_pack(
    *,
    root: str | Path | None = None,
    client: PluginRegistryClient | None = None,
) -> dict[str, Any]:
    """Return a product envelope describing whether the demo pack is loadable."""
    registry = client or PluginRegistryClient(root)
    plugins_root = registry.resolve_plugins_root(root)
    env_name = "COGNISPHERE_LEARNING_PLUGINS_ROOT"
    env_set = bool((os.getenv(env_name) or "").strip())

    issues: list[str] = []
    if not plugins_root.exists():
        issues.append("plugins_root_missing")
    plugins_dir = plugins_root / "plugins"
    if plugins_root.exists() and not plugins_dir.is_dir():
        issues.append("plugins_dir_missing")
    twin_manifest = plugins_dir / TWIN_DOMAIN / "plugin_manifest.json"
    twin_manifest_present = twin_manifest.is_file()

    import_ok = False
    import_error: str | None = None
    try:
        registry.ensure_import_paths(domain=TWIN_DOMAIN, root=plugins_root)
        import cognisphere_plugins.aws_certification_twin.practitioner_mastery_path as mod  # type: ignore[import-not-found]

        import_ok = callable(getattr(mod, "run_aws_digital_twin_mastery", None))
        if not import_ok:
            issues.append("mastery_entrypoint_missing")
    except Exception as exc:  # noqa: BLE001 — surface as product issue
        import_error = str(exc)
        issues.append("twin_import_failed")

    status = aws_digital_twin_mastery_status(root=plugins_root, client=registry)
    status_ok = bool(status.get("ok"))
    if not status_ok:
        issues.append(str(status.get("error") or "twin_digital_twin_mastery_unavailable"))

    # Fail-closed on import + mastery readiness. Manifest is helpful for discovery
    # but wheel installs may still run when plugin_manifest stub is absent.
    ok = (
        import_ok
        and status_ok
        and "plugins_root_missing" not in issues
        and "twin_import_failed" not in issues
        and "mastery_entrypoint_missing" not in issues
    )

    return {
        "ok": ok,
        "contract": CONTRACT_ID,
        "domain": TWIN_DOMAIN,
        "plugins_root": str(plugins_root),
        "env": env_name,
        "env_set": env_set,
        "twin_manifest_present": twin_manifest_present,
        "import_ok": import_ok,
        "import_error": import_error,
        "mastery_status": {
            "ok": status.get("ok"),
            "status": status.get("status"),
            "runtime_mode": status.get("runtime_mode"),
            "error": status.get("error"),
        },
        "issues": [] if ok else issues,
        "tutor_cli": TUTOR_CLI,
        "live_aws_api": False,
        "use_llm": False,
        "sot_docs": LP_DEMO_DOC,
        "note": (
            "Install LP dist/aws_dt_tutor_demo wheels (or editable twin) "
            "and set COGNISPHERE_LEARNING_PLUGINS_ROOT"
            if not ok
            else "Demo pack loadable; run cognispheretutor cognisphere aws-twin-mastery"
        ),
    }
