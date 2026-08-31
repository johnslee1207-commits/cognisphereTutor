from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


class AetherInfraTwinError(RuntimeError):
    """Raised when the local AI Infra Twin lab engine cannot be reached."""


def _default_base_url() -> str:
    return os.environ.get("AETHERINFRA_TWIN_BASE_URL", "http://127.0.0.1:8765").rstrip("/")


@dataclass(frozen=True)
class AetherInfraTwinClient:
    base_url: str
    timeout: float = 8.0

    @property
    def embed_base_url(self) -> str:
        return os.environ.get("AETHERINFRA_TWIN_EMBED_URL", self.base_url).rstrip("/")

    def embed_url(self, lab_id: str | None = None) -> str:
        if lab_id:
            return f"{self.embed_base_url}/embed/{parse.quote(lab_id, safe='')}"
        return f"{self.embed_base_url}/"

    def get_json(self, path: str) -> dict[str, Any] | list[dict[str, Any]]:
        return self._request_json("GET", path)

    def post_json(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self._request_json("POST", path, payload or {})
        if not isinstance(result, dict):
            raise AetherInfraTwinError("AI Infra Twin returned a non-object response")
        return result

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        url = f"{self.base_url}{path if path.startswith('/') else '/' + path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except error.URLError as exc:
            raise AetherInfraTwinError(str(exc)) from exc
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise AetherInfraTwinError("AI Infra Twin returned invalid JSON") from exc
        if not isinstance(parsed, (dict, list)):
            raise AetherInfraTwinError("AI Infra Twin returned an unsupported JSON shape")
        return parsed


def default_client() -> AetherInfraTwinClient:
    return AetherInfraTwinClient(_default_base_url())
