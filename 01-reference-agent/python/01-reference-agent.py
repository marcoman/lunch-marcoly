#!/usr/bin/env python3
"""
01-reference-agent.py — thin HTTP adapter for the reference agent UI.

=============================================================================
HOW TO READ THIS FILE
=============================================================================

This file only does four jobs:

  1. Serve the static browser UI (index.html)
  2. Expose a small JSON bootstrap API
  3. Fetch Yahoo Finance headlines for two tickers
  4. Bridge browser SSE to agent_core.generate_stream()

All persona / prompt / provider / news logic lives in agent_core.py and
yahoo_news.py so a future python-console/ can reuse them without HTTP.

Request map
-----------
  GET /                 → index.html
  GET /api/bootstrap    → personas, default tickers, cached stories, provider/model
  GET /api/stories      → latest 2 headlines for ticker1 + ticker2
                          query: ticker1=NVDA&ticker2=SPCX
                          (falls back to stories_cache.json on Yahoo errors)
  POST /api/generate    → text/event-stream of generation events
                          JSON body: { personaId, stories }
                          Uses the stories already shown in the UI (no Yahoo re-fetch)

Typical session
---------------
  open / → bootstrap → enter tickers → Get Stories → panels fill
        → choose user (Previous/Next) → Generate AI Report
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
    Persona,
    generate_stream,
    model_label,
    persona_by_id,
    provider_label,
    resolve_mode,
)
from yahoo_news import (  # noqa: E402
    DEFAULT_TICKER_1,
    DEFAULT_TICKER_2,
    fetch_stories_for_tickers,
    get_last_pair_cached,
)

# Shown in the UI banner and in the server startup log.
APP_BANNER = "01-reference-agent[python]"

# Distinct from 00-reference-code (8080) so both demos can run together.
PORT = 8090


class Handler(BaseHTTPRequestHandler):
    """Route table for the reference agent web app."""

    server_version = "ReferenceAgentHTTP/1.0"

    def log_message(self, fmt: str, *args) -> None:
        # Prefer simple stderr lines over the default noisy format.
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self) -> None:  # noqa: N802
        """Dispatch static files and API endpoints."""
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        # --- UI ------------------------------------------------------------
        if path in {"/", "/index.html"}:
            self._serve_file(HERE / "index.html", "text/html; charset=utf-8")
            return

        # --- Bootstrap: everything the page needs before first generate ----
        if path == "/api/bootstrap":
            mode = resolve_mode()
            cached = get_last_pair_cached()
            body = {
                "appBanner": APP_BANNER,
                "personas": [
                    {"id": p.id, "name": p.name, "profile": p.profile} for p in PERSONAS
                ],
                "defaultTickers": {
                    "ticker1": (cached or {}).get("ticker1") or DEFAULT_TICKER_1,
                    "ticker2": (cached or {}).get("ticker2") or DEFAULT_TICKER_2,
                },
                "cachedStories": cached,
                "mode": mode,
                "provider": provider_label(mode),
                "model": model_label(mode),
            }
            self._json(200, body)
            return

        # --- Stories: Yahoo Finance headlines for two tickers --------------
        if path == "/api/stories":
            ticker1 = (qs.get("ticker1") or [DEFAULT_TICKER_1])[0]
            ticker2 = (qs.get("ticker2") or [DEFAULT_TICKER_2])[0]
            body = fetch_stories_for_tickers(ticker1, ticker2, count=2)
            self._json(200, body)
            return

        self.send_error(404, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        """Handle generate: stream a report from the stories already in the UI."""
        parsed = urlparse(self.path)
        if parsed.path != "/api/generate":
            self.send_error(404, "Not found")
            return

        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "Invalid JSON body."})
            return

        persona_id = str(payload.get("personaId") or PERSONAS[0].id)
        persona = persona_by_id(persona_id) or PERSONAS[0]
        stories = payload.get("stories")
        if not isinstance(stories, list):
            stories = []
        # Do not call Yahoo here — the client sends the headlines currently shown.
        self._sse_generate(persona, stories)

    # --- helpers -----------------------------------------------------------

    def _serve_file(self, path: Path, content_type: str) -> None:
        """Send a local file as the HTTP body (used for index.html)."""
        if not path.is_file():
            self.send_error(404, "Not found")
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: int, body: dict) -> None:
        """Send a compact JSON response."""
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _sse_generate(self, persona: Persona, ticker_results: list) -> None:
        """Write agent_core events as Server-Sent Events.

        Each event becomes:

            data: {"type":"token","text":"..."}\n\n

        The browser's fetch reader splits on blank lines and JSON-parses the
        payload after the `data:` prefix (see index.html).
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for event in generate_stream(persona, ticker_results=ticker_results):
                payload = json.dumps(event, ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()  # important: push each chunk immediately
        except BrokenPipeError:
            # Client navigated away / aborted; nothing else to do.
            return


def main() -> None:
    """Start the local demo server on 127.0.0.1:PORT."""
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"{APP_BANNER}")
    print(f"Open http://127.0.0.1:{PORT}/")
    print(f"AGENT_LLM_MODE={resolve_mode()} model={model_label(resolve_mode())}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
