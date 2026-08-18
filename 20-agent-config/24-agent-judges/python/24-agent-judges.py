#!/usr/bin/env python3
"""
24-agent-judges.py — thin HTTP adapter for the Judges runtime-gate demo.

  GET /                 → index.html
  GET /api/bootstrap    → personas, tickers, config/judge keys
  GET /api/stories      → Yahoo headlines
  POST /api/generate    → SSE (draft → judges → optional Charlie rewrite)

LaunchDarkly work lives in agent_core.py.
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
    config_key,
    generate_stream,
    init_launchdarkly,
    judge_discipline_key,
    judge_fidelity_key,
    pass_threshold,
    persona_by_id,
)
from yahoo_news import (  # noqa: E402
    DEFAULT_TICKER_1,
    DEFAULT_TICKER_2,
    fetch_stories_for_tickers,
    get_last_pair_cached,
)

APP_BANNER = "24-agent-judges[python]"
PORT = 8240


class Handler(BaseHTTPRequestHandler):
    server_version = "AgentJudgesHTTP/1.0"

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
                    {"id": p.id, "name": p.name, "profile": p.profile}
                    for p in PERSONAS
                ],
                "defaultTickers": {
                    "ticker1": (cached or {}).get("ticker1") or DEFAULT_TICKER_1,
                    "ticker2": (cached or {}).get("ticker2") or DEFAULT_TICKER_2,
                },
                "cachedStories": cached,
                "mode": "launchdarkly-judges",
                "provider": "AgentControl",
                "model": f"config:{config_key()}",
                "configKey": config_key(),
                "judgeKeys": [judge_fidelity_key(), judge_discipline_key()],
                "passThreshold": pass_threshold(),
            }
            self._json(200, body)
            return

        if path == "/api/stories":
            ticker1 = (qs.get("ticker1") or [DEFAULT_TICKER_1])[0]
            ticker2 = (qs.get("ticker2") or [DEFAULT_TICKER_2])[0]
            body = fetch_stories_for_tickers(ticker1, ticker2, count=2)
            self._json(200, body)
            return

        self.send_error(404, "Not found")

    def do_POST(self) -> None:  # noqa: N802
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
        self._sse_generate(persona, stories)

    def _serve_file(self, path: Path, content_type: str) -> None:
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
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _sse_generate(self, persona: Persona, ticker_results: list) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for event in generate_stream(persona, ticker_results=ticker_results):
                payload = json.dumps(event, ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
        except BrokenPipeError:
            return


def main() -> None:
    init_launchdarkly()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"{APP_BANNER}")
    print(f"Open http://127.0.0.1:{PORT}/")
    print(f"LD_AGENT_CONFIG_KEY={config_key()}")
    print(f"Judges: {judge_fidelity_key()}, {judge_discipline_key()}")
    print(f"Pass threshold: {pass_threshold()}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
