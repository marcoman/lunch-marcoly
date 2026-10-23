#!/usr/bin/env python3
"""Serve the tenant datacenter lab and evaluate one context per presence."""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import ldclient
from ldclient import Context
from ldclient.config import Config
from ldclient.client import LDClient

EXAMPLE = Path(__file__).resolve().parent.parent
WEB = Path(__file__).resolve().parent
sys.path.insert(0, str(EXAMPLE))

from flags import FLAG_BORDER, FLAG_FILL, SEGMENTS, hue  # noqa: E402
from tenants import build_layout  # noqa: E402

PORT = int(os.environ.get("PORT", "8080"))
EXAMPLE_CUSTOM = EXAMPLE / "customizations.json.example"
LOCAL_CUSTOM = EXAMPLE / "customizations.json"
_ld_client: LDClient | None = None


def init_launchdarkly() -> None:
    """Start one server SDK client for every tenant evaluation.

    LaunchDarkly: server-side Python SDK
    https://launchdarkly.com/docs/sdk/server-side/python
    """
    global _ld_client
    sdk_key = os.environ.get("LD_SDK_KEY")
    if not sdk_key:
        print("Warning: LD_SDK_KEY not set — flags fall back to none and false.", flush=True)
        return
    ldclient.set_config(Config(sdk_key))
    _ld_client = ldclient.get()
    if not _ld_client.is_initialized():
        print("Warning: LaunchDarkly SDK did not initialize — flags fall back.", flush=True)


def tenant_context(box: dict[str, Any]) -> Context:
    """Build the context for one presence.

    LaunchDarkly: contexts — https://launchdarkly.com/docs/home/flags/contexts
    """
    return (
        Context.builder(box["name"])
        .kind("tenant")
        .set("size", box["size"])
        .set("sizeClass", box["sizeClass"])
        .set("version", box["version"])
        .set("span", box["span"])
        .set("datacenter", box["datacenter"])
        .build()
    )


def _reason_kind(detail: Any) -> str:
    reason = getattr(detail, "reason", None)
    if isinstance(reason, dict):
        return str(reason.get("kind", "UNKNOWN"))
    kind = getattr(reason, "kind", None)
    return str(kind or "UNKNOWN")


def _variation(client: LDClient, key: str, context: Context, default: Any) -> tuple[Any, str]:
    """Evaluate one flag. The last argument is the safe default.

    LaunchDarkly: evaluating flags — https://launchdarkly.com/docs/sdk/features/evaluation-reasons
    """
    detail = client.variation_detail(key, context, default)
    return detail.value, _reason_kind(detail)


def evaluate_floor(layout: dict[str, Any]) -> None:
    """Evaluate both flags for every presence and paint each box from its size class."""
    boxes = [box for datacenter in layout["datacenters"] for box in datacenter["customers"]]
    client = _ld_client if _ld_client is not None and _ld_client.is_initialized() else None
    border_values: list[str] = []
    fill_values: list[bool] = []
    border_reason = "fallback"
    fill_reason = "fallback"
    for box in boxes:
        if client is None:
            palette, fill = "none", False
        else:
            context = tenant_context(box)
            # Multivariate string. One palette for the whole floor.
            # https://launchdarkly.com/docs/home/flags/variations
            palette_raw, border_reason = _variation(client, FLAG_BORDER, context, "none")
            palette = str(palette_raw) if isinstance(palette_raw, str) else "none"
            # Boolean fill. With no hue, the box stays empty.
            # https://launchdarkly.com/docs/home/flags/boolean
            fill_raw, fill_reason = _variation(client, FLAG_FILL, context, False)
            fill = bool(fill_raw)
        color = hue(palette, box["sizeClass"])
        box["color"] = color
        box["fill"] = bool(color) and fill
        border_values.append(palette)
        fill_values.append(fill)
    layout["sdkConnected"] = client is not None
    layout["flags"] = [
        _flag_summary(FLAG_BORDER, "Border palette", border_values, border_reason, len(boxes)),
        _flag_summary(FLAG_FILL, "Box fill", fill_values, fill_reason, len(boxes)),
    ]
    layout["segments"] = SEGMENTS


def _flag_summary(key: str, name: str, values: list[Any], reason: str, count: int) -> dict[str, Any]:
    unique = list(dict.fromkeys(values))
    return {
        "key": key,
        "name": name,
        "value": unique[0] if len(unique) == 1 else None,
        "values": [str(value) for value in unique],
        "uniform": len(unique) == 1,
        "reason": reason,
        "evaluations": count,
    }


def load_customization() -> dict[str, str]:
    """Read company name and logo. A missing local file uses the example."""
    data = json.loads(EXAMPLE_CUSTOM.read_text())
    if LOCAL_CUSTOM.is_file():
        override = json.loads(LOCAL_CUSTOM.read_text())
        if isinstance(override, dict):
            data.update(override)
    name = str(data.get("companyName") or "Example Hosting").strip()
    logo = str(data.get("logo") or "logo.svg").strip()
    return {"companyName": name, "logo": logo}


def brand_file(name: str) -> Path | None:
    """Resolve a logo that sits directly in the example directory."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    path = (EXAMPLE / name).resolve()
    if path.parent != EXAMPLE.resolve() or not path.is_file():
        return None
    return path


class Handler(BaseHTTPRequestHandler):
    """Serve the page, the generated layout, and the company logo."""

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/layout":
            custom = load_customization()
            logo = brand_file(custom["logo"]) or brand_file("logo.svg")
            body = build_layout()
            evaluate_floor(body)
            body["companyName"] = custom["companyName"]
            body["logoUrl"] = f"/brand/{logo.name}" if logo else ""
            self._json(body)
            return
        if path.startswith("/brand/"):
            self._brand(unquote(path.removeprefix("/brand/")))
            return
        if path in ("/", "/index.html"):
            self._file(WEB / "index.html", "text/html; charset=utf-8")
            return
        self.send_error(404)

    def _brand(self, name: str) -> None:
        path = brand_file(name)
        if path is None:
            self.send_error(404)
            return
        kind = "image/svg+xml" if path.suffix == ".svg" else "application/octet-stream"
        self._file(path, kind)

    def _file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    init_launchdarkly()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"21-tenant-datacenters running at http://127.0.0.1:{PORT}/", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
        if _ld_client is not None:
            _ld_client.close()


if __name__ == "__main__":
    main()
