#!/usr/bin/env python3
"""
23-agent-tools.py — thin HTTP adapter for the tools demo UI.

  1. Serve index.html
  2. JSON bootstrap
  3. Yahoo Finance headlines
  4. Bridge browser SSE → agent_core.generate_stream() (tool loop)

LaunchDarkly work lives in agent_core.py (completion_config + tools + track_tool_call).
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from agent_core import (  # noqa: E402
    PERSONAS,
    config_key,
    generate_stream,
    init_launchdarkly,
    persona_by_id,
)
from yahoo_news import (  # noqa: E402
    DEFAULT_TICKER_1,
    DEFAULT_TICKER_2,
    fetch_stories_for_tickers,
    get_last_pair_cached,
)

APP_BANNER = "23-agent-tools[python]"
PORT = 8230


class Handler(BaseHTTPRequestHandler):
    server_version = "AgentToolsHTTP/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path in {"/", "/index.html"}:
            self._serve_file(HERE / "index.html", "text/html; charset=utf-8")
            return

        if path == "/api/bootstrap":
            cached = get_last_pair_cached()
            body = {
                "appBanner": APP_BANNER,
                "personas": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "profile": p.profile,
                        "model": p.model,
                        "anonymous": p.anonymous,
                    }
                    for p in PERSONAS
                ],
                "defaultTickers": {
                    "ticker1": (cached or {}).get("ticker1") or DEFAULT_TICKER_1,
                    "ticker2": (cached or {}).get("ticker2") or DEFAULT_TICKER_2,
                },
                "cachedStories": cached,
                "mode": "launchdarkly",
                "provider": "AgentControl",
                "model": f"config:{config_key()}",
                "configKey": config_key(),
            }
            self._send_json(200, body)
            return

        if path == "/api/stories":
            ticker1 = (qs.get("ticker1") or [DEFAULT_TICKER_1])[0]
            ticker2 = (qs.get("ticker2") or [DEFAULT_TICKER_2])[0]
            try:
                self._send_json(200, fetch_stories_for_tickers(ticker1, ticker2, 2))
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"error": str(exc)})
            return

        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/generate":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON body."})
            return

        persona_id = str(payload.get("personaId") or PERSONAS[0].id)
        persona = persona_by_id(persona_id) or PERSONAS[0]
        stories = payload.get("stories") if isinstance(payload.get("stories"), list) else []

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        try:
            for event in generate_stream(persona, stories):
                line = "data: " + json.dumps(event, default=str) + "\n\n"
                self.wfile.write(line.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:  # noqa: BLE001
            try:
                err = "data: " + json.dumps({"type": "error", "message": str(exc)}) + "\n\n"
                self.wfile.write(err.encode("utf-8"))
                self.wfile.flush()
            except Exception:  # noqa: BLE001
                return

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status: int, body: object) -> None:
        raw = json.dumps(body, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> None:
    init_launchdarkly()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(APP_BANNER)
    print(f"Open http://127.0.0.1:{PORT}/")
    print(f"LD_AGENT_CONFIG_KEY={config_key()}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
