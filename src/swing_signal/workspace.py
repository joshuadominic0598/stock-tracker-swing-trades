"""Validated edits and exports for the user's private workspace."""

import math
import re
from datetime import date

from swing_signal.data import market, storage

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

def add_asset(body):
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
    return dict(ok=True, symbol=symbol)

def save_zone(asset, body):
    symbol = asset["symbol"]
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

def delete_zone(asset, body):
    symbol = asset["symbol"]
    storage.write(
        "DELETE FROM zones WHERE id=? AND symbol=?",
        (int(body["id"]), symbol),
    )

def save_position(asset, body):
    symbol = asset["symbol"]
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

def save_journal(asset, body):
    symbol = asset["symbol"]
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

def export():
    tables = ("assets", "zones", "positions", "journal", "cache")
    snapshot = {table: storage.rows("SELECT * FROM " + table) for table in tables}
    return dict(version=1, exported_at=market.now(), data=snapshot)
