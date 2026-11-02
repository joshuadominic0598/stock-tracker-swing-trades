import unittest

from swing_signal.ai.brief import build_report, technical_view

class PlainBriefTests(unittest.TestCase):
    def source(self):
        return dict(
            id="T1",
            as_of="2026-10-29",
            facts=dict(price=100, change=2, rsi=55, rsi_delta=3, volume_ratio=1.5),
            swing=dict(
                direction="bullish",
                near_demand=True,
                rsi_recovery=True,
                period_trend={
                    str(n): dict(available=True, rising=True, change=2) for n in (3, 7, 14)
                },
                signals=[dict(key="ma", score=1), dict(key="stoch", score=1)],
            ),
            weekly_swing=dict(direction="bullish"),
        )

    def test_strong_buyer_view_requires_actual_price_and_momentum_confirmation(self):
        source = self.source()
        self.assertIn("Strong evidence", technical_view(source, "1d")["headline"])
        source["facts"].update(change=-2, rsi=33, rsi_delta=-3)
        source["swing"].update(
            rsi_recovery=False,
            period_trend={
                str(n): dict(available=True, rising=False, change=-2) for n in (3, 7, 14)
            },
        )
        view = technical_view(source, "1d")
        self.assertEqual(view["green_flags"], 2)
        self.assertEqual(view["headline"], "Sellers still have the upper hand")
        self.assertEqual(view["tone"], "negative")

    def test_partial_week_and_old_data_cannot_get_a_strong_buyer_claim(self):
        source = self.source()
        source["week_partial"] = True
        self.assertNotIn("Strong evidence", technical_view(source, "1d")["headline"])
        self.assertIn("still forming", technical_view(source, "1w")["headline"])
        source["data_warning"] = True
        self.assertEqual(technical_view(source, "1d")["tone"], "unknown")

    def test_news_caution_is_included_in_the_overall_view_and_keeps_citations(self):
        sources = [self.source(), dict(id="N1", title="Company reports a large loss")]
        summary, sections = build_report(
            sources,
            [dict(source_id="N1", impact="negative")],
            dict(name="Test", market="NSE"),
            "1d",
        )
        self.assertEqual(summary["tone"], "neutral")
        self.assertIn("news adds caution", summary["title"])
        self.assertIn("N1", summary["source_ids"])
        self.assertEqual([s["key"] for s in sections], ["signals", "news", "attention"])
        self.assertIn("not measured", sections[2]["points"][-1]["label"])
        self.assertEqual(sections[1]["points"][0]["source_ids"], ["N1"])

    def test_more_discussion_is_not_converted_into_bullish_sentiment(self):
        social = dict(id="C1", facts=dict(recent=12, previous=2, tone=dict(positive=1, negative=9)))
        _, sections = build_report(
            [self.source(), social], [], dict(name="Test", market="NSE"), "1d"
        )
        attention = sections[2]
        self.assertEqual(attention["tone"], "neutral")
        self.assertEqual(attention["points"][0]["label"], "More discussion")
        self.assertIn("Negative wording", attention["points"][1]["label"])
        self.assertIn("sampled posts", attention["points"][0]["text"])

if __name__ == "__main__":
    unittest.main()
