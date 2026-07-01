#!/usr/bin/env python3
"""Local host for the Silent Zone Operations Console.

Run this script instead of opening index.html with file://.
It gives the browser a stable http://127.0.0.1 origin so sessionStorage,
fetch requests, and the console's 15-minute token flow behave predictably.
"""
from __future__ import annotations

import argparse
import functools
import os
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class ConsoleHandler(SimpleHTTPRequestHandler):
    """Static handler with no-cache headers for local UI development."""

    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory or str(ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self.path = "/index.html"
        super().do_GET()

    def log_message(self, fmt: str, *args) -> None:
        print("[console-host] " + (fmt % args))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve the local Silent Zone Operations Console."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address. Default: 127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5500,
        help="Listen port. Default: 5500",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the console URL in the default browser.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    index_path = ROOT / "index.html"

    if not index_path.exists():
        raise SystemExit("找不到 index.html，請確認檔案沒有被移動。")

    handler = functools.partial(ConsoleHandler, directory=str(ROOT))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}/"

    print("=" * 64)
    print("Silent Zone Operations Console local host")
    print(f"UI URL: {url}")
    print("請保持這個終端機開啟；按 Ctrl+C 停止。")
    print("FastAPI backend should run separately at https://silent-api.hasaki.idv.tw/")
    print("=" * 64)

    if args.open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[console-host] Stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
