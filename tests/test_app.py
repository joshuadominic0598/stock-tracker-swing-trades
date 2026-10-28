import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from swing_signal.data import market, storage
from swing_signal.http.server import Handler

class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.original = storage.DB_PATH
        storage.DB_PATH = Path(cls.directory.name) / "test.sqlite3"
        storage.init()
        cls.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.http.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        storage.DB_PATH = cls.original
        cls.directory.cleanup()

    def post(self, path, body, origin=None):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        request = urllib.request.Request(
            self.base + "/api/" + path, data=json.dumps(body).encode(), headers=headers
        )
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def test_new_workspace_has_a_watchlist_without_assumed_holdings(self):
        storage.init()
        self.assertEqual(len(storage.rows("SELECT * FROM assets")), 55)
        self.assertEqual(len(storage.rows("SELECT * FROM assets WHERE held=1")), 0)

    def test_initialization_preserves_existing_holdings(self):
        storage.write("UPDATE assets SET held=1 WHERE symbol='ASIANPAINT'")
        try:
            storage.init()
            self.assertEqual(storage.asset("ASIANPAINT")["held"], 1)
        finally:
            storage.write("UPDATE assets SET held=0 WHERE symbol='ASIANPAINT'")

    def test_non_local_hostname_cannot_read_private_endpoints(self):
        request = urllib.request.Request(
            self.base + "/api/backup", headers={"Host": "untrusted.example"}
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code, 403)

    def test_post_requires_a_json_object(self):
        status, body = self.post("connections", [])
        self.assertEqual(status, 400)
        self.assertIn("JSON object", body["error"])

    def test_failed_workspace_transaction_rolls_back_and_releases_connection(self):
        import sqlite3

        before = storage.asset("ASIANPAINT")["held"]
        with self.assertRaisesRegex(RuntimeError, "cancel"):
            with storage.connect() as db:
                db.execute("UPDATE assets SET held=1 WHERE symbol='ASIANPAINT'")
                raise RuntimeError("cancel")
        self.assertEqual(storage.asset("ASIANPAINT")["held"], before)
        with self.assertRaises(sqlite3.ProgrammingError):
            db.execute("SELECT 1")

    def test_zone_validation_and_persistence(self):
        status, _ = self.post("assets/ASIANPAINT/zone", dict(kind="demand", low=2200, high=2100))
        self.assertEqual(status, 400)
        status, _ = self.post(
            "assets/ASIANPAINT/zone",
            dict(kind="demand", low=2100, high=2200, label="Weekly base"),
        )
        self.assertEqual(status, 200)
        zone = storage.rows("SELECT * FROM zones WHERE symbol=?", ("ASIANPAINT",))[-1]
        self.assertEqual(zone["label"], "Weekly base")
        status, _ = self.post(
            "assets/ASIANPAINT/zone",
            dict(id=zone["id"], kind="demand", low=2110, high=2210, label="Edited base"),
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            storage.rows("SELECT low FROM zones WHERE id=?", (zone["id"],))[0]["low"],
            2110,
        )
        self.post("assets/ASIANPAINT/delete-zone", dict(id=zone["id"]))
        self.assertFalse(storage.rows("SELECT * FROM zones WHERE id=?", (zone["id"],)))

    def test_journal_can_be_saved_and_reopened(self):
        status, _ = self.post(
            "assets/ASIANPAINT/journal",
            dict(
                thesis="Test thesis",
                invalidation="Weekly break",
                horizon="1–3 months",
                review_date="2026-11-01",
            ),
        )
        self.assertEqual(status, 200)
        storage.init()
        note = storage.rows("SELECT * FROM journal WHERE symbol=?", ("ASIANPAINT",))[0]
        self.assertEqual(note["thesis"], "Test thesis")
        self.assertEqual(note["review_date"], "2026-11-01")

    def test_positions_require_both_fields_and_reject_nonfinite(self):
        self.assertEqual(
            self.post("assets/COALINDIA/position", dict(quantity=10, average=""))[0],
            400,
        )
        self.assertEqual(
            self.post("assets/COALINDIA/position", dict(quantity="nan", average=100))[0],
            400,
        )
        self.assertEqual(
            self.post("assets/COALINDIA/position", dict(quantity=10, average=300, held=True))[0],
            200,
        )
        self.assertEqual(
            storage.rows("SELECT * FROM positions WHERE symbol=?", ("COALINDIA",))[0]["quantity"],
            10,
        )

    def test_removed_price_history_upload_routes_cannot_change_saved_history(self):
        saved = dict(
            bars=[
                dict(
                    time="2026-10-20",
                    open=100,
                    high=105,
                    low=99,
                    close=103,
                    volume=1000,
                )
            ],
            source="Yahoo Finance",
        )
        storage.cache_set("price:ASIANPAINT", saved, market.now())
        for action in ("import", "resume-provider"):
            with self.subTest(action=action):
                status, _ = self.post(
                    "assets/ASIANPAINT/" + action,
                    dict(csv="date,open,high,low,close,volume"),
                )
                self.assertEqual(status, 404)
                self.assertEqual(storage.cache_get("price:ASIANPAINT")["value"], saved)

    def test_provider_refresh_is_not_pinned_by_legacy_uploaded_history(self):
        legacy = dict(bars=[dict(time="2026-10-20", close=100)], source="Your CSV import")
        current = dict(bars=[dict(time="2026-10-21", close=101)], source="Yahoo Finance")
        storage.cache_set("price:ASIANPAINT", legacy, market.now())
        with patch("swing_signal.data.market.yahoo", return_value=current) as fetch:
            market.fetch_asset(storage.asset("ASIANPAINT"))
        fetch.assert_called_once_with("ASIANPAINT.NS")
        self.assertEqual(storage.cache_get("price:ASIANPAINT")["value"], current)

    def test_cross_origin_mutations_are_rejected(self):
        status, _ = self.post(
            "assets/ASIANPAINT/journal",
            dict(thesis="Should not write"),
            origin="https://example.org",
        )
        self.assertEqual(status, 403)

    def test_missing_source_does_not_produce_synthetic_history(self):
        detail = market.asset_detail(storage.asset("HCG"))
        self.assertFalse(detail["available"])
        self.assertEqual(detail["bars"], [])
        self.assertEqual(detail["summary"], {})

    def test_failed_fetch_preserves_good_cache(self):
        value = dict(
            bars=[
                dict(
                    time="2026-10-20",
                    open=100,
                    high=105,
                    low=99,
                    close=103,
                    volume=1000,
                )
            ],
            source="Yahoo Finance",
        )
        storage.cache_set("price:COALINDIA", value, market.now())
        with patch("swing_signal.data.market.yahoo", side_effect=OSError("Source down")):
            with self.assertRaises(OSError):
                market.fetch_asset(storage.asset("COALINDIA"))
        self.assertEqual(storage.cache_get("price:COALINDIA")["value"], value)

    def test_older_provider_history_cannot_replace_newer_cache(self):
        old = dict(bars=[dict(time="2026-10-22", close=100)], source="Yahoo Finance")
        storage.cache_set("price:HDFCBANK", old, market.now())
        incoming = dict(bars=[dict(time="2026-10-21", close=90)], source="Yahoo Finance")
        with self.assertRaisesRegex(ValueError, "retained cached"):
            market.save_price("price:HDFCBANK", incoming)
        self.assertEqual(storage.cache_get("price:HDFCBANK")["value"], old)

    def test_model_connection_check_has_a_dedicated_endpoint(self):
        with patch(
            "swing_signal.ai.providers.check_connection",
            return_value=dict(ok=True, provider="openai", model="gpt-5-mini"),
        ) as check:
            status, result = self.post(
                "connections/check", dict(provider="openai", model="gpt-5-mini")
            )
            self.assertEqual(status, 200)
            self.assertTrue(result["ok"])
            check.assert_called_once_with("openai", "gpt-5-mini")

    def test_removed_broker_routes_are_unavailable(self):
        for path in (
            "/api/hdfcsky/login",
            "/api/hdfcsky/callback?request_token=fixture",
        ):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(self.base + path)
            self.assertEqual(caught.exception.code, 404)

    def test_google_trends_import_is_available_for_a_tracked_stock(self):
        text = "Day,HCG share price: (India)\n" + "\n".join(
            str(date.today() - timedelta(days=i)) + ",20" for i in range(14, 0, -1)
        )
        status, value = self.post("assets/HCG/trends-import", dict(csv=text))
        self.assertEqual(status, 200)
        self.assertEqual(value["unit"], "Relative search interest (0–100)")
        self.assertTrue(storage.cache_get("trends:HCG"))
        self.assertEqual(self.post("assets/HCG/trends-import", dict(csv="invalid"))[0], 400)

    def test_unknown_asset_and_path_traversal(self):
        for path in ("/api/assets/NOTHERE", "/../launch.py"):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(self.base + path)
            self.assertEqual(ctx.exception.code, 404)

if __name__ == "__main__":
    unittest.main()
