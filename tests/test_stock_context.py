import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swing_signal.ai import intelligence
from swing_signal.data import market, storage

class StockSectorContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = storage.DB_PATH
        storage.DB_PATH = Path(self.tmp.name) / "workspace.sqlite3"
        storage.init()

    def tearDown(self):
        storage.DB_PATH = self.original
        self.tmp.cleanup()

    def detail(self, a, **kwargs):
        return dict(
            a,
            available=True,
            stale=False,
            quality_note=None,
            summary=dict(candle_date="2026-10-23", change=2 if a["symbol"] == "DRREDDY" else 1),
            daily_swing=dict(direction="bullish"),
            weekly_swing=dict(direction="neutral"),
        )

    def test_industry_context_stays_centered_on_stock_and_keeps_custom_group_distinct(
        self,
    ):
        with patch("swing_signal.data.market.asset_detail", side_effect=self.detail):
            out = market.sector_context(storage.asset("DRREDDY"))
        self.assertTrue(out["available"])
        self.assertEqual(out["industry"], "Healthcare")
        self.assertEqual(out["research_group"], "Consumer")
        self.assertEqual(out["sample_size"], 3)
        self.assertEqual({p["symbol"] for p in out["peers"]}, {"HCG", "THYROCARE", "DRREDDY"})
        self.assertAlmostEqual(out["relative_change"], 2 - 4 / 3)

    def test_mixed_dates_and_stale_peers_cannot_be_called_a_current_sector_read(self):
        def detail(a, **kwargs):
            d = self.detail(a)
            if a["symbol"] == "HCG":
                d["summary"]["candle_date"] = "2026-10-22"
            if a["symbol"] == "THYROCARE":
                d["stale"] = True
            return d

        with patch("swing_signal.data.market.asset_detail", side_effect=detail):
            out = market.sector_context(storage.asset("DRREDDY"))
        self.assertFalse(out["available"])
        self.assertIsNone(out["change"])
        self.assertIsNone(out["relative_change"])

    def test_custom_group_fallback_is_named_as_a_tracked_sample(self):
        with patch("swing_signal.data.market.asset_detail", side_effect=self.detail):
            out = market.sector_context(storage.asset("ASIANPAINT"))
        self.assertEqual(out["basis"], "Your tracked research group")
        self.assertEqual(out["label"], "Consumer")

    def test_ai_fact_catalog_uses_real_attention_counts_and_labels_peer_scope(self):
        technical = dict(
            id="T1",
            as_of="2026-10-23",
            facts=dict(
                price=100,
                change=1,
                rsi=40,
                rsi_delta=1,
                k=60,
                d=50,
                volume_ratio=1.2,
                distance=None,
                change_3d=2,
                change_20d=3,
            ),
        )
        with patch("swing_signal.data.market.asset_detail", side_effect=self.detail):
            context = market.sector_context(storage.asset("DRREDDY"))
        sources = [
            technical,
            dict(
                id="C1",
                facts=dict(
                    recent=8,
                    previous=2,
                    label="More mentions",
                    tone=dict(positive=2, negative=1, mixed=0, unclear=5),
                ),
            ),
            dict(id="S1", facts=context),
        ]
        catalog = {
            f["id"]: f for f in intelligence.fact_catalog(sources, storage.asset("DRREDDY"), "1d")
        }
        self.assertIn("8 matched Reddit posts", catalog["C1_ACTIVITY"]["text"])
        self.assertIn("not a count of people", catalog["C1_ACTIVITY"]["text"])
        self.assertIn("Healthcare", catalog["S1_CONTEXT"]["text"])
        self.assertIn("Consumer", catalog["S1_CONTEXT"]["text"])
        self.assertIn("not the whole sector", catalog["S1_RELATIVE"]["text"])

if __name__ == "__main__":
    unittest.main()
