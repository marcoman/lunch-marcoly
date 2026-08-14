"""Parse and format LaunchDarkly: inventory comments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

LD_MARKER = "LaunchDarkly:"

# LaunchDarkly: flag key=foo name="Bar" kind=boolean
_LINE_RE = re.compile(
    r"LaunchDarkly:\s+(?P<rtype>flag|ai-config)\s+(?P<body>.+)$"
)
_TOKEN_RE = re.compile(
    r"""(?P<k>[a-zA-Z_][\w-]*)=(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|(?P<bare>\S+))"""
)


@dataclass
class ParsedComment:
    resource_type: str  # flag | ai-config
    key: str
    name: str = ""
    kind: str = ""
    mode: str = ""


def parse_ld_comment_line(line: str) -> ParsedComment | None:
    if LD_MARKER not in line:
        return None
    # Strip language comment prefixes
    stripped = line.strip()
    for prefix in ("#", "//", "*", "/*"):
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix) :].strip()
    m = _LINE_RE.search(stripped)
    if not m:
        return None
    fields: dict[str, str] = {}
    for tm in _TOKEN_RE.finditer(m.group("body")):
        val = tm.group("dq") if tm.group("dq") is not None else (
            tm.group("sq") if tm.group("sq") is not None else tm.group("bare")
        )
        fields[tm.group("k")] = val or ""
    key = fields.get("key", "")
    if not key:
        return None
    return ParsedComment(
        resource_type=m.group("rtype"),
        key=key,
        name=fields.get("name", ""),
        kind=fields.get("kind", ""),
        mode=fields.get("mode", ""),
    )


def comment_has_key(lines: list[str], key: str, *, around: int, window: int = 4) -> bool:
    """True if LaunchDarkly: comment with key= is within window lines above around."""
    start = max(0, around - window)
    for i in range(start, around):
        parsed = parse_ld_comment_line(lines[i])
        if parsed and parsed.key == key:
            return True
    return False


def _quote_name(name: str) -> str:
    return f'"{name.replace(chr(34), "")}"'


def format_flag_comment(
    *,
    key: str,
    name: str = "",
    kind: str = "",
    project_key: str,
    api_host: str = "https://app.launchdarkly.com",
    style: str,  # hash | slash
) -> list[str]:
    parts = [f"flag key={key}"]
    if name:
        parts.append(f"name={_quote_name(name)}")
    if kind:
        parts.append(f"kind={kind}")
    prefix = "#" if style == "hash" else "//"
    host = api_host.rstrip("/")
    url = f"{host}/projects/{quote(project_key)}/features/{quote(key)}"
    return [f"{prefix} {LD_MARKER} {' '.join(parts)}", f"{prefix} {url}"]


def format_ai_config_comment(
    *,
    key: str,
    name: str = "",
    mode: str = "",
    project_key: str,
    api_host: str = "https://app.launchdarkly.com",
    style: str,
) -> list[str]:
    parts = [f"ai-config key={key}"]
    if name:
        parts.append(f"name={_quote_name(name)}")
    if mode:
        parts.append(f"mode={mode}")
    prefix = "#" if style == "hash" else "//"
    host = api_host.rstrip("/")
    url = f"{host}/projects/{quote(project_key)}/ai-configs/{quote(key)}"
    return [f"{prefix} {LD_MARKER} {' '.join(parts)}", f"{prefix} {url}"]


def comment_style_for_path(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".py"):
        return "hash"
    return "slash"  # js, java


def project_settings(project: dict[str, Any]) -> tuple[str, str]:
    api = project.get("api") if isinstance(project.get("api"), dict) else {}
    host = str(api.get("host") or "https://app.launchdarkly.com")
    project_key = str(project.get("project_key") or "default")
    return project_key, host
