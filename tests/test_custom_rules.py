"""Behavior checks for the user's pullback and demand-led shortlist."""

import unittest
from datetime import date, timedelta

from app.indicators import enrich, weekly
from app.market import long_candidates
from app.signals import assess


def history(values):
    return enrich(
        [
            dict(
                time=str(date(2025, 1, 1) + timedelta(days=i)),
                open=c,
                high=c + 1,
                low=c - 1,
                close=c,
                volume=100,
            )
            for i, c in enumerate(values)
        ]
    )


def signal(reading, key):
    return next(x for x in reading["signals"] if x["key"] == key)


class CustomRulesTests(unittest.TestCase):
    def test_rsi_recovery_needs_strict_dip_reclaim_and_current_rise(self):
        data = history([100] * 220)
        data[-10]["rsi"] = 34.9
        data[-2]["rsi"] = 39
        data[-1]["rsi"] = 40.1
        self.assertEqual(signal(assess(data, []), "rsi")["score"], 1)
        data[-1]["rsi"] = 40
        self.assertNotEqual(signal(assess(data, []), "rsi")["score"], 1)
        data[-1]["rsi"] = 41
        data[-10]["rsi"] = 35
        self.assertFalse(assess(data, [])["rsi_recovery"])
        data[-10]["rsi"] = 34
        data[-2]["rsi"] = 42
        self.assertFalse(assess(data, [])["rsi_recovery"])

    def test_rsi_dip_must_precede_the_current_bar_and_be_recent(self):
        data = history([100] * 220)
        data[-32]["rsi"] = 20
        data[-2]["rsi"] = 39
        data[-1]["rsi"] = 41
        self.assertFalse(assess(data, [])["rsi_recovery"])
        data[-31]["rsi"] = 20
        self.assertTrue(assess(data, [])["rsi_recovery"])

    def test_stoch_low_or_falling_is_green_even_below_d(self):
        data = history([100] * 220)
        data[-2].update(k=10, d=30)
        data[-1].update(k=20, d=40)
        self.assertEqual(signal(assess(data, []), "stoch")["score"], 1)
        data[-2]["k"] = 75
        data[-1]["k"] = 70
        out = signal(assess(data, []), "stoch")
        self.assertEqual(out["score"], 1)
        self.assertIn("falling", out["reading"])
        data[-2]["k"] = 60
        data[-1].update(k=70, d=40)
        self.assertEqual(signal(assess(data, []), "stoch")["score"], 0)

    def test_positive_three_day_move_qualifies_despite_negative_longer_windows(self):
        data = history([120] * 217 + [100, 101, 102, 103])
        out = assess(data, [])
        self.assertTrue(out["period_trend"]["3"]["rising"])
        self.assertFalse(out["period_trend"]["7"]["rising"])
        self.assertFalse(out["period_trend"]["14"]["rising"])
        self.assertEqual(signal(out, "highs")["score"], 1)
        self.assertIn("3D", signal(out, "highs")["title"])

    def test_below_daily_200_sma_is_green_in_both_timeframes(self):
        daily = history([100] * 219 + [80])
        expected = sum(x["close"] for x in daily[-200:]) / 200
        for out in (assess(daily, []), assess(enrich(weekly(daily)), [], "1w", daily)):
            self.assertAlmostEqual(out["daily_ma200"], expected)
            self.assertEqual(signal(out, "ma")["score"], 1)
            self.assertAlmostEqual(out["gap_to_200d_pct"], 100 * (expected / 80 - 1))
        self.assertIsNone(assess(enrich(weekly(daily)), [], "1w")["daily_ma200"])
        daily[-1]["close"] = 101
        self.assertEqual(signal(assess(daily, []), "ma")["score"], 0)

    def test_broken_or_below_demand_does_not_match_but_near_supply_does_not_cancel(
        self,
    ):
        data = history([100] * 220)
        demand = dict(kind="demand", low=99, high=101)
        out = assess(data, [demand, dict(kind="supply", low=101, high=102)])
        self.assertEqual(signal(out, "zones")["score"], 1)
        self.assertTrue(any("supply" in w for w in out["warnings"]))
        self.assertFalse(assess(data, [dict(demand, broken=True)])["near_demand"])
        self.assertFalse(assess(data, [dict(demand, low=101, high=102)])["near_demand"])

    def asset(self, symbol, keys, coverage=8, **flags):
        signals = [dict(key=k, title=k, value="match", reading="match", score=1) for k in keys]
        reading = dict(
            signals=signals,
            coverage=coverage,
            direction="neutral" if coverage >= 5 else "unavailable",
            score=len(keys),
            warnings=["Risk remains"],
        )
        return dict(
            symbol=symbol,
            available=True,
            stale=False,
            quality_note=None,
            daily_swing=reading,
            weekly_swing=reading,
            **flags,
        )

    def test_green_demand_automatically_qualifies_with_limited_components(self):
        asset = self.asset("DEMAND", ["zones"], 1)
        out = long_candidates([asset, self.asset("OTHER", ["rsi"], 1)])
        self.assertEqual([c["symbol"] for c in out["items"]], ["DEMAND"])
        asset["stale"] = True
        self.assertFalse(long_candidates([asset])["items"])
        asset["stale"] = False
        asset["quality_note"] = "Missing latest session"
        self.assertFalse(long_candidates([asset])["items"])

    def test_demand_confluence_ranks_ahead_of_unrelated_green_counts(self):
        assets = [
            self.asset("OTHER", ["rsi", "stoch", "ma", "volume", "retest"]),
            self.asset("DEMAND", ["zones"]),
            self.asset("TREND", ["zones", "highs"]),
            self.asset("MOVE", ["zones", "move"]),
            self.asset("BOTH", ["zones", "highs", "move"]),
        ]
        out = long_candidates(assets)["items"]
        self.assertEqual(out[0]["symbol"], "BOTH")
        self.assertEqual({c["symbol"] for c in out[1:3]}, {"TREND", "MOVE"})
        self.assertEqual([c["symbol"] for c in out[3:]], ["DEMAND", "OTHER"])
        self.assertEqual(out[0]["priority"], 3)
        self.assertEqual(out[0]["score"], 3)  # No additional points for the same confluence.
        self.assertEqual(out[0]["warnings"], ["Risk remains"])

    def test_overall_scores_are_bounded_ranked_and_explainable(self):
        assets = [
            self.asset("DEMAND", ["zones"]),
            self.asset("BOTH", ["zones", "highs", "move"]),
            self.asset("OTHER", ["rsi", "stoch", "ma", "volume", "retest"]),
        ]
        scan = long_candidates(assets)["items"]
        self.assertEqual([c["symbol"] for c in scan], ["BOTH", "DEMAND", "OTHER"])
        self.assertEqual([c["rank"] for c in scan], [1, 2, 3])
        scores = [c["overall_score"] for c in scan]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for c in scan:
            self.assertTrue(0 <= c["overall_score"] <= 100)
            self.assertAlmostEqual(
                c["overall_score"], sum(c["score_breakdown"].values()), delta=0.051
            )
        risk = self.asset("RISK", ["zones"])
        risk["daily_swing"]["score"] = -5
        self.assertLess(
            long_candidates([risk])["items"][0]["overall_score"],
            scan[1]["overall_score"],
        )

    def test_exact_one_percent_does_not_receive_demand_move_boost(self):
        data = history([100] * 219 + [101])
        zones = [dict(kind="demand", low=99, high=100)]
        a = dict(
            symbol="ONE",
            available=True,
            stale=False,
            quality_note=None,
            daily_swing=assess(data, zones),
        )
        self.assertNotIn("move", [s["key"] for s in long_candidates([a])["items"][0]["matched"]])
        data[-1]["close"] = 101.01
        a["daily_swing"] = assess(data, zones)
        self.assertIn("move", [s["key"] for s in long_candidates([a])["items"][0]["matched"]])


if __name__ == "__main__":
    unittest.main()
