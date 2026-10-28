#!/usr/bin/env python3
"""Swing Signal: dependency-free localhost service and static frontend."""

import argparse
import json
import math
import mimetypes
import re
import threading
import time
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app import ai_providers, attention, intelligence, market, settings, storage

ROOT = Path(__file__).resolve().parent
SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9&.-]{0,23}$")


def number(value, name, optional=False):
    if optional and (value is None or value == ""):
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValueError(name + " must be a number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(name + " must be greater than zero")
    return value


class Handler(BaseHTTPRequestHandler):
    def local_host(self):
        """Keep loopback services inaccessible through an attacker-controlled hostname."""
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1:
            return False
        port = self.server.server_port
        return hosts[0].lower() in (f"127.0.0.1:{port}", f"localhost:{port}")

    def log_message(self, fmt, *args):
        if self.path.startswith("/api/") and "?" in self.path:
            return
        if "/api/overview" not in str(args):
            super().log_message(fmt, *args)

    def reply(self, value, status=200):
        raw = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not self.local_host():
            return self.reply(dict(error="Use this app through its localhost address"), 403)
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/api/health":
                return self.reply(dict(ok=True, app="signaldesk", version="2.1.0"))
            if path == "/api/overview":
                overview = market.overview()
                overview["connections"] = settings.public()
                return self.reply(overview)
            if path == "/api/connections":
                return self.reply(settings.public())
            if path == "/api/catalog":
                query = parse_qs(parsed.query).get("q", [""])[0].strip().upper()
                return self.reply(market.search_catalog(query))
            if path == "/api/models":
                return self.reply(intelligence.models())
            if path == "/api/backup":
                data = {
                    table: storage.rows("SELECT * FROM " + table)
                    for table in ("assets", "zones", "positions", "journal", "cache")
                }
                return self.reply(dict(version=1, exported_at=market.now(), data=data))
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[:2] in (
                ["api", "assets"],
                ["api", "research"],
            ):
                asset = storage.asset(parts[2])
                if not asset:
                    return self.reply(dict(error="Unknown asset"), 404)
                if parts[1] == "research":
                    return self.reply(market.research(asset))
                tf = parse_qs(parsed.query).get("timeframe", ["1d"])[0]
                if tf not in ("1d", "1w"):
                    raise ValueError("Use daily or weekly timeframe")
                return self.reply(market.asset_detail(asset, tf))
            if path.startswith("/api/"):
                return self.reply(dict(error="Unknown endpoint"), 404)
            rel = "index.html" if path == "/" else path.lstrip("/")
            target = (ROOT / "web" / rel).resolve()
            if not target.is_relative_to(ROOT / "web") or not target.is_file():
                return self.reply(dict(error="File not found"), 404)
            raw = target.read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type",
                mimetypes.guess_type(str(target))[0] or "application/octet-stream",
            )
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except ValueError as exc:
            self.reply(dict(error=str(exc)), 400)
        except Exception as exc:
            self.reply(dict(error=str(exc)), 500)

    def do_POST(self):
        if not self.local_host():
            return self.reply(dict(error="Use this app through its localhost address"), 403)
        try:
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                return self.reply(dict(error="Cross-origin changes are disabled"), 403)
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                raise ValueError("Use application/json")
            size = int(self.headers.get("Content-Length", "0"))
            if size < 0:
                raise ValueError("Content-Length must be non-negative")
            if size > 4_000_000:
                return self.reply(dict(error="Request is too large"), 413)
            body = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("Use a JSON object")
            path = urlparse(self.path).path
            if path == "/api/connections/check":
                return self.reply(
                    ai_providers.check_connection(
                        str(body.get("provider", "")), str(body.get("model", ""))
                    )
                )
            if path == "/api/connections":
                settings.update(body)
                return self.reply(settings.public())
            if path == "/api/refresh-quotes":
                threading.Thread(
                    target=market.refresh_quotes, kwargs={"force": True}, daemon=True
                ).start()
                return self.reply(dict(started=True))
            if path == "/api/refresh":
                return self.reply(dict(started=market.refresh(), refresh=market.get_state()))
            if path == "/api/assets":
                symbol = str(body.get("symbol", "")).strip().upper().removesuffix(".NS")
                name = str(body.get("name", symbol)).strip()[:100] or symbol
                which = body.get("market", "NSE")
                if not SYMBOL.fullmatch(symbol):
                    raise ValueError("Enter a valid NSE symbol or USDT crypto pair")
                if which not in ("NSE", "CRYPTO", "US"):
                    raise ValueError("Choose NSE, US or crypto")
                if which == "CRYPTO" and not symbol.endswith("USDT"):
                    raise ValueError("New crypto assets use Binance USDT pairs, e.g. LINKUSDT")
                if storage.asset(symbol):
                    raise ValueError("This asset is already on your watchlist")
                storage.write(
                    "INSERT INTO assets VALUES (?,?,?,?,?)",
                    (
                        symbol,
                        name,
                        which,
                        str(body.get("sector", "Custom watchlist"))[:80],
                        0,
                    ),
                )
                market.refresh()
                return self.reply(dict(ok=True, symbol=symbol))
            parts = path.strip("/").split("/")
            if len(parts) != 4 or parts[:2] != ["api", "assets"]:
                return self.reply(dict(error="Unknown endpoint"), 404)
            symbol = parts[2]
            action = parts[3]
            asset = storage.asset(symbol)
            if not asset:
                return self.reply(dict(error="Unknown asset"), 404)
            if action == "zone":
                low = number(body.get("low"), "Lower price")
                high = number(body.get("high"), "Upper price")
                if high <= low:
                    raise ValueError("Upper price must be above lower price")
                kind = body.get("kind")
                if kind not in ("demand", "supply"):
                    raise ValueError("Choose demand or supply")
                label = str(body.get("label", "My " + kind + " zone"))[:80]
                zone_id = body.get("id")
                if zone_id is not None:
                    storage.write(
                        "UPDATE zones SET low=?, high=?, kind=?, label=? WHERE id=? AND symbol=?",
                        (low, high, kind, label, int(zone_id), symbol),
                    )
                else:
                    storage.write(
                        "INSERT INTO zones(symbol,kind,low,high,label,created_at) VALUES (?,?,?,?,?,?)",
                        (symbol, kind, low, high, label, market.now()),
                    )
            elif action == "delete-zone":
                storage.write(
                    "DELETE FROM zones WHERE id=? AND symbol=?",
                    (int(body["id"]), symbol),
                )
            elif action == "position":
                quantity = number(body.get("quantity"), "Quantity", True)
                average = number(body.get("average"), "Average cost", True)
                if (quantity is None) != (average is None):
                    raise ValueError("Enter both quantity and average cost, or leave both empty")
                storage.write(
                    "INSERT OR REPLACE INTO positions VALUES (?,?,?)",
                    (symbol, quantity, average),
                )
                storage.write(
                    "UPDATE assets SET held=? WHERE symbol=?",
                    (int(bool(body.get("held", True))), symbol),
                )
            elif action == "journal":
                review = str(body.get("review_date", ""))
                if review:
                    date.fromisoformat(review)
                storage.write(
                    "INSERT OR REPLACE INTO journal VALUES (?,?,?,?,?,?)",
                    (
                        symbol,
                        str(body.get("thesis", ""))[:10000],
                        str(body.get("invalidation", ""))[:2000],
                        str(body.get("horizon", "1–3 months"))[:80],
                        review,
                        market.now(),
                    ),
                )
            elif action == "trends-import":
                return self.reply(attention.import_trends(asset, body.get("csv", "")))
            elif action == "ai-brief":
                tf = body.get("timeframe", "1d")
                if tf not in ("1d", "1w"):
                    raise ValueError("Choose daily or weekly timeframe")
                return self.reply(
                    intelligence.generate(
                        asset,
                        str(body.get("model", "")),
                        tf,
                        str(body.get("provider", "local")),
                    )
                )
            else:
                return self.reply(dict(error="Unknown action"), 404)
            return self.reply(dict(ok=True))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self.reply(dict(error=str(exc)), 400)
        except Exception as exc:
            self.reply(dict(error=str(exc)), 500)


def main():
    parser = argparse.ArgumentParser(description="Run Swing Signal on your laptop")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true")
    parser.add_argument(
        "--data-dir", type=Path, help="Workspace directory (default: data/ beside the app)"
    )
    parser.add_argument("--no-refresh", action="store_true", help="Start with cached data only")
    args = parser.parse_args()
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

        def scheduled():
            while True:
                time.sleep(900)
                market.refresh()

        threading.Thread(target=scheduled, daemon=True).start()

        def scheduled_quotes():
            while True:
                time.sleep(60)
                market.refresh_quotes()

        threading.Thread(target=scheduled_quotes, daemon=True).start()
    if args.open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSwing Signal stopped. Your work is saved.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
