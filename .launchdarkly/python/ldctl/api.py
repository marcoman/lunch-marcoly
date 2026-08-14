"""Minimal LaunchDarkly REST client for inventory status checks."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class ApiConfig:
    host: str
    token: str
    version: str
    agent_control_version: str
    project_key: str
    environment_key: str


def api_config_from_env(project: dict[str, Any]) -> ApiConfig:
    token = os.environ.get("LD_API_ACCESS_TOKEN") or os.environ.get("LD_ACCESS_TOKEN")
    if not token:
        raise SystemExit(
            "error: LD_API_ACCESS_TOKEN is required for status/report "
            "(see .launchdarkly/README.md)"
        )

    api = project.get("api") if isinstance(project.get("api"), dict) else {}
    host = (
        os.environ.get("LD_API_HOST")
        or api.get("host")
        or "https://app.launchdarkly.com"
    ).rstrip("/")
    project_key = os.environ.get("LD_PROJECT_KEY") or project.get("project_key")
    environment_key = os.environ.get("LD_ENVIRONMENT_KEY") or project.get("environment_key")
    if not project_key:
        raise SystemExit("error: LD_PROJECT_KEY or project.yaml project_key is required")
    if not environment_key:
        raise SystemExit("error: LD_ENVIRONMENT_KEY or project.yaml environment_key is required")

    return ApiConfig(
        host=host,
        token=token,
        version=str(api.get("version") or os.environ.get("LD_API_VERSION") or "20240415"),
        agent_control_version=str(api.get("agent_control_version") or "beta"),
        project_key=str(project_key),
        environment_key=str(environment_key),
    )


@dataclass
class ApiResult:
    ok: bool
    status: int
    body: Any | None
    error: str | None = None


class LdClient:
    def __init__(self, cfg: ApiConfig) -> None:
        self.cfg = cfg

    def _request(self, method: str, path: str, *, api_version: str | None = None) -> ApiResult:
        url = f"{self.cfg.host}/api/v2{path}"
        req = urllib.request.Request(url, method=method)
        req.add_header("Authorization", self.cfg.token)
        req.add_header("LD-API-Version", api_version or self.cfg.version)
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                body = json.loads(raw) if raw else None
                return ApiResult(ok=True, status=resp.status, body=body)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                body = raw
            msg = None
            if isinstance(body, dict):
                msg = body.get("message") or body.get("error")
            return ApiResult(ok=False, status=exc.code, body=body, error=msg or raw or str(exc))
        except urllib.error.URLError as exc:
            return ApiResult(ok=False, status=0, body=None, error=str(exc.reason))

    def get_flag(self, key: str) -> ApiResult:
        return self._request("GET", f"/flags/{self.cfg.project_key}/{key}")

    def get_metric(self, key: str) -> ApiResult:
        return self._request("GET", f"/metrics/{self.cfg.project_key}/{key}")

    def get_ai_config(self, key: str) -> ApiResult:
        return self._request(
            "GET",
            f"/projects/{self.cfg.project_key}/ai-configs/{key}",
            api_version=self.cfg.agent_control_version,
        )

    def get_ai_config_targeting(self, key: str) -> ApiResult:
        env = self.cfg.environment_key
        return self._request(
            "GET",
            f"/projects/{self.cfg.project_key}/ai-configs/{key}/targeting?env={env}",
            api_version=self.cfg.agent_control_version,
        )

    def get_model_config(self, key: str) -> ApiResult:
        return self._request(
            "GET",
            f"/projects/{self.cfg.project_key}/ai-configs/model-configs/{key}",
            api_version=self.cfg.agent_control_version,
        )
