import unittest
from datetime import date, timedelta

from swing_signal.analysis.indicators import enrich
from swing_signal.analysis.patterns import support_retest
from swing_signal.analysis.signals import assess
from swing_signal.data.market import long_candidates

def sample(values):
    return enrich(
        [
            dict(
                time=str(date(2025, 1, 1) + timedelta(days=i)),
                open=values[i - 1] if i else v - 0.2,
                high=max(v, values[i - 1] if i else v) + 0.6,
                low=min(v, values[i - 1] if i else v) - 0.6,
                close=v,
                volume=100,
            )
            for i, v in enumerate(values)
        ]
    )

def pattern_data():
    # Decline, first trough, intervening rally, second trough, strong rebound.
    values = [100 + i * 0.5 for i in range(60)] + [
        128,
        124,
        120,
        116,
        115,
        117,
        120,
        125,
        127,
        124,
        120,
        117,
        115.5,
        117,
        122,
        128,
        140,
        144,
    ]
    data = sample(values)
    return enrich(data)

class RetestTests(unittest.TestCase):
    def test_retest_confirmation_needs_breakout_strong_response_and_upward_trend(self):
        p = support_retest(pattern_data())
        self.assertEqual(p["status"], "confirmed", p)
        self.assertTrue(p["trend_up"])
        self.assertLess(p["first_low"]["time"], p["second_low"]["time"])
        self.assertGreaterEqual(p["confirmed_at"], p["second_low"]["time"])
        signal = next(x for x in assess(pattern_data(), [])["signals"] if x["key"] == "retest")
        self.assertEqual(signal["score"], 1)
        self.assertEqual(len(assess(pattern_data(), [])["signals"]), 8)

    def test_prefixes_do_not_show_a_confirmation_from_future_candles(self):
        data = pattern_data()
        for end in range(65, 75):
            self.assertNotEqual(support_retest(data[:end])["status"], "confirmed")

    def test_flat_floor_touches_do_not_become_a_rebound_pattern(self):
        self.assertEqual(support_retest(sample([100] * 80))["status"], "none")

    def test_materially_different_second_low_does_not_match_same_floor(self):
        data = pattern_data()
        data[72]["low"] = 100
        data[72]["close"] = 101
        self.assertNotEqual(support_retest(enrich(data))["status"], "confirmed")

    def test_later_close_through_support_invalidates_a_previously_confirmed_pattern(
        self,
    ):
        data = pattern_data()
        last = data[-1]
        for i in range(1, 4):
            data.append(
                dict(
                    time=str(date.fromisoformat(last["time"]) + timedelta(days=i)),
                    open=100,
                    high=102,
                    low=98,
                    close=99,
                    volume=100,
                )
            )
        p = support_retest(enrich(data))
        self.assertEqual(p["status"], "failed", p)

    def test_rebound_without_broader_uptrend_remains_unconfirmed(self):
        data = pattern_data()
        for b in data:
            b.update(sma20=140, sma50=150)
        self.assertNotEqual(support_retest(data)["status"], "confirmed")

    def test_old_rebound_is_not_presented_as_a_fresh_trigger(self):
        data = pattern_data()
        last = date.fromisoformat(data[-1]["time"])
        for i in range(1, 8):
            data.append(
                dict(
                    time=str(last + timedelta(days=i)),
                    open=136,
                    high=137,
                    low=135,
                    close=136,
                    volume=100,
                )
            )
        self.assertNotEqual(support_retest(enrich(data))["status"], "confirmed")

class CandidateTests(unittest.TestCase):
    def asset(self, symbol, positives=1, negatives=0, **extra):
        items = [
            dict(key="rsi" + str(i), score=1, title="Rising", value="up") for i in range(positives)
        ] + [
            dict(key="risk" + str(i), score=-1, title="Falling", value="down")
            for i in range(negatives)
        ]
        reading = dict(
            direction="bullish" if positives - negatives >= 2 else "neutral",
            score=positives - negatives,
            coverage=8,
            signals=items,
            label="Fixture",
            retest=dict(status="none"),
        )
        return dict(
            symbol=symbol,
            available=True,
            stale=False,
            quality_note=None,
            daily_swing=reading,
            weekly_swing=reading,
            **extra,
        )

    def test_any_positive_condition_qualifies_but_stale_and_incomplete_data_do_not(
        self,
    ):
        a = self.asset("ONE")
        b = self.asset("STALE")
        b["stale"] = True
        c = self.asset("GAP")
        c["quality_note"] = "Missing candles"
        out = long_candidates([a, b, c, self.asset("NONE", 0)])
        self.assertEqual([v["symbol"] for v in out["items"]], ["ONE"])
        self.assertEqual(out["excluded"], 2)

    def test_balanced_evidence_ranks_before_a_lone_positive_with_counterpoints(self):
        out = long_candidates([self.asset("CONFLICT", 1, 3), self.asset("ALIGNED", 3, 0)])
        self.assertEqual([v["symbol"] for v in out["items"]], ["ALIGNED", "CONFLICT"])
        self.assertEqual(len(out["items"][1]["counterpoints"]), 3)

if __name__ == "__main__":
    unittest.main()
