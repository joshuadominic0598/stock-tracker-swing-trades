import io
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from app import intelligence, market, settings, storage
from app.indicators import enrich, weekly
from app.signals import assess, financial_meanings, highs
from app.zones import discover


def bars(values, start=date(2025, 1, 1)):
    return [
        dict(
            time=str(start + timedelta(days=i)),
            open=c - 0.2,
            high=c + 0.5,
            low=c - 0.5,
            close=c,
            volume=100,
        )
        for i, c in enumerate(values)
    ]


class SwingTests(unittest.TestCase):
    def test_exactly_one_percent_is_not_more_than_one(self):
        data = enrich(bars([100] * 60 + [101]))
        s = assess(data, [])
        self.assertFalse(s["up_over_one"])
        self.assertEqual(next(x for x in s["signals"] if x["key"] == "move")["score"], 0)
        data[-1]["close"] = 101.01
        self.assertTrue(assess(data, [])["up_over_one"])

    def test_volume_confirms_the_direction_of_close_not_candle_colour(self):
        data = enrich(bars([100] * 60 + [98]))
        data[-1].update(volume_ratio=2, open=97)
        self.assertEqual(
            next(x for x in assess(data, [])["signals"] if x["key"] == "volume")["score"],
            -1,
        )

    def test_high_touch_is_not_a_closing_breakout(self):
        data = bars([100] * 40)
        data[-1].update(high=110, close=100)
        h = highs(data)["14"]
        self.assertTrue(h["reached"])
        self.assertFalse(h["breakout"])
        self.assertFalse(h["at_high"])
        data[-1]["close"] = 109
        self.assertTrue(highs(data)["14"]["breakout"])

    def test_daily_windows_use_calendar_days_not_seven_sessions(self):
        data = bars([100] * 20)
        data[-8]["high"] = 200
        h = highs(data)
        self.assertEqual(h["7"]["high"], 100.5)
        self.assertEqual(h["14"]["high"], 200)

    def test_weekly_high_windows_retain_daily_context(self):
        daily = bars([100 + i * 0.1 for i in range(250)])
        weeks = enrich(weekly(daily))
        s = assess(weeks, [], "1w", daily)
        self.assertEqual(s["daily_highs"], highs(daily))
        self.assertEqual(s["highs"]["7"]["samples"], 7)
        self.assertIn("7W", next(x for x in s["signals"] if x["key"] == "highs")["title"])

    def test_flat_price_does_not_get_buy_side_for_tying_a_high(self):
        s = assess(enrich(bars([100] * 250)), [])
        self.assertEqual(s["score"], 0)
        self.assertEqual(s["label"], "Mixed / wait")

    def test_short_history_has_no_directional_rating(self):
        s = assess(enrich(bars([100, 101, 102])), [])
        self.assertEqual(s["direction"], "unavailable")
        self.assertLess(s["coverage"], 5)

    def test_nearby_supply_warns_without_cancelling_demand_match(self):
        s = assess(
            enrich(bars([100] * 60)),
            [
                dict(kind="demand", low=98, high=99),
                dict(kind="supply", low=101, high=102),
            ],
        )
        zone = next(x for x in s["signals"] if x["key"] == "zones")
        self.assertEqual(zone["score"], 1)
        self.assertTrue(any("supply" in w for w in s["warnings"]))

    def test_financial_meanings_keep_periods_currency_and_bank_context(self):
        data = {
            "TotalDebt": [
                dict(date="2025-03-31", value=100, currency="INR"),
                dict(date="2026-03-31", value=120, currency="INR"),
            ],
            "NetIncome": [
                dict(date="2023-03-31", value=10, currency="INR"),
                dict(date="2026-03-31", value=20, currency="INR"),
            ],
        }
        results = {x["metric"]: x for x in financial_meanings(data, "Banking")}
        self.assertEqual(results["TotalDebt"]["direction"], "context")
        self.assertIn("banks", results["TotalDebt"]["price_implication"])
        self.assertIsNone(results["NetIncome"]["yoy"])
        data["NetIncome"][0]["date"] = "2025-03-31"
        data["NetIncome"][0]["currency"] = "USD"
        self.assertIsNone(financial_meanings(data)[1]["yoy"])

    def test_confirmed_departure_and_later_invalidation(self):
        data = bars([100] * 40)
        for b in data:
            b.update(open=100, close=100, low=99.5, high=100.5)
        data += bars([103, 105, 106, 107, 108], start=date(2025, 2, 10))
        data[40].update(open=100, low=99.8, high=103.5)
        ready = enrich(data)
        candidates = discover(ready)
        zone = next(
            z
            for z in candidates
            if z["kind"] == "demand" and z["label"] == "Base + strong departure"
        )
        self.assertGreaterEqual(zone["confirmed_at"], zone["origin"])
        broken = data + bars([95, 105, 106], start=date(2025, 2, 15))
        self.assertFalse(
            any(
                z["kind"] == "demand" and z["low"] <= 100 <= z["high"]
                for z in discover(enrich(broken))
            )
        )
        before = enrich(data[:40])
        self.assertFalse(
            any(
                z["label"] == "Base + strong departure" and z["kind"] == "demand"
                for z in discover(before)
            )
        )


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = storage.DB_PATH
        storage.DB_PATH = Path(self.tmp.name) / "workspace.sqlite3"
        storage.init()
        market.ANALYSIS_CACHE.clear()

    def tearDown(self):
        storage.DB_PATH = self.original
        self.tmp.cleanup()
        market.ANALYSIS_CACHE.clear()

    def test_newer_quote_wins_across_timezone_representations(self):
        market.save_quote("HCG", dict(price=100, as_of="2026-10-23T15:30:00+05:30"))
        market.save_quote("HCG", dict(price=101, as_of="2026-10-23T10:01:00+00:00"))
        market.save_quote("HCG", dict(price=99, as_of="2026-10-23T15:29:00+05:30"))
        self.assertEqual(storage.cache_get("quote:HCG")["value"]["price"], 101)

    def test_incomplete_history_suspends_both_timeframe_leans(self):
        data = dict(
            bars=bars([100 + i * 0.1 for i in range(250)]),
            source="Fixture",
            source_url="",
            provider_symbol="HCG.NS",
            currency="INR",
            events=[],
            as_of=market.now(),
            fetched_at=market.now(),
            quality_note="Missing recent candle",
        )
        storage.cache_set("price:HCG", data, market.now())
        out = market.asset_detail(storage.asset("HCG"))
        self.assertEqual(out["daily_swing"]["label"], "Check data first")
        self.assertEqual(out["weekly_swing"]["direction"], "unavailable")

    def test_credentials_are_not_in_public_settings_or_cache_export(self):
        with patch.dict("os.environ", {}, clear=True):
            settings.update(dict(gemini_api_key="private-example"))
            self.assertTrue(settings.public()["gemini_api_key_configured"])
            self.assertNotIn("private-example", json.dumps(settings.public()))
            self.assertNotIn("private-example", json.dumps(storage.rows("SELECT * FROM cache")))
            if os.name != "nt":
                self.assertEqual(settings.path().stat().st_mode & 0o777, 0o600)
            settings.update(dict(gemini_api_key=""))
            self.assertEqual(settings.read()["gemini_api_key"], "private-example")
            settings.update(dict(clear_gemini_api_key=True))
            self.assertFalse(settings.public()["gemini_api_key_configured"])

    def test_us_prices_do_not_use_an_nse_suffix(self):
        data = dict(
            bars=bars([100] * 50),
            source="Yahoo Finance",
            provider_symbol="AAPL",
            as_of=market.now(),
        )
        with patch("app.market.yahoo", return_value=data) as fetch:
            market.fetch_asset(storage.asset("AAPL"))
        fetch.assert_called_once_with("AAPL")

    def test_nse_uses_yahoo_and_replaces_a_previous_source_once(self):
        old = dict(bars=bars([100, 101], date(2026, 10, 22)), source="Previous provider")
        incoming = dict(
            bars=bars([100, 99], date(2026, 10, 19)),
            source="Yahoo Finance",
            provider_symbol="HCG.NS",
            as_of=market.now(),
        )
        storage.cache_set("price:HCG", old, market.now())
        with patch("app.market.yahoo", return_value=incoming) as fetch:
            market.fetch_asset(storage.asset("HCG"))
        fetch.assert_called_once_with("HCG.NS")
        self.assertEqual(storage.cache_get("price:HCG")["value"]["source"], "Yahoo Finance")
        older = dict(incoming, bars=bars([100, 99], date(2026, 10, 17)))
        with self.assertRaisesRegex(ValueError, "older history"):
            market.save_price("price:HCG", older, allow_source_change=True)

    def test_removed_connection_settings_are_purged_without_losing_gemini(self):
        settings.path().write_text(
            json.dumps(
                dict(
                    gemini_api_key="keep-local",
                    gemini_model="gemini-2.5-flash",
                    nse_provider="removed",
                    hdfcsky_api_key="remove-local",
                    hdfcsky_access_token="remove-token",
                )
            )
        )
        with patch.dict("os.environ", {}, clear=True):
            settings.update({})
            self.assertEqual(settings.read()["gemini_api_key"], "keep-local")
            self.assertEqual(settings.public()["price_source"], "Yahoo Finance")
            self.assertFalse(
                any(
                    k.startswith(("hdfcsky", "kite", "upstox", "nse_provider"))
                    for k in json.loads(settings.path().read_text())
                )
            )

    def test_stock_search_only_returns_nse_results_and_marks_tracked(self):
        raw = dict(
            quotes=[
                dict(symbol="HCG.NS", shortname="Healthcare Global"),
                dict(symbol="HCG.BO"),
                dict(symbol="HCGS"),
                dict(symbol="NEW.NS", shortname="New company"),
            ]
        )
        with patch("app.market.get_json", return_value=raw) as request:
            out = market.search_catalog("HCG")
        self.assertEqual([r["symbol"] for r in out["results"]], ["HCG", "NEW"])
        self.assertTrue(out["results"][0]["tracked"])
        self.assertFalse(out["results"][1]["tracked"])
        self.assertIn("finance.yahoo.com", request.call_args[0][0])

    def test_consumer_group_tracks_requested_names_and_excludes_parle(self):
        from app.config import research_group

        for symbol in (
            "DRREDDY",
            "PRICOLLTD",
            "ASIANPAINT",
            "GILLETTE",
            "BRITANNIA",
            "HINDUNILVR",
            "PIDILITIND",
            "NESTLEIND",
        ):
            self.assertEqual(research_group(storage.asset(symbol)), "Consumer")
        self.assertIsNone(storage.asset("PARLEIND"))
        self.assertEqual(research_group(storage.asset("COLPAL")), "Consumer")

    def test_correlations_exclude_returns_spanning_different_missing_dates(self):
        a = bars([100 + i for i in range(100)])
        b = [r for i, r in enumerate(a) if i % 10 != 5]
        storage.cache_set("benchmark:NIFTY50", dict(bars=a), market.now())
        storage.cache_set("benchmark:SP500", dict(bars=b), market.now())
        pair = market.correlations()[0]
        self.assertEqual(pair["samples"], 60)
        self.assertAlmostEqual(pair["value"], 1)


class AIIntegrationTests(unittest.TestCase):
    def test_only_curated_models_are_exposed(self):
        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

        raw = json.dumps(
            dict(
                models=[
                    dict(name=n)
                    for n in [
                        "qwen3:8b",
                        "sprintlens-qwen3:8b",
                        "qwen2.5-coder:7b",
                        "deepseek-r1:8b",
                        "qwen3:14b",
                    ]
                ]
            )
        ).encode()
        with patch("urllib.request.urlopen", return_value=Response(raw)):
            self.assertEqual(intelligence.models()["models"], ["qwen3:8b", "qwen3:14b"])

    def test_gemini_sends_key_in_header_and_validates_fact_ids(self):
        source = dict(
            id="T1",
            as_of="2026-10-23",
            facts=dict(
                price=100,
                change=0,
                rsi=None,
                k=None,
                d=None,
                volume_ratio=None,
                distance=None,
                change_3d=None,
                change_20d=None,
            ),
        )
        selected = dict(
            summary=["T_CLOSE"],
            observations=["T_CLOSE"],
            counterpoints=["T_ZONE"],
            unknowns=["U_ZONE"],
            watch_next=["W_ZONE"],
        )
        raw = dict(candidates=[dict(content=dict(parts=[dict(text=json.dumps(selected))]))])

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

        with (
            patch("app.intelligence.models", return_value=dict(models=[])),
            patch(
                "app.settings.read",
                return_value=dict(
                    gemini_api_key="private-key", gemini_model="gemini-2.5-flash-lite"
                ),
            ),
            patch("app.intelligence.evidence_pack", return_value=[source]),
            patch(
                "urllib.request.urlopen",
                return_value=Response(json.dumps(raw).encode()),
            ) as call,
            patch("app.storage.cache_set"),
        ):
            result = intelligence.generate(
                dict(symbol="HCG", name="HCG", market="NSE"), "", "1d", "gemini"
            )
            req = call.call_args[0][0]
            self.assertNotIn("private-key", req.full_url)
            self.assertEqual(req.get_header("X-goog-api-key"), "private-key")
            self.assertIn("responseJsonSchema", json.loads(req.data)["generationConfig"])
            self.assertEqual(result["provider"], "gemini")
            self.assertIn("100.00", result["brief"]["summary"]["text"])
        selected["summary"] = ["INVENTED_BUY_CALL"]
        raw["candidates"][0]["content"]["parts"][0]["text"] = json.dumps(selected)
        with (
            patch("app.intelligence.models", return_value=dict(models=[])),
            patch(
                "app.settings.read",
                return_value=dict(
                    gemini_api_key="private-key", gemini_model="gemini-2.5-flash-lite"
                ),
            ),
            patch("app.intelligence.evidence_pack", return_value=[source]),
            patch(
                "urllib.request.urlopen",
                return_value=Response(json.dumps(raw).encode()),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "unsupported"):
                intelligence.generate(
                    dict(symbol="HCG", name="HCG", market="NSE"), "", "1d", "gemini"
                )


if __name__ == "__main__":
    unittest.main()
