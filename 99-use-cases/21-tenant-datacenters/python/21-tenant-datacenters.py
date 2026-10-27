#!/usr/bin/env python3
"""Serve the tenant datacenter lab.

This one process stands in for many applications. Each tenant presence is
one of those applications: its own context, the same two flags. build_layout
keeps that collection in one dict. evaluate_floor walks it and writes each
variation back onto the box.

Flags: tenant-border-palette, tenant-box-fill, tenant-security, tenant-firewall.
"""

from __future__ import annotations

import json
import os
import queue
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import ldclient
from ldclient import Context
from ldclient.config import Config
from ldclient.client import LDClient
from ldclient.interfaces import FlagChange

EXAMPLE = Path(__file__).resolve().parent.parent
WEB = Path(__file__).resolve().parent
sys.path.insert(0, str(EXAMPLE))

from flags import FLAG_BORDER, FLAG_FILL, FLAG_FIREWALL, FLAG_SECURITY, SEGMENTS, hue  # noqa: E402
from fill_rollout import fill_rollout_status, flag_console_url, reset_fill_rollout  # noqa: E402
from ld_flag_controls import api_config, apply_flag_control, list_flag_controls  # noqa: E402
from security_waves import (  # noqa: E402
    reset_security_wave,
    security_status,
    start_security_wave,
)
from tenants import build_layout  # noqa: E402

PORT = int(os.environ.get("PORT", "8080"))
EXAMPLE_CUSTOM = EXAMPLE / "customizations.json.example"
LOCAL_CUSTOM = EXAMPLE / "customizations.json"
_FLOOR_FLAGS = {FLAG_BORDER, FLAG_FILL, FLAG_SECURITY, FLAG_FIREWALL}
_ld_client: LDClient | None = None
_floor_queues: list[queue.Queue[str]] = []
_floor_queues_lock = threading.Lock()


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
    # The stream delivers flag changes to this process. The browser is a
    # separate layer, so the listener only forwards the flag key. The page
    # fetches /api/layout and redraws the floor in place.
    # Flag change notifications — https://launchdarkly.com/docs/sdk/features/flag-changes
    _ld_client.flag_tracker.add_listener(_on_flag_change)
    if not _ld_client.is_initialized():
        print("Warning: LaunchDarkly SDK did not initialize — flags fall back.", flush=True)


def _on_flag_change(change: FlagChange) -> None:
    """Forward one streamed flag change to the open pages.

    The SDK calls this on its stream thread. Keep it to a queue write.
    Evaluating the floor happens later, on the layout request.
    """
    if change.key not in _FLOOR_FLAGS:
        return
    _publish_floor_event(change.key)


def _publish_floor_event(key: str) -> None:
    with _floor_queues_lock:
        subscribers = list(_floor_queues)
    for subscriber in subscribers:
        try:
            subscriber.put_nowait(key)
        except queue.Full:
            try:
                subscriber.get_nowait()
            except queue.Empty:
                pass
            try:
                subscriber.put_nowait(key)
            except queue.Full:
                pass


def tenant_context(box: dict[str, Any]) -> Context:
    """Build one tenant context. This method does not hold the collection.

    The collection is the layout dict from build_layout. Its contexts list
    has one entry per presence: 52 customers, 106 boxes. A customer in three
    datacenters has three contexts, the same key, and a different datacenter.
    evaluate_floor calls this once per box, then evaluates the two flags.

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
    """Evaluate one flag for one context. The last argument is the safe default.

    evaluate_floor calls this once per flag per presence: tenant-border-palette,
    tenant-box-fill, and tenant-security.

    LaunchDarkly: evaluating flags — https://launchdarkly.com/docs/sdk/features/evaluation-reasons
    """
    detail = client.variation_detail(key, context, default)
    return detail.value, _reason_kind(detail)


def evaluate_floor(layout: dict[str, Any]) -> None:
    """Evaluate each flag for every presence and paint that box.

    The layout dict is the whole floor: many simulated applications, one SDK
    client. This loop is where each flag runs. It writes color, fill,
    security, and the firewall icon onto the box the page draws.

    tenant-border-palette is one string for every box. Size class picks the
    hue inside that palette. The safe default is "none", which keeps the
    hairline.

    tenant-box-fill is a boolean. True tints the box with that hue. False,
    or a palette of none, leaves the box empty. The safe default is False.
    A progressive rollout is why two tenants can disagree. A name that fills
    stays filled in every datacenter it occupies, because those contexts
    share a key.

    tenant-security is a boolean. True draws the lock. By name, an individual
    target matches the tenant key, so every datacenter for that name locks
    together. By datacenter, a rule matches the large segment and one
    datacenter segment, so only that presence locks. Full deployment matches
    Small by the size attribute, Medium by datacenter, then Large by name.
    Unknown matches none of the waves. The safe default is False.

    tenant-firewall is a boolean. True draws the firewall icon. Off draws
    nothing. The safe default is False. The release that turns it on is
    configured in LaunchDarkly, not by this process.

    LaunchDarkly: multivariate variations — https://launchdarkly.com/docs/home/flags/variations
    LaunchDarkly: boolean variations — https://launchdarkly.com/docs/home/flags/boolean
    LaunchDarkly: individual targets — https://launchdarkly.com/docs/home/flags/individual-targeting
    LaunchDarkly: targeting rules — https://launchdarkly.com/docs/home/flags/targeting-rules
    """
    boxes = [box for datacenter in layout["datacenters"] for box in datacenter["customers"]]
    client = _ld_client if _ld_client is not None and _ld_client.is_initialized() else None
    border_values: list[str] = []
    fill_values: list[bool] = []
    security_values: list[bool] = []
    firewall_values: list[bool] = []
    border_reason = "fallback"
    fill_reason = "fallback"
    security_reason = "fallback"
    firewall_reason = "fallback"
    for box in boxes:
        if client is None:
            palette, fill, security, firewall = "none", False, False, False
        else:
            context = tenant_context(box)
            # tenant-border-palette — one string palette for this whole pass.
            palette_raw, border_reason = _variation(client, FLAG_BORDER, context, "none")
            palette = str(palette_raw) if isinstance(palette_raw, str) else "none"
            # tenant-box-fill — boolean. Empty unless this context is included.
            fill_raw, fill_reason = _variation(client, FLAG_FILL, context, False)
            fill = bool(fill_raw)
            # tenant-security — boolean. The lock follows the wave: one name,
            # Large in one datacenter, or the full deployment step.
            security_raw, security_reason = _variation(client, FLAG_SECURITY, context, False)
            security = bool(security_raw)
            # tenant-firewall — boolean. True draws the icon. A release in
            # LaunchDarkly chooses who gets it.
            firewall_raw, firewall_reason = _variation(client, FLAG_FIREWALL, context, False)
            firewall = bool(firewall_raw)
        color = hue(palette, box["sizeClass"])
        box["color"] = color
        box["fill"] = bool(color) and fill
        box["security"] = security
        box["firewall"] = firewall
        border_values.append(palette)
        fill_values.append(fill)
        security_values.append(security)
        firewall_values.append(firewall)
    layout["sdkConnected"] = client is not None
    cfg = api_config()
    layout["flags"] = [
        _flag_summary(FLAG_BORDER, "Border palette", border_values, border_reason, len(boxes)),
        _flag_summary(FLAG_FILL, "Box fill", fill_values, fill_reason, len(boxes)),
        _flag_summary(FLAG_SECURITY, "Security", security_values, security_reason, len(boxes)),
        _flag_summary(FLAG_FIREWALL, "Firewall", firewall_values, firewall_reason, len(boxes)),
    ]
    for summary in layout["flags"]:
        summary["flagUrl"] = flag_console_url(cfg.get("projectKey"), cfg.get("environmentKey"), summary["key"])
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


# Lab chrome. customizations.json.example carries the same values.
# A company file replaces any of these with a #RGB or #RRGGBB color.
_DEFAULT_COLORS = {
    "background": "#1e1e2e",
    "panel": "#2d2d3d",
    "ink": "#e8e8ec",
    "muted": "#9a9aab",
    "line": "#4a4a5c",
    "accent": "#64b5f6",
}
_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _colors(data: dict[str, Any]) -> dict[str, str]:
    """Keep only hex colors. A missing or invalid value stays the lab default."""
    raw = data.get("colors")
    chosen = raw if isinstance(raw, dict) else {}
    colors = {}
    for key, fallback in _DEFAULT_COLORS.items():
        value = chosen.get(key)
        if isinstance(value, str) and _HEX_COLOR.match(value.strip()):
            colors[key] = value.strip()
        else:
            colors[key] = fallback
    return colors


def load_customization() -> dict[str, Any]:
    """Read company name, logo, and chrome colors.

    A missing local file uses the example. The colors object may omit a key.
    """
    data = json.loads(EXAMPLE_CUSTOM.read_text())
    if LOCAL_CUSTOM.is_file():
        override = json.loads(LOCAL_CUSTOM.read_text())
        if isinstance(override, dict):
            data.update(override)
    name = str(data.get("companyName") or "Example Hosting").strip()
    logo = str(data.get("logo") or "logo.svg").strip()
    return {"companyName": name, "logo": logo, "colors": _colors(data)}


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
        if path == "/api/floor-events":
            # Server-sent event. One flag key per message. The page fetches
            # the layout. This does not reload the browser.
            # https://launchdarkly.com/docs/sdk/features/flag-changes
            self._floor_events()
            return
        if path == "/api/layout":
            # Rebuild the floor dict, then run tenant-border-palette and
            # tenant-box-fill for every presence. See evaluate_floor.
            custom = load_customization()
            logo = brand_file(custom["logo"]) or brand_file("logo.svg")
            body = build_layout()
            evaluate_floor(body)
            body["companyName"] = custom["companyName"]
            body["logoUrl"] = f"/brand/{logo.name}" if logo else ""
            body["colors"] = custom["colors"]
            self._json(body)
            return
        if path == "/api/flag-controls":
            # LaunchDarkly: get feature flag — on/off and fallthrough
            # https://launchdarkly.com/docs/api/feature-flags/get-feature-flag
            self._json(list_flag_controls())
            return
        if path == "/api/fill-rollout":
            # LaunchDarkly: progressive rollouts — read the current step
            # https://launchdarkly.com/docs/home/releases/progressive-rollouts
            try:
                self._json(fill_rollout_status())
            except Exception as exc:  # noqa: BLE001
                self._json({"ok": False, "error": str(exc)}, 502)
            return
        if path == "/api/security":
            # tenant-security — which wave is running, and the latest step.
            # https://launchdarkly.com/docs/home/flags/individual-targeting
            try:
                self._json(security_status())
            except Exception as exc:  # noqa: BLE001
                self._json({"ok": False, "error": str(exc)}, 502)
            return
        if path.startswith("/brand/"):
            self._brand(unquote(path.removeprefix("/brand/")))
            return
        if path in ("/", "/index.html"):
            self._file(WEB / "index.html", "text/html; charset=utf-8")
            return
        self.send_error(404)

    def _floor_events(self) -> None:
        """Hold one browser connection until a streamed flag change arrives."""
        subscriber: queue.Queue[str] = queue.Queue(maxsize=16)
        with _floor_queues_lock:
            _floor_queues.append(subscriber)
        self.close_connection = False
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    key = subscriber.get(timeout=20)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                payload = json.dumps({"key": key}).encode()
                self.wfile.write(b"event: flag\ndata: " + payload + b"\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            pass
        finally:
            with _floor_queues_lock:
                if subscriber in _floor_queues:
                    _floor_queues.remove(subscriber)

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

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/fill-rollout":
            # LaunchDarkly: stop the rollout by serving Empty and turning the flag off
            # https://launchdarkly.com/docs/home/releases/progressive-rollouts
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                data = json.loads(raw.decode() or "{}")
                if data.get("action") != "reset":
                    raise ValueError('Provide {"action": "reset"}')
                self._json(reset_fill_rollout())
            except ValueError as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
            except Exception as exc:  # noqa: BLE001
                self._json({"ok": False, "error": str(exc)}, 502)
            return
        if path == "/api/security":
            # tenant-security — By name targets S01. By datacenter rules Large in DC01.
            # Full deployment rules Small size 1. By name waits 10 seconds.
            # By datacenter waits 10 seconds. Full deployment waits 10 seconds.
            # The timer writes each later step. Reset clears every wave.
            # https://launchdarkly.com/docs/home/flags/individual-targeting
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                data = json.loads(raw.decode() or "{}")
                action = data.get("action")
                if action == "start":
                    mode = data.get("mode")
                    if mode not in ("name", "datacenter", "full"):
                        raise ValueError('Provide {"action": "start", "mode": "name"}, "datacenter", or "full"')
                    self._json(start_security_wave(mode))
                elif action == "reset":
                    self._json(reset_security_wave())
                else:
                    raise ValueError('Provide {"action": "start", "mode": "name"|"datacenter"|"full"} or {"action": "reset"}')
            except ValueError as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
            except Exception as exc:  # noqa: BLE001
                self._json({"ok": False, "error": str(exc)}, 502)
            return
        if path != "/api/flag-controls":
            self.send_error(404)
            return
        # LaunchDarkly: turnFlagOn / turnFlagOff / updateFallthroughVariationOrRollout
        # https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode() or "{}")
            key = str(data.get("key") or "").strip()
            if not key:
                raise ValueError('"key" is required')
            turn_on = bool(data["on"]) if "on" in data else None
            fallthrough = data.get("fallthrough")
            fallthrough_value = str(fallthrough).strip() if isinstance(fallthrough, str) else None
            result = apply_flag_control(
                key,
                turn_on=turn_on,
                fallthrough=fallthrough_value or None,
                everybody=data.get("everybody") is True,
            )
            self._json(result)
        except ValueError as exc:
            self._json({"ok": False, "error": str(exc)}, 400)
        except Exception as exc:  # noqa: BLE001
            self._json({"ok": False, "error": str(exc)}, 502)

    def _json(self, body: dict, status: int = 200) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
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
