import json
import sqlite3
from contextlib import contextmanager

from swing_signal.config import ADDITIONS, ASSETS, CONSUMER_ADDITIONS
from swing_signal.paths import DATA_DIR

DB_PATH = DATA_DIR / "signaldesk.sqlite3"

@contextmanager
def connect():
    """Commit/rollback the transaction and always release the workspace file handle."""
    db = sqlite3.connect(str(DB_PATH), timeout=20)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        with db:
            yield db
    finally:
        db.close()

def init():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS assets (
          symbol TEXT PRIMARY KEY, name TEXT NOT NULL, market TEXT NOT NULL,
          sector TEXT NOT NULL, held INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS cache (
          key TEXT PRIMARY KEY, value TEXT NOT NULL, fetched_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS zones (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          symbol TEXT NOT NULL REFERENCES assets(symbol), kind TEXT NOT NULL,
          low REAL NOT NULL, high REAL NOT NULL, label TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS positions (
          symbol TEXT PRIMARY KEY REFERENCES assets(symbol), quantity REAL, average REAL);
        CREATE TABLE IF NOT EXISTS journal (
          symbol TEXT PRIMARY KEY REFERENCES assets(symbol), thesis TEXT NOT NULL DEFAULT '',
          invalidation TEXT NOT NULL DEFAULT '', horizon TEXT NOT NULL DEFAULT '1–3 months',
          review_date TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL);
        """)
        db.executemany("INSERT OR IGNORE INTO assets VALUES (?,?,?,?,?)", ASSETS)
        seeded = db.execute("SELECT 1 FROM cache WHERE key='migration:swing-v2'").fetchone()
        if not seeded:
            db.executemany("INSERT OR IGNORE INTO assets VALUES (?,?,?,?,?)", ADDITIONS)
            db.execute(
                "INSERT INTO cache VALUES (?,?,?)",
                ("migration:swing-v2", "true", "2026-10-24T00:00:00+00:00"),
            )
        if not db.execute("SELECT 1 FROM cache WHERE key='migration:consumer-20261024'").fetchone():
            db.executemany("INSERT OR IGNORE INTO assets VALUES (?,?,?,?,?)", CONSUMER_ADDITIONS)
            db.execute(
                "INSERT INTO cache VALUES (?,?,?)",
                ("migration:consumer-20261024", "true", "2026-10-24T00:00:00+00:00"),
            )

def rows(sql, args=()):
    with connect() as db:
        return [dict(x) for x in db.execute(sql, args).fetchall()]

def write(sql, args=()):
    with connect() as db:
        cur = db.execute(sql, args)
        return cur.lastrowid

def cache_get(key):
    data = rows("SELECT * FROM cache WHERE key=?", (key,))
    if not data:
        return None
    return dict(value=json.loads(data[0]["value"]), fetched_at=data[0]["fetched_at"])

def cache_set(key, value, timestamp):
    write(
        "INSERT OR REPLACE INTO cache VALUES (?,?,?)",
        (key, json.dumps(value, allow_nan=False), timestamp),
    )

def asset(symbol):
    a = rows("SELECT * FROM assets WHERE symbol=?", (symbol,))
    return a[0] if a else None
