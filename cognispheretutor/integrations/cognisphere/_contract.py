"""Load Cognisphere integration contracts from data manifests (not code SoT)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_MANIFESTS_DIR = Path(__file__).resolve().parent / "manifests"


def _load_json(name: str) -> dict[str, Any]:
    path = _MANIFESTS_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def load_plugin_contract() -> dict[str, Any]:
    return _load_json("plugin_contract.json")


@lru_cache(maxsize=4)
def load_error_code_catalog() -> dict[str, Any]:
    return _load_json("error_codes.json")


@lru_cache(maxsize=4)
def load_learning_loop_mapping() -> dict[str, Any]:
    contract = load_plugin_contract()
    name = str(contract.get("learning_loop_mapping_manifest") or "learning_loop_mapping.json")
    return _load_json(name)


@lru_cache(maxsize=4)
def load_trusted_context_contract() -> dict[str, Any]:
    contract = load_plugin_contract()
    name = str(
        contract.get("trusted_context_contract_manifest") or "trusted_context_contract.json"
    )
    return _load_json(name)


@lru_cache(maxsize=4)
def load_runtime_adapters() -> dict[str, Any]:
    contract = load_plugin_contract()
    name = str(contract.get("runtime_adapters_manifest") or "runtime_adapters.json")
    return _load_json(name)


def contract_path() -> Path:
    return _MANIFESTS_DIR / "plugin_contract.json"


def manifests_dir() -> Path:
    return _MANIFESTS_DIR
