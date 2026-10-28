import unittest
from datetime import date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app import market
from app.indicators import enrich, rsi, sma
from app.signals import assess, period_trend


class YahooSessionTests(unittest.TestCase):
    def raw(self, day=None, count=7, zero=False):
        day = day or date.today() - timedelta(days=2)
        z = ZoneInfo("Asia/Kolkata")
        stamps = [
            int((datetime.combine(day, time(9, 15), z) + timedelta(hours=i)).timestamp())
            for i in range(count)
        ]
        q = {k: [] for k in ("open", "high", "low", "close", "volume")}
        for i in range(count):
            for k, v in dict(
                open=100 + i,
                high=102 + i,
                low=99 + i,
                close=101 + i,
                volume=0 if zero and i == 0 else 10,
            ).items():
                q[k].append(v)
        return {"chart": {"result": [dict(timestamp=stamps, indicators={"quote": [q]})]}}, str(day)

    def test_complete_yahoo_session_preserves_reported_daily_volume_when_available(
        self,
    ):
        raw, day = self.raw(zero=True)
        with patch("app.market.get_json", return_value=raw):
            out = market.yahoo_recent_days("TCS.NS", [day], ZoneInfo("Asia/Kolkata"), {day: 9876})
        self.assertEqual(out[day]["open"], 100)
        self.assertEqual(out[day]["close"], 107)
        self.assertEqual(out[day]["volume"], 9876)
        self.assertEqual(out[day]["volume_basis"], "Yahoo daily reported volume")

    def test_incomplete_or_invalid_hour_set_cannot_fabricate_a_daily_bar(self):
        for count in (6, 8):
            raw, day = self.raw(count=count)
            if count == 8:
                raw["chart"]["result"][0]["timestamp"][-1] = raw["chart"]["result"][0]["timestamp"][
                    0
                ]
            with patch("app.market.get_json", return_value=raw):
                out = market.yahoo_recent_days("TCS.NS", [day], ZoneInfo("Asia/Kolkata"))
            self.assertEqual(out, {})
        raw, day = self.raw()
        raw["chart"]["result"][0]["indicators"]["quote"][0]["close"][3] = None
        with patch("app.market.get_json", return_value=raw):
            self.assertEqual(
                market.yahoo_recent_days("TCS.NS", [day], ZoneInfo("Asia/Kolkata")), {}
            )

    def test_zero_traded_volume_with_a_price_range_needs_reported_daily_volume(self):
        raw, day = self.raw(zero=True)
        with patch("app.market.get_json", return_value=raw):
            self.assertEqual(
                market.yahoo_recent_days("TCS.NS", [day], ZoneInfo("Asia/Kolkata")), {}
            )

    def test_current_unfinished_session_is_not_recovered(self):
        z = ZoneInfo("Asia/Kolkata")
        fixed = datetime(2026, 10, 23, 14, tzinfo=z)
        raw, day = self.raw(fixed.date())

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)

        with (
            patch("app.market.get_json", return_value=raw),
            patch("app.market.datetime", Clock),
        ):
            self.assertEqual(market.yahoo_recent_days("TCS.NS", [day], z), {})


class TrendAndRSITests(unittest.TestCase):
    def test_net_uptrend_can_be_yes_with_a_red_latest_candle_below_recent_high(self):
        values = [100 + i for i in range(40)]
        values[-1] = values[-2] - 0.5
        bars = enrich(
            [
                dict(
                    time=str(date(2026, 8, 1) + timedelta(days=i)),
                    open=v + 0.2,
                    high=v + 0.5,
                    low=v - 0.5,
                    close=v,
                    volume=100,
                )
                for i, v in enumerate(values)
            ]
        )
        result = assess(bars, [])
        self.assertTrue(result["period_trend"]["7"]["rising"])
        self.assertTrue(result["period_trend"]["14"]["rising"])
        self.assertFalse(result["highs"]["7"]["reached"])
        item = next(s for s in result["signals"] if s["key"] == "highs")
        self.assertEqual(item["score"], 1)
        self.assertIn("7D: Yes", item["value"])
        self.assertIn("14D: Yes", item["value"])

    def test_rsi_15_and_14_period_smoothing_are_separate_from_stoch_rsi_14(self):
        values = [100 + i * 0.2 + (-1) ** i for i in range(80)]
        bars = [
            dict(
                time=str(date(2026, 7, 1) + timedelta(days=i)),
                open=v,
                high=v + 0.5,
                low=v - 0.5,
                close=v,
                volume=100,
            )
            for i, v in enumerate(values)
        ]
        out = enrich(bars)
        self.assertAlmostEqual(out[-1]["rsi"], rsi(values, 15)[-1])
        self.assertAlmostEqual(out[-1]["rsi_average"], sma(rsi(values, 15), 14)[-1])
        self.assertAlmostEqual(out[-1]["rsi14"], rsi(values, 14)[-1])

    def test_weekly_trend_is_measured_in_weeks_and_requires_a_baseline(self):
        bars = [
            dict(time=str(date(2025, 1, 6) + timedelta(weeks=i)), close=100 + i) for i in range(20)
        ]
        self.assertTrue(period_trend(bars, 14, calendar=False)["rising"])
        self.assertFalse(period_trend(bars[:10], 14, calendar=False)["available"])


if __name__ == "__main__":
    unittest.main()
