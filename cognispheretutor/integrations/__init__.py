"""Cognisphere Learning Plugins integration (cognisphereTutor product side).

Thin DT-P1…P6 client: discover / negotiate / validate / import /
trusted-context / runtime callbacks + offline bridge / compose.
Domain learning logic stays in plugins; Tutor only orchestrates.
"""

from __future__ import annotations

from cognispheretutor.integrations.cognisphere.capability_negotiator import (
    negotiate,
    query_cross_domain,
)
from cognispheretutor.integrations.cognisphere.registry_client import (
    PluginRegistryClient,
    get_plugin,
    list_plugins,
    load_cognisphere_entrypoint,
    load_deeptutor_entrypoint,
    resolve_plugins_root,
    validate_adapter,
)
from cognispheretutor.integrations.cognisphere.security_gates import (
    assert_sandbox_authorized,
    is_sandbox_authorized,
)

__all__ = [
    "PluginRegistryClient",
    "assert_sandbox_authorized",
    "get_plugin",
    "is_sandbox_authorized",
    "list_plugins",
    "load_cognisphere_entrypoint",
    "load_deeptutor_entrypoint",
    "negotiate",
    "query_cross_domain",
    "resolve_plugins_root",
    "validate_adapter",
]
