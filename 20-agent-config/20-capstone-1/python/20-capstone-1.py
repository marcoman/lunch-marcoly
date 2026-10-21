#!/usr/bin/env python3
"""
20-capstone-1.py — thin HTTP adapter for the capstone UI.

  GET  /              → index.html
  GET  /api/bootstrap → personas, tools, graph keys, persisted stories
  GET  /api/stories   → headlines
  POST /api/generate  → SSE
  POST /api/feedback  → thumbs on the specialist draft

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
    TOOL_ORDER,
    Persona,
    generate_stream,
    graph_key,
    init_launchdarkly,
    judge_key,
    node_key,
    persona_by_id,
    submit_feedback,
)
from yahoo_news import (  # noqa: E402
    DEFAULT_TICKER_1,
    DEFAULT_TICKER_2,
    fetch_stories_for_tickers,
    get_last_pair_cached,
)

APP_BANNER = "20-capstone-1[python]"
PORT = 8290
ROLES = ("assess", "report", "questions", "good", "finalize")


class Handler(BaseHTTPRequestHandler):
    server_version = "CapstoneHTTP/1.0"

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
            self._json(200, {
                "appBanner": APP_BANNER,
                "personas": [
                    {"id": p.id, "name": p.name, "profile": p.profile, "anonymous": p.anonymous}
                    for p in PERSONAS
                ],
                "tools": TOOL_ORDER,
                "actions": [
                    {"id": "report", "labelKey": "actionReport"},
                    {"id": "questions", "labelKey": "actionQuestions"},
                    {"id": "good", "labelKey": "actionGood"},
                ],
                "graphKey": graph_key(),
                "nodeKeys": {role: node_key(role) for role in ROLES},
                "judgeKeys": [judge_key("fidelity"), judge_key("discipline")],
                "defaultTickers": {
                    "ticker1": (cached or {}).get("ticker1") or DEFAULT_TICKER_1,
                    "ticker2": (cached or {}).get("ticker2") or DEFAULT_TICKER_2,
                },
                "persistedStories": None if not cached else {
                    "ticker1": cached.get("ticker1"),
                    "ticker2": cached.get("ticker2"),
                    "tickers": cached.get("tickers"),
                    "savedAt": cached.get("updated_at"),
                    "directory": "20-agent-config/stories",
                },
            })
            return
        if path == "/api/stories":
            ticker1 = (qs.get("ticker1") or [DEFAULT_TICKER_1])[0]
            ticker2 = (qs.get("ticker2") or [DEFAULT_TICKER_2])[0]
            self._json(200, fetch_stories_for_tickers(ticker1, ticker2, count=2))
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "Invalid JSON body."})
            return
        if parsed.path == "/api/generate":
            persona = persona_by_id(str(payload.get("personaId") or "")) or PERSONAS[1]
            action = str(payload.get("action") or "report")
            locale = "es" if payload.get("locale") == "es" else "en"
            tools = payload.get("tools") if isinstance(payload.get("tools"), list) else []
            stories = payload.get("stories") if isinstance(payload.get("stories"), list) else []
            self._sse(persona, action, stories, [str(item) for item in tools], locale)
            return
        if parsed.path == "/api/feedback":
            persona = persona_by_id(str(payload.get("personaId") or "")) or PERSONAS[1]
            try:
                body = submit_feedback(
                    persona=persona,
                    locale="es" if payload.get("locale") == "es" else "en",
                    resumption_token=str(payload.get("resumptionToken") or ""),
                    kind=str(payload.get("kind") or ""),
                )
                self._json(200, body)
            except Exception as exc:  # noqa: BLE001
                self._json(400, {"ok": False, "error": str(exc)})
            return
        self.send_error(404, "Not found")

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

    def _sse(self, persona: Persona, action: str, stories: list, tools: list[str], locale: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for event in generate_stream(persona, action, stories, tools, locale):
                self.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()
        except BrokenPipeError:
            return
        except Exception as exc:  # noqa: BLE001
            try:
                self.wfile.write(
                    f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n".encode("utf-8")
                )
                self.wfile.flush()
            except BrokenPipeError:
                return


def main() -> None:
    init_launchdarkly()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(APP_BANNER)
    print(f"Open http://127.0.0.1:{PORT}/")
    print(f"LD_GRAPH_KEY={graph_key()}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
