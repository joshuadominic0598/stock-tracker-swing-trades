"""Local startup, browser launch and market refresh scheduling."""

import argparse
import json
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

from swing_signal.data import market, storage
from swing_signal.http.server import Handler

PORTS = (8765, 8767, 8769)

def is_running(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
            return json.load(response).get("app") == "signaldesk"
    except (OSError, ValueError, AttributeError):
        return False

def schedule(interval, action):
    def repeat():
        while True:
            time.sleep(interval)
            action()

    threading.Thread(target=repeat, daemon=True).start()

def serve(arguments):
    parser = argparse.ArgumentParser(description="Run Swing Signal on your laptop")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true")
    parser.add_argument(
        "--data-dir", type=Path, help="Workspace directory (default: data/ beside the source app)"
    )
    parser.add_argument("--no-refresh", action="store_true", help="Start with cached data only")
    args = parser.parse_args(arguments)
    if args.data_dir:
        storage.DB_PATH = args.data_dir.expanduser().resolve() / "signaldesk.sqlite3"
    storage.init()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        parser.error(f"Could not open localhost port {args.port}: {exc}. Try another --port.")
    url = f"http://127.0.0.1:{server.server_port}"
    print(
        f"\n  Swing Signal → {url}\n  Data → {storage.DB_PATH}\n  Press Control-C to stop.\n",
        flush=True,
    )
    if not args.no_refresh:
        market.refresh()
        schedule(900, market.refresh)
        schedule(60, market.refresh_quotes)
    if args.open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSwing Signal stopped. Your work is saved.")
    finally:
        server.server_close()

def launch():
    for port in PORTS:
        if is_running(port):
            webbrowser.open(f"http://127.0.0.1:{port}/")
            return
    for port in PORTS:
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
        serve(["--port", str(port), "--open"])
        return
    raise SystemExit("The local app ports are busy. Start launch.py with another --port value.")

def main():
    if len(sys.argv) > 1:
        serve(sys.argv[1:])
    else:
        launch()
