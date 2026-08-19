#!/usr/bin/env python3
"""
portal.py — series shell for 20-agent-config (Python web examples 21–24).

One process for the user:
  - Serves this folder's index.html on :8200 (PORTAL_PORT)
  - Spawns each example's existing Python server as a child
  - Embeds those pages in iframes (see index.html)

Standalone entrypoints under each example's python/ still work alone.
Ctrl+C / SIGTERM stops the portal and all children.
"""

from __future__ import annotations

import atexit
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
SERIES_ROOT = HERE.parent
PORTAL_PORT = int(os.environ.get("PORTAL_PORT") or "8200")
APP_BANNER = "20-agent-config[portal]"

# cwd = each example's python/ so index.html + imports resolve like a solo run.
CHILDREN: list[dict[str, Any]] = [
    {
        "id": "21",
        "label": "Completion",
        "script": SERIES_ROOT
        / "21-agent-completion-config"
        / "python"
        / "21-agent-completion-config.py",
        "cwd": SERIES_ROOT / "21-agent-completion-config" / "python",
        "port": 8210,
    },
    {
        "id": "22",
        "label": "Tracked + feedback",
        "script": SERIES_ROOT / "22-config-outside-code" / "python" / "22-config-outside-code.py",
        "cwd": SERIES_ROOT / "22-config-outside-code" / "python",
        "port": 8220,
    },
    {
        "id": "23",
        "label": "Tools",
        "script": SERIES_ROOT / "23-agent-tools" / "python" / "23-agent-tools.py",
        "cwd": SERIES_ROOT / "23-agent-tools" / "python",
        "port": 8230,
    },
    {
        "id": "24",
        "label": "Judges",
        "script": SERIES_ROOT / "24-agent-judges" / "python" / "24-agent-judges.py",
        "cwd": SERIES_ROOT / "24-agent-judges" / "python",
        "port": 8240,
    },
]

_procs: dict[str, subprocess.Popen[bytes]] = {}
_lock = threading.Lock()
_shutting_down = False


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except OSError:
        return False


def _wait_for_port(port: int, timeout_s: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _port_open(port):
            return True
        time.sleep(0.2)
    return False


def _pipe_prefix(child_id: str, stream) -> None:
    """Forward child stdout/stderr lines with a [id] prefix."""
    try:
        for raw in iter(stream.readline, b""):
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            print(f"[{child_id}] {line}", flush=True)
    except Exception:
        pass
    finally:
        try:
            stream.close()
        except Exception:
            pass


def start_children() -> None:
    python = sys.executable
    env = os.environ.copy()

    for child in CHILDREN:
        cid = child["id"]
        port = int(child["port"])
        script: Path = child["script"]
        cwd: Path = child["cwd"]

        if not script.is_file():
            print(f"[{cid}] ERROR: missing script {script}", flush=True)
            continue

        if _port_open(port):
            print(
                f"[{cid}] WARNING: port {port} already in use — "
                f"assuming an existing server; not spawning.",
                flush=True,
            )
            continue

        print(f"[{cid}] Starting {script.name} on :{port} …", flush=True)
        proc = subprocess.Popen(
            [python, str(script)],
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        with _lock:
            _procs[cid] = proc

        threading.Thread(
            target=_pipe_prefix,
            args=(cid, proc.stdout),
            daemon=True,
            name=f"portal-pipe-{cid}",
        ).start()

        if _wait_for_port(port):
            print(f"[{cid}] Ready http://127.0.0.1:{port}/", flush=True)
        else:
            code = proc.poll()
            print(
                f"[{cid}] ERROR: port {port} not ready "
                f"(exit={code}). Check LD_SDK_KEY and logs above.",
                flush=True,
            )


def stop_children() -> None:
    global _shutting_down
    if _shutting_down:
        return
    _shutting_down = True

    with _lock:
        items = list(_procs.items())
        _procs.clear()

    for cid, proc in items:
        if proc.poll() is not None:
            continue
        print(f"[{cid}] Stopping …", flush=True)
        try:
            proc.terminate()
        except Exception:
            pass

    deadline = time.monotonic() + 5.0
    for cid, proc in items:
        remaining = max(0.05, deadline - time.monotonic())
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            print(f"[{cid}] Kill (still running)", flush=True)
            try:
                proc.kill()
            except Exception:
                pass
            try:
                proc.wait(timeout=2)
            except Exception:
                pass


def child_status() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with _lock:
        procs = dict(_procs)
    for child in CHILDREN:
        cid = child["id"]
        port = int(child["port"])
        proc = procs.get(cid)
        alive = proc is not None and proc.poll() is None
        up = _port_open(port)
        out.append(
            {
                "id": cid,
                "label": child["label"],
                "port": port,
                "url": f"http://127.0.0.1:{port}/",
                "spawned": proc is not None,
                "alive": alive,
                "up": up,
            }
        )
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: Any) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self._send(status, raw, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            index = HERE / "index.html"
            if not index.is_file():
                self._send(404, b"Not found", "text/plain; charset=utf-8")
                return
            self._send(200, index.read_bytes(), "text/html; charset=utf-8")
            return

        if path == "/api/status":
            self._json(
                200,
                {
                    "appBanner": APP_BANNER,
                    "portalPort": PORTAL_PORT,
                    "children": child_status(),
                },
            )
            return

        self._send(404, b"Not found", "text/plain; charset=utf-8")


def main() -> None:
    if not (os.environ.get("LD_SDK_KEY") or "").strip():
        print(
            "WARNING: LD_SDK_KEY is unset. Child examples will fail to init "
            "LaunchDarkly until you export a server-side SDK key.",
            flush=True,
        )

    atexit.register(stop_children)
    start_children()

    server = ThreadingHTTPServer(("127.0.0.1", PORTAL_PORT), Handler)

    def _shutdown(signum=None, _frame=None) -> None:
        print(f"\n{APP_BANNER}: shutting down …", flush=True)
        stop_children()
        # serve_forever blocks the main thread; shut it down from a helper thread.
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print(APP_BANNER, flush=True)
    print(f"Open http://127.0.0.1:{PORTAL_PORT}/", flush=True)
    print("Tabs embed Python examples on 8210 / 8220 / 8230 / 8240.", flush=True)
    print("Ctrl+C stops the portal and all children.", flush=True)
    try:
        server.serve_forever()
    finally:
        stop_children()
        server.server_close()
        print(f"{APP_BANNER}: stopped.", flush=True)


if __name__ == "__main__":
    main()
