import unittest
from datetime import date, timedelta

from swing_signal.analysis.indicators import candidate_zones, enrich, rsi, summarize, weekly

def candles(closes):
    start = date(2025, 1, 1)
    return [
        dict(
            time=str(start + timedelta(days=i)),
            open=c,
            high=c + 1,
            low=c - 1,
            close=c,
            volume=100,
        )
        for i, c in enumerate(closes)
    ]

class IndicatorTests(unittest.TestCase):
    def test_wilder_reference_example(self):
        # Wilder's common published 14-period example, independently rounded.
        prices = [
            44.34,
            44.09,
            44.15,
            43.61,
            44.33,
            44.83,
            45.10,
            45.42,
            45.84,
            46.08,
            45.89,
            46.03,
            45.61,
            46.28,
            46.28,
            46.00,
            46.03,
            46.41,
        ]
        result = rsi(prices)
        self.assertTrue(all(x is None for x in result[:14]))
        self.assertAlmostEqual(result[14], 70.4641, places=3)
        self.assertAlmostEqual(result[15], 66.2496, places=3)
        self.assertAlmostEqual(result[16], 66.4809, places=3)

    def test_rsi_zero_loss_gain_and_flat_prices(self):
        self.assertEqual(rsi([10] * 35)[-1], 50)
        self.assertEqual(rsi(list(range(1, 36)))[-1], 100)
        self.assertEqual(rsi(list(range(35, 0, -1)))[-1], 0)

    def test_short_history_remains_unknown(self):
        result = enrich(candles([100 + i for i in range(10)]))
        self.assertIsNone(result[-1]["rsi"])
        self.assertIsNone(result[-1]["k"])
        self.assertIsNone(result[-1]["sma50"])
        self.assertIsNone(result[-1]["volume_ratio"])

    def test_volume_baseline_excludes_current_bar(self):
        bars = candles([100] * 30)
        bars[-1]["volume"] = 200
        last = enrich(bars)[-1]
        self.assertEqual(last["volume_ratio"], 2)
        self.assertEqual(last["rsi"], 50)
        self.assertEqual(last["k"], 50)

    def test_stochastic_flat_rsi_is_neutral(self):
        last = enrich(candles([100] * 60))[-1]
        self.assertEqual(last["rsi"], 50)
        self.assertEqual(last["k"], 50)
        self.assertEqual(last["d"], 50)

    def test_sma_200_warmup_and_value(self):
        bars = enrich(candles(list(range(1, 202))))
        self.assertIsNone(bars[198]["sma200"])
        self.assertEqual(bars[199]["sma200"], 100.5)
        self.assertEqual(bars[200]["sma200"], 101.5)

    def test_weekly_ohlcv_preserves_extrema_and_volume(self):
        bars = [
            dict(time=d, open=o, high=h, low=low, close=c, volume=v)
            for d, o, h, low, c, v in [
                ("2026-10-16", 100, 105, 99, 103, 20),
                ("2026-10-19", 104, 110, 103, 108, 30),
                ("2026-10-20", 108, 112, 101, 102, 40),
                ("2026-10-22", 102, 106, 100, 105, 50),
            ]
        ]
        weeks = weekly(bars)
        self.assertEqual(len(weeks), 2)
        self.assertEqual(
            weeks[-1],
            dict(time="2026-10-19", open=104, high=112, low=100, close=105, volume=120),
        )

    def test_manual_demand_below_price_and_distance(self):
        bars = enrich(candles([105] * 60))
        zone = dict(kind="demand", low=100, high=103)
        result = summarize(bars, [zone])
        self.assertAlmostEqual(result["distance"], 100 * 2 / 105)
        self.assertTrue(result["flags"][0]["met"])
        self.assertEqual(result["state"], "At demand")
        self.assertEqual(summarize(bars, [dict(kind="demand", low=110, high=112)])["demand"], None)

    def test_recent_unconfirmed_pivots_cannot_form_zone(self):
        bars = candles([100 + i for i in range(45)])
        bars[-2]["low"] = 80
        self.assertEqual(candidate_zones(enrich(bars)), [])

if __name__ == "__main__":
    unittest.main()
