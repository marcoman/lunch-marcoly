#!/usr/bin/env python3
"""Serve the grid navigator web UI on a local HTTP server."""

from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


class Handler(SimpleHTTPRequestHandler):
    """Serve files from this directory (index.html is the app entry point)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)


def main() -> None:
    port = 8080
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"Grid navigator running at http://127.0.0.1:{port}/")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
