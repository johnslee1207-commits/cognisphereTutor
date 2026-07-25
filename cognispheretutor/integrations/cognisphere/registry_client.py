"""Plugin Registry Client — discover and load Cognisphere Learning Plugins."""

from __future__ import annotations

from importlib import import_module
import json
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

from cognispheretutor.integrations.cognisphere._contract import load_plugin_contract
from cognispheretutor.integrations.cognisphere.error_codes import (
    CognisphereIntegrationError,
    format_issue,
)


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


class PluginRegistryClient:
    """Discover domain packs under ``COGNISPHERE_LEARNING_PLUGINS_ROOT``."""

    def __init__(self, plugins_root: str | Path | None = None) -> None:
        self._explicit_root = Path(plugins_root).resolve() if plugins_root is not None else None
        self._contract = load_plugin_contract()

    def resolve_plugins_root(self, explicit: str | Path | None = None) -> Path:
        if explicit is not None:
            return Path(explicit).resolve()
        if self._explicit_root is not None:
            return self._explicit_root
        env_name = str(self._contract["plugins_root_env"])
        env = (os.getenv(env_name) or "").strip()
        if env:
            return Path(env).resolve()
        sibling_name = str(self._contract["default_sibling_name"])
        registry_rel = str(self._contract["install_registry_relative_path"])

        def _is_plugins_root(path: Path) -> bool:
            return (path / "plugins").is_dir() and (path / registry_rel).exists()

        # Prefer sibling of the cognisphereTutor checkout
        # (…/Projects/cognisphereTutor → …/CognisphereLearningPlugins).
        here = Path(__file__).resolve()
        for parent in here.parents:
            if parent.name in {"cognisphereTutor", "DeepTutor"}:
                candidate = parent.parent / sibling_name
                if _is_plugins_root(candidate):
                    return candidate.resolve()
            candidate = parent / sibling_name
            if _is_plugins_root(candidate):
                return candidate.resolve()
            if parent.name == sibling_name and _is_plugins_root(parent):
                return parent.resolve()
        sibling = Path.cwd().parent / sibling_name
        if _is_plugins_root(sibling):
            return sibling.resolve()
        return Path.cwd().resolve()

    def load_install_registry(self, root: str | Path | None = None) -> dict[str, Any]:
        plugins_root = self.resolve_plugins_root(root)
        rel = str(self._contract["install_registry_relative_path"])
        path = plugins_root / rel
        if not path.exists():
            return {
                "registry_id": "cognisphere.learning_plugins.install_registry.v1",
                "plugins_root": str(plugins_root),
                "plugins": [],
                "issues": ["install_registry_missing"],
            }
        data = json.loads(path.read_text(encoding="utf-8"))
        data["plugins_root"] = str(plugins_root)
        return data

    def list_plugins(self, root: str | Path | None = None) -> dict[str, Any]:
        plugins_root = self.resolve_plugins_root(root)
        issues: list[str] = []
        if not plugins_root.exists():
            return {
                "ok": False,
                "plugins_root": str(plugins_root),
                "plugin_count": 0,
                "plugins": [],
                "issues": ["plugins_root_missing"],
                "registry": {},
                "env": self._contract["plugins_root_env"],
            }

        registry = self.load_install_registry(plugins_root)
        if "install_registry_missing" in list(registry.get("issues") or []):
            issues.append("install_registry_missing")
        tutor_pack_profile = _read_json_if_exists(
            plugins_root / "manifests" / "ops" / "tutor_pack_profile.json"
        )
        distribution_catalog = _read_json_if_exists(
            plugins_root / "manifests" / "ops" / "domain_distribution_catalog.json"
        )
        distributions: dict[str, dict[str, Any]] = {
            str(key): value
            for key, value in dict(distribution_catalog.get("domains") or {}).items()
            if isinstance(value, dict)
        }
        for package in list(distribution_catalog.get("packages") or []):
            if not isinstance(package, dict):
                continue
            domain = str(package.get("domain") or package.get("unit_id") or "").strip()
            if domain and domain not in distributions:
                distributions[domain] = package

        plugins_dir = plugins_root / "plugins"
        if not plugins_dir.is_dir():
            return {
                "ok": False,
                "plugins_root": str(plugins_root),
                "plugin_count": 0,
                "plugins": [],
                "issues": issues + ["plugins_dir_missing"],
                "registry": registry,
                "env": self._contract["plugins_root_env"],
            }

        registry_paths = {
            item.get("domain"): item.get("relative_path")
            for item in list(registry.get("plugins") or [])
            if isinstance(item, dict)
        }
        found: list[dict[str, Any]] = []
        domain_dirs = sorted(
            [
                p
                for p in plugins_dir.iterdir()
                if p.is_dir() and not p.name.startswith("_") and p.name != "_shared"
            ]
        )
        for domain_dir in domain_dirs:
            manifest_path = domain_dir / "plugin_manifest.json"
            if not manifest_path.exists():
                issues.append(format_issue("missing_plugin_manifest", domain_dir.name))
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                issues.append(f"invalid_json:{domain_dir.name}:{exc}")
                continue
            validation = self.validate_plugin_manifest(manifest)
            entry = {
                "domain": domain_dir.name,
                "path": str(domain_dir),
                "manifest_path": str(manifest_path),
                "manifest": manifest,
                "validation": validation,
                "in_registry": domain_dir.name in registry_paths,
                "lifecycle": self._lifecycle_for_domain(domain_dir.name, registry),
                "distribution": distributions.get(domain_dir.name) or {},
                "tutor_pack": {
                    **dict(tutor_pack_profile.get("defaults") or {}),
                    **_read_json_if_exists(domain_dir / "tutor_pack_profile.json"),
                },
            }
            found.append(entry)
            if not validation.get("ok"):
                issues.extend(f"{domain_dir.name}:{i}" for i in validation.get("issues") or [])

        return {
            "ok": not issues,
            "plugins_root": str(plugins_root),
            "plugin_count": len(found),
            "plugins": found,
            "issues": issues,
            "registry": registry,
            "tutor_pack": tutor_pack_profile,
            "distribution_catalog": distribution_catalog,
            "env": self._contract["plugins_root_env"],
        }

    def get_plugin(self, domain: str, root: str | Path | None = None) -> dict[str, Any]:
        discovery = self.list_plugins(root)
        for item in discovery.get("plugins") or []:
            if item.get("domain") == domain:
                return {
                    "ok": True,
                    "plugin": item,
                    "plugins_root": discovery.get("plugins_root"),
                    "issues": list(discovery.get("issues") or []),
                }
        raise CognisphereIntegrationError(
            "domain_not_found",
            details={"domain": domain, "plugins_root": discovery.get("plugins_root")},
        )

    def ensure_import_paths(self, domain: str | None = None, root: str | Path | None = None) -> list[str]:
        plugins_root = self.resolve_plugins_root(root)
        added: list[str] = []
        candidates = [str(self._contract["sdk_import_root_relative_path"])]
        if domain:
            template = str(self._contract["plugin_src_relative_template"])
            candidates.append(template.format(domain=domain))
        for rel in candidates:
            path = plugins_root / rel
            if path.is_dir():
                text = str(path)
                # Keep the active domain src first so sibling packs that share a
                # top-level package name (e.g. fixture_plugins) resolve correctly.
                if text in sys.path:
                    sys.path.remove(text)
                sys.path.insert(0, text)
                added.append(text)
        if domain:
            self._purge_colliding_entrypoint_modules(plugins_root, domain)
        return added

    def _purge_colliding_entrypoint_modules(self, plugins_root: Path, domain: str) -> None:
        """Drop cached top-level packs that may have been imported from another domain src."""
        template = str(self._contract["plugin_src_relative_template"])
        active = (plugins_root / template.format(domain=domain)).resolve()
        doomed: list[str] = []
        for name, mod in list(sys.modules.items()):
            if not (
                name == "fixture_plugins"
                or name.startswith("fixture_plugins.")
                or name == "cognisphere_plugins"
                or name.startswith("cognisphere_plugins.")
            ):
                continue
            mod_file = getattr(mod, "__file__", None)
            if not mod_file:
                # Namespace / partially initialized — safe to drop.
                doomed.append(name)
                continue
            try:
                resolved = Path(mod_file).resolve()
            except OSError:
                doomed.append(name)
                continue
            if active not in resolved.parents and resolved != active:
                doomed.append(name)
        for name in doomed:
            sys.modules.pop(name, None)

    def load_deeptutor_entrypoint(self, domain: str, root: str | Path | None = None) -> ModuleType:
        record = self.get_plugin(domain, root)
        manifest = (record.get("plugin") or {}).get("manifest") or {}
        module_name = str(manifest.get("deeptutor_entrypoint") or "").strip()
        if not module_name:
            raise CognisphereIntegrationError(
                "missing_deeptutor_func",
                message="deeptutor_entrypoint missing from manifest",
                details={"domain": domain},
            )
        self.ensure_import_paths(domain, root=record.get("plugins_root"))
        try:
            return import_module(module_name)
        except Exception as exc:  # noqa: BLE001 — surface as product error
            raise CognisphereIntegrationError(
                "entrypoint_import_failed",
                message=str(exc),
                details={"domain": domain, "module": module_name},
            ) from exc

    def load_cognisphere_entrypoint(self, domain: str, root: str | Path | None = None) -> ModuleType:
        record = self.get_plugin(domain, root)
        manifest = (record.get("plugin") or {}).get("manifest") or {}
        module_name = str(manifest.get("cognisphere_entrypoint") or "").strip()
        if not module_name:
            raise CognisphereIntegrationError(
                "entrypoint_import_failed",
                message="cognisphere_entrypoint missing from manifest",
                details={"domain": domain},
            )
        self.ensure_import_paths(domain, root=record.get("plugins_root"))
        try:
            return import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            raise CognisphereIntegrationError(
                "entrypoint_import_failed",
                message=str(exc),
                details={"domain": domain, "module": module_name},
            ) from exc

    def validate_plugin_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]:
        issues: list[str] = []
        for key in list(self._contract["required_manifest_keys"]):
            if not manifest.get(key):
                issues.append(f"missing:{key}")
        known = set(self._contract["known_capabilities"])
        for cap in list(manifest.get("capabilities") or []):
            if cap not in known:
                issues.append(format_issue("unknown_capability", str(cap)))
        return {
            "ok": not issues,
            "issues": issues,
            "schema_id": self._contract["schema_id"],
            "plugin_id": manifest.get("plugin_id"),
            "domain": manifest.get("domain"),
        }

    def validate_adapter(self, domain: str, root: str | Path | None = None) -> dict[str, Any]:
        """Call plugin ``validate_adapter`` and normalize the product envelope."""
        issues: list[str] = []
        try:
            record = self.get_plugin(domain, root)
        except CognisphereIntegrationError as exc:
            return {
                "ok": False,
                "domain": domain,
                "issues": [exc.code],
                "handoff_contract": {"ok": False, "issues": [exc.code]},
            }

        plugin = record.get("plugin") or {}
        manifest_validation = plugin.get("validation") or {}
        if not manifest_validation.get("ok"):
            issues.extend(manifest_validation.get("issues") or [])

        try:
            mod = self.load_deeptutor_entrypoint(domain, root=record.get("plugins_root"))
        except CognisphereIntegrationError as exc:
            issues.append(format_issue("missing_deeptutor_func", "import"))
            issues.append(str(exc))
            return {
                "ok": False,
                "domain": domain,
                "plugin_id": (plugin.get("manifest") or {}).get("plugin_id"),
                "issues": issues,
                "handoff_contract": {"ok": False, "issues": issues},
            }

        for name in list(self._contract["required_deeptutor_funcs"]):
            if not callable(getattr(mod, name, None)):
                issues.append(format_issue("missing_deeptutor_func", name))

        legacy_adapter: dict[str, Any] | None = None
        handoff_contract: dict[str, Any] = {"ok": False, "issues": ["validate_adapter_not_callable"]}
        if callable(getattr(mod, "validate_adapter", None)):
            try:
                raw = mod.validate_adapter()
                if isinstance(raw, dict):
                    legacy_adapter = raw.get("legacy_adapter") if "legacy_adapter" in raw else raw.get("legacy")
                    handoff_contract = (
                        raw.get("handoff_contract")
                        or raw.get("validation")
                        or {
                            "ok": bool(raw.get("ok", True)),
                            "issues": list(raw.get("issues") or []),
                            "contract": raw.get("contract"),
                        }
                    )
                    if raw.get("issues"):
                        issues.extend(str(i) for i in raw["issues"])
                    if raw.get("ok") is False:
                        issues.append("validate_adapter_ok_false")
                else:
                    handoff_contract = {"ok": False, "issues": ["validate_adapter_non_dict"]}
                    issues.append("validate_adapter_non_dict")
            except Exception as exc:  # noqa: BLE001
                handoff_contract = {"ok": False, "issues": [f"validate_adapter_error:{exc}"]}
                issues.append(f"validate_adapter_error:{exc}")

        ok = not issues and bool(handoff_contract.get("ok", False))
        return {
            "ok": ok,
            "domain": domain,
            "plugin_id": (plugin.get("manifest") or {}).get("plugin_id"),
            "legacy_adapter": legacy_adapter,
            "handoff_contract": handoff_contract,
            "issues": issues,
            "production_ready": ok,
        }

    @staticmethod
    def _lifecycle_for_domain(domain: str, registry: dict[str, Any]) -> str | None:
        for item in registry.get("plugins") or []:
            if isinstance(item, dict) and item.get("domain") == domain:
                return item.get("lifecycle")
        return None


_DEFAULT_CLIENT = PluginRegistryClient()


def resolve_plugins_root(explicit: str | Path | None = None) -> Path:
    return _DEFAULT_CLIENT.resolve_plugins_root(explicit)


def list_plugins(root: str | Path | None = None) -> dict[str, Any]:
    return _DEFAULT_CLIENT.list_plugins(root)


def get_plugin(domain: str, root: str | Path | None = None) -> dict[str, Any]:
    return _DEFAULT_CLIENT.get_plugin(domain, root)


def load_deeptutor_entrypoint(domain: str, root: str | Path | None = None) -> ModuleType:
    return _DEFAULT_CLIENT.load_deeptutor_entrypoint(domain, root)


def load_cognisphere_entrypoint(domain: str, root: str | Path | None = None) -> ModuleType:
    return _DEFAULT_CLIENT.load_cognisphere_entrypoint(domain, root)


def validate_adapter(domain: str, root: str | Path | None = None) -> dict[str, Any]:
    return _DEFAULT_CLIENT.validate_adapter(domain, root)
