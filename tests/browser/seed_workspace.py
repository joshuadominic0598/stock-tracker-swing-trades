"""Deterministic illustrative candles for offline UI tests; never production data."""

import argparse
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app import storage  # noqa: E402


def seed(folder):
    folder = folder.resolve()
    if not folder.is_relative_to(ROOT / ".tmp"):
        raise ValueError("Browser fixtures must use the repository's ignored .tmp directory")
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("signaldesk.sqlite3", "signaldesk.sqlite3-wal", "signaldesk.sqlite3-shm"):
        (folder / name).unlink(missing_ok=True)
    storage.DB_PATH = folder / "signaldesk.sqlite3"
    storage.init()
    stamp = datetime.now(timezone.utc).isoformat()
    end = date.today() - timedelta(days=1)
    for index, asset in enumerate(storage.rows("SELECT * FROM assets ORDER BY symbol")):
        values = []
        base = 80 + index * 13
        for i in range(300):
            trend = i * 0.06 + math.sin(i / 11) * 5
            rebound = max(0, i - 285) * 0.6
            pullback = max(0, i - 294) * 0.9 if index % 3 == 1 else 0
            close = base + trend + rebound - pullback
            if i == 299 and index % 5 == 0:
                close *= 1.025
            values.append(
                dict(
                    time=str(end - timedelta(days=299 - i)),
                    open=close - 0.4,
                    high=close + 1.2,
                    low=close - 1.1,
                    close=close,
                    volume=(100000 + i * 100) * (1.5 if i == 299 and index % 2 == 0 else 1),
                )
            )
        price = values[-1]["close"]
        storage.cache_set(
            "price:" + asset["symbol"],
            dict(
                bars=values,
                source="Illustrative sample data",
                source_url="",
                provider_symbol=asset["symbol"],
                currency="INR"
                if asset["market"] == "NSE"
                else "USD"
                if asset["market"] == "US"
                else "USDT",
                events=[],
                as_of=stamp,
                fetched_at=stamp,
                methodology="Synthetic UI fixture; not actual market prices.",
            ),
            stamp,
        )
        storage.write(
            "INSERT INTO zones (symbol,kind,low,high,label,created_at) VALUES (?,?,?,?,?,?)",
            (asset["symbol"], "demand", price * 0.97, price * 0.99, "Sample demand band", stamp),
        )
    storage.cache_set("migration:browser-demo", True, stamp)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    seed(parser.parse_args().data_dir)
