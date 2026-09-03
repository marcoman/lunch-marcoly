#!/usr/bin/env python3
"""Serve the SDK-fallback lab and gate its real streaming connection.

LaunchDarkly: every grid refresh uses ``variation_detail``. The loopback gate
only interrupts flag-data delivery, allowing the same SDK client to demonstrate
last-known evaluation without application-side fallback branching.
https://launchdarkly.com/docs/sdk/features/evaluating
"""

from __future__ import annotations

import http.client
import json
import os
import signal
import socket
import ssl
import sys
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ldclient import Config
from ldclient.client import LDClient
from ldclient.context import Context

PORT = int(os.environ.get("PORT", "8181"))
GATE_PORT = int(os.environ.get("LD_STREAM_GATE_PORT", "8182"))
ROOT = Path(__file__).resolve().parent
FLAG_KEY = "enable-sdk-fallback-grid-highlight"
FLAG_NAME = "Enable: SDK fallback grid highlight"
CODE_DEFAULT = "none"
LIVE_VALUE = "green"
STREAM_ORIGIN = os.environ.get(
    "LD_STREAM_ORIGIN", "https://stream.launchdarkly.com"
).rstrip("/")
START_WAIT = float(os.environ.get("LD_START_WAIT", "2"))


class ApiError(Exception):
    """An error safe to return from the local JSON API."""

    def __init__(self, message: str, status: int = 500) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class ActiveStream:
    """Resources for one proxied SDK stream, closable by the lab control."""

    response: http.client.HTTPResponse
    connection: http.client.HTTPConnection

    def close(self) -> None:
        connection_socket = self.connection.sock
        if connection_socket is not None:
            try:
                connection_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection_socket.close()
        try:
            self.response.close()
        finally:
            self.connection.close()


class StreamGate:
    """Open, reject, and actively sever proxied LaunchDarkly streams."""

    def __init__(self) -> None:
        self._allowed = True
        self._active: list[ActiveStream] = []
        self._lock = threading.Lock()

    @property
    def allowed(self) -> bool:
        with self._lock:
            return self._allowed

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._active)

    def open(self) -> None:
        with self._lock:
            self._allowed = True

    def drop(self) -> None:
        with self._lock:
            self._allowed = False
            streams = list(self._active)
            self._active.clear()
        for stream in streams:
            try:
                stream.close()
            except OSError:
                pass

    def register(self, stream: ActiveStream) -> bool:
        with self._lock:
            if not self._allowed:
                return False
            self._active.append(stream)
            return True

    def unregister(self, stream: ActiveStream) -> None:
        with self._lock:
            if stream in self._active:
                self._active.remove(stream)


gate = StreamGate()
_client: LDClient | None = None
_client_lock = threading.RLock()
_mode = "starting"
_ever_initialized = False


class LabServer(ThreadingHTTPServer):
    """Do not let blocked stream-proxy workers delay process shutdown."""

    daemon_threads = True
    allow_reuse_address = True


def json_reason(reason: object) -> object:
    """Return the SDK evaluation reason in a JSON-safe form."""
    if reason is None or isinstance(reason, (str, int, float, bool, list, dict)):
        return reason
    if hasattr(reason, "__dict__"):
        return vars(reason)
    return str(reason)


def stream_connection(path: str, headers: dict[str, str]) -> ActiveStream:
    """Open the gate's upstream stream without exposing its Authorization header."""
    origin = urlparse(STREAM_ORIGIN)
    connection_type = (
        http.client.HTTPSConnection if origin.scheme == "https" else http.client.HTTPConnection
    )
    kwargs: dict[str, Any] = {"timeout": 10}
    if origin.scheme == "https":
        kwargs["context"] = ssl.create_default_context()
    connection = connection_type(origin.hostname, origin.port, **kwargs)
    upstream_path = f"{origin.path.rstrip('/')}{path}"
    connection.request("GET", upstream_path, headers=headers)
    response = connection.getresponse()
    if connection.sock is not None:
        connection.sock.settimeout(None)
    return ActiveStream(response, connection)


class GateHandler(BaseHTTPRequestHandler):
    """Reverse-proxy only the SDK stream and let controls cut the connection."""

    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:
        if not gate.allowed:
            self.send_error(503, "stream gate closed")
            return

        forwarded = {
            name: value
            for name, value in self.headers.items()
            if name.lower() in {
                "authorization",
                "accept",
                "user-agent",
                "x-launchdarkly-event-schema",
                "x-launchdarkly-wrapper",
            }
        }
        stream: ActiveStream | None = None
        try:
            stream = stream_connection(self.path, forwarded)
            if stream.response.status >= 400:
                self.send_error(stream.response.status, stream.response.reason)
                return
            if not gate.register(stream):
                stream.close()
                self.send_error(503, "stream gate closed")
                return

            self.send_response(stream.response.status)
            self.send_header(
                "Content-Type",
                stream.response.getheader("Content-Type", "text/event-stream"),
            )
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

            while gate.allowed:
                chunk = stream.response.read1(4096)
                if not chunk:
                    break
                self.wfile.write(f"{len(chunk):X}\r\n".encode("ascii"))
                self.wfile.write(chunk)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionError, OSError, http.client.HTTPException):
            pass
        finally:
            if stream is not None:
                gate.unregister(stream)
                try:
                    stream.close()
                except OSError:
                    pass
            self.close_connection = True


def make_client() -> LDClient:
    """Construct one client whose streaming data source passes through the gate.

    LaunchDarkly: ``stream_uri`` changes transport only. Evaluations continue
    through the SDK's normal in-memory feature store.
    https://launchdarkly-python-sdk.readthedocs.io/en/latest/api-main.html
    """
    sdk_key = os.environ.get("LD_SDK_KEY", "").strip()
    if not sdk_key:
        raise ApiError("LD_SDK_KEY is required for this lab.", 503)
    return LDClient(
        Config(
            sdk_key,
            stream_uri=f"http://127.0.0.1:{GATE_PORT}",
            send_events=False,
            diagnostic_opt_out=True,
            initial_reconnect_delay=0.5,
        ),
        start_wait=START_WAIT,
    )


def replace_client(mode: str) -> dict[str, Any]:
    """Create a fresh client for live or never-initialized demonstrations."""
    global _client, _mode, _ever_initialized
    if mode == "stream":
        gate.open()
    elif mode == "default":
        gate.drop()
    else:
        raise ApiError(f"Unknown mode: {mode}", 400)

    with _client_lock:
        old_client = _client
        _client = None
        _mode = mode
        _ever_initialized = False
    if old_client is not None:
        old_client.close()

    new_client = make_client()
    initialized = new_client.is_initialized()
    with _client_lock:
        _client = new_client
        _ever_initialized = initialized
    return status()


def drop_stream() -> dict[str, Any]:
    """Sever transport while preserving this client's initialized feature store."""
    global _mode, _ever_initialized
    with _client_lock:
        if _client is None or not _client.is_initialized():
            raise ApiError("Connect and initialize the stream before dropping it.", 409)
        _ever_initialized = True
        _mode = "last-known"
    gate.drop()
    return status()


def source() -> str:
    """Name the lab's current evaluation data path."""
    if _mode == "last-known":
        return "LAST_KNOWN"
    if _mode == "stream" and _client is not None and _client.is_initialized():
        return "STREAM"
    return "DEFAULT"


def status() -> dict[str, Any]:
    """Describe transport separately from SDK initialization and evaluation."""
    global _ever_initialized
    with _client_lock:
        client = _client
        initialized = client.is_initialized() if client is not None else False
        if initialized:
            _ever_initialized = True
        return {
            "mode": _mode,
            "source": source(),
            "initialized": initialized,
            "everInitialized": _ever_initialized,
            "gateOpen": gate.allowed,
            "activeStreams": gate.active_count,
            "startWaitSeconds": START_WAIT,
            "configured": bool(os.environ.get("LD_SDK_KEY", "").strip()),
        }


def evaluate(username: str) -> dict[str, Any]:
    """Evaluate the dedicated string flag in every mode with default ``none``.

    LaunchDarkly: detailed variation evaluation exposes the targeting/error
    reason; the lab source is reported separately.
    https://launchdarkly.com/docs/sdk/features/evaluating
    """
    context = Context.builder(username).kind("user").build()
    with _client_lock:
        client = _client
        if client is None:
            return {
                "flagValue": CODE_DEFAULT,
                "highlightColor": CODE_DEFAULT,
                "reason": {"kind": "ERROR", "errorKind": "CLIENT_NOT_READY"},
                **status(),
            }
        detail = client.variation_detail(FLAG_KEY, context, CODE_DEFAULT)
        value = detail.value if detail.value in {CODE_DEFAULT, LIVE_VALUE} else CODE_DEFAULT
        return {
            "flagValue": value,
            "highlightColor": value,
            "reason": json_reason(detail.reason),
            **status(),
        }


class AppHandler(SimpleHTTPRequestHandler):
    """Serve the grid and its local fallback-scenario controls."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, status_code: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/config":
                self.send_json(
                    200,
                    {
                        "runtime": "18-sdk-fallbacks[python]",
                        "flag": {"key": FLAG_KEY, "name": FLAG_NAME},
                        "codeDefault": CODE_DEFAULT,
                        **status(),
                    },
                )
                return
            if parsed.path == "/api/evaluate":
                username = (parse_qs(parsed.query).get("username") or [""])[0].strip()
                if not username:
                    raise ApiError("username query parameter is required", 400)
                self.send_json(200, evaluate(username))
                return
            if parsed.path == "/api/status":
                self.send_json(200, status())
                return
            if parsed.path.startswith("/api/"):
                self.send_json(404, {"error": "Not found"})
                return
            super().do_GET()
        except Exception as error:
            self.send_json(getattr(error, "status", 500), {"error": str(error)})

    def do_POST(self) -> None:
        try:
            if self.path == "/api/connect":
                self.send_json(200, replace_client("stream"))
            elif self.path == "/api/drop-stream":
                self.send_json(200, drop_stream())
            elif self.path == "/api/block-init":
                self.send_json(200, replace_client("default"))
            else:
                self.send_json(404, {"error": "Not found"})
        except Exception as error:
            self.send_json(getattr(error, "status", 500), {"error": str(error)})


def close_all(*_args: object) -> None:
    """Close client and active stream resources during process shutdown."""
    global _client
    gate.drop()
    with _client_lock:
        client = _client
        _client = None
    if client is not None:
        client.close()


def run_server() -> None:
    """Start the stream gate before constructing the first SDK client."""
    gate_server = LabServer(("127.0.0.1", GATE_PORT), GateHandler)
    gate_thread = threading.Thread(target=gate_server.serve_forever, daemon=True)
    gate_thread.start()

    try:
        if os.environ.get("LD_SDK_KEY", "").strip():
            initial = replace_client("stream")
            if not initial["initialized"]:
                print(
                    "Warning: SDK did not initialize; use Connect stream to retry.",
                    file=sys.stderr,
                )
        else:
            print("Warning: LD_SDK_KEY is unset; evaluations use none.", file=sys.stderr)

        app_server = LabServer(("127.0.0.1", PORT), AppHandler)
        print("18-sdk-fallbacks[python]")
        print(f"Flag: {FLAG_NAME} ({FLAG_KEY}); code default: {CODE_DEFAULT}")
        print(f"Stream gate: http://127.0.0.1:{GATE_PORT} → {STREAM_ORIGIN}")
        print(f"Open http://127.0.0.1:{PORT}/", flush=True)
        try:
            app_server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            app_server.server_close()
    finally:
        close_all()
        gate_server.shutdown()
        gate_server.server_close()


def raise_keyboard_interrupt() -> None:
    """Translate SIGTERM into the same cleanup path as Ctrl-C."""
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_args: raise_keyboard_interrupt())
    run_server()
