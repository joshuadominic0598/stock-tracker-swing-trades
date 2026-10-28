#!/usr/bin/env python3
"""Open the existing Swing Signal server or choose a free localhost port."""

import json
import socket
import subprocess
import sys
import urllib.request
import webbrowser
from pathlib import Path

PORTS = (8765, 8767, 8769)


def is_signaldesk(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
            return json.load(response).get("app") == "signaldesk"
    except (OSError, ValueError, AttributeError):
        return False


def main():
    for port in PORTS:
        if is_signaldesk(port):
            webbrowser.open(f"http://127.0.0.1:{port}/")
            return
    for port in PORTS:
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("server.py")),
                "--port",
                str(port),
                "--open",
            ],
            check=True,
        )
        return
    raise SystemExit("The local app ports are busy. Start server.py with another --port value.")


if __name__ == "__main__":
    main()
