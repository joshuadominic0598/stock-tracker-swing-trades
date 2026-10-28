import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app import attention, market, storage

UTC = timezone.utc
CLOCK = datetime(2026, 10, 24, 5, tzinfo=UTC)
ASSET = dict(
    symbol="HCG",
    name="Healthcare Global Enterprises",
    market="NSE",
    sector="Healthcare",
)


class AttentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = storage.DB_PATH
        storage.DB_PATH = Path(self.tmp.name) / "test.sqlite3"
        storage.init()

    def tearDown(self):
        storage.DB_PATH = self.original
        self.tmp.cleanup()

    def test_zero_baseline_does_not_create_infinite_growth_or_people_count(self):
        posts = [
            dict(
                published_at=(CLOCK - timedelta(days=1)).isoformat(),
                title="HCG looks undervalued",
            )
        ]
        out = attention.activity(posts, CLOCK)
        self.assertEqual((out["recent"], out["previous"]), (1, 0))
        self.assertIsNone(out["change"])
        self.assertEqual(out["label"], "New sampled mentions")

    def test_counts_use_comparable_rolling_windows_and_ignore_future_or_old(self):
        posts = [
            dict(published_at=(CLOCK - timedelta(days=i)).isoformat(), title="HCG")
            for i in (1, 2, 9, 15, -1)
        ]
        out = attention.activity(posts, CLOCK)
        self.assertEqual((out["recent"], out["previous"]), (2, 1))
        self.assertEqual(out["change"], 100)

    def test_questions_and_negated_phrases_are_not_mistaken_for_bullish_posts(self):
        self.assertEqual(attention.wording("Is HCG undervalued?")["direction"], "unclear")
        self.assertEqual(attention.wording("HCG is not undervalued")["direction"], "unclear")
        self.assertEqual(attention.wording("HCG bullish but overvalued")["direction"], "mixed")

    def test_alias_matches_are_word_bounded(self):
        self.assertFalse(attention.matches("HCGS announced results", ASSET))
        self.assertTrue(attention.matches("Healthcare Global sees profits rise", ASSET))

    def test_reddit_parser_excludes_communities_duplicates_wrong_companies_and_offsite_urls(
        self,
    ):
        def entry(identity, title, link, group="r/IndianStockMarket"):
            return f'<entry><id>{identity}</id><title>{title}</title><link href="{link}"/><updated>2026-10-23T05:00:00Z</updated><category label="{group}"/></entry>'

        xml = (
            '<feed xmlns="http://www.w3.org/2005/Atom">'
            + "".join(
                [
                    entry(
                        "t3_1",
                        "HCG looks undervalued",
                        "https://www.reddit.com/r/IndianStockMarket/comments/1/hcg/",
                    ),
                    entry(
                        "t3_1",
                        "HCG looks undervalued",
                        "https://www.reddit.com/r/IndianStockMarket/comments/1/hcg/",
                    ),
                    entry(
                        "t5_2",
                        "HCG discussion community",
                        "https://www.reddit.com/r/hcg/",
                    ),
                    entry(
                        "t3_3",
                        "Another company",
                        "https://www.reddit.com/r/IndianStockMarket/comments/3/other/",
                    ),
                    entry("t3_4", "HCG bullish", "https://example.com/comments/4/hcg/"),
                    entry(
                        "t3_5",
                        "HCG bullish",
                        "https://www.reddit.com/r/random/comments/5/hcg/",
                        "r/random",
                    ),
                ]
            )
            + "</feed>"
        )
        with patch("app.attention.now", return_value=CLOCK):
            out = attention.community(ASSET, lambda _: xml.encode())
        self.assertEqual(len(out["posts"]), 1)
        self.assertEqual(out["activity"]["recent"], 1)
        self.assertEqual(out["posts"][0]["tone"]["direction"], "positive")

    def test_reddit_failure_is_unavailable_instead_of_zero_or_neutral(self):
        def failed(_):
            raise OSError("403 refused")

        out = attention.community(ASSET, failed)
        self.assertFalse(out["available"])
        self.assertNotIn("activity", out)

    def test_google_no_trending_match_is_not_a_zero_search_count(self):
        xml = b'<rss xmlns:ht="https://trends.google.com/trending/rss"><channel><item><title>unrelated sport</title><ht:approx_traffic>200+</ht:approx_traffic></item></channel></rss>'
        with patch("app.attention.now", return_value=CLOCK):
            out = attention.trends(ASSET, lambda _: xml)
        self.assertFalse(out["available"])
        self.assertTrue(out["trending_now"]["available"])
        self.assertEqual(out["trending_now"]["matches"], [])
        self.assertNotIn("search_count", out)

    def test_google_matching_topic_preserves_approximate_label(self):
        xml = b'<rss xmlns:ht="https://trends.google.com/trending/rss"><channel><item><title>HCG share price</title><ht:approx_traffic>500+</ht:approx_traffic></item></channel></rss>'
        with patch("app.attention.now", return_value=CLOCK):
            out = attention.trends(ASSET, lambda _: xml)
        self.assertEqual(out["trending_now"]["matches"][0]["traffic"], "500+")
        self.assertFalse(out["available"])

    def csv(self, values, label="HCG share price: (India)", step=1):
        rows = ["Category: All categories", "", "Day," + label] if step == 1 else ["Week," + label]
        rows += [
            str((CLOCK - timedelta(days=(len(values) - i) * step)).date()) + "," + str(v)
            for i, v in enumerate(values)
        ]
        return "\n".join(rows)

    def test_google_csv_compares_completed_periods_and_keeps_source_units(self):
        out = attention.import_trends(ASSET, self.csv([10] * 7 + [20] * 7), CLOCK)
        self.assertEqual(out["comparison"]["change"], 100)
        self.assertEqual(out["comparison"]["label"], "Search interest rising")
        self.assertEqual(out["unit"], "Relative search interest (0–100)")
        self.assertEqual(storage.cache_get("trends:HCG")["value"], out)

    def test_low_volume_or_missing_google_value_prevents_fabricated_comparison(self):
        out = attention.import_trends(ASSET, self.csv([10] * 13 + ["<1"]), CLOCK)
        self.assertIsNone(out["points"][-1]["value"])
        self.assertFalse(out["comparison"]["complete"])
        self.assertIsNone(out["comparison"]["change"])

    def test_google_csv_rejects_wrong_company_multiple_terms_and_out_of_range(self):
        for text in (
            self.csv([10] * 14, label="Asian Paints share price: (India)"),
            self.csv([10] * 13 + [101]),
            self.csv([10] * 14).replace("Day,HCG", "Day,OTHER,HCG"),
        ):
            with self.assertRaises(ValueError):
                attention.import_trends(ASSET, text, CLOCK)

    def test_weekly_google_series_uses_four_weeks_on_each_side(self):
        out = attention.import_trends(ASSET, self.csv([10] * 4 + [20] * 4, step=7), CLOCK)
        self.assertEqual(out["comparison"]["change"], 100)
        self.assertEqual(out["interval"], "week")

    def test_news_headlines_deduplicate_and_match_the_company(self):
        xml = b"<rss><channel><item><title>HCG profit jumps - News</title><link>https://news.google.com/a</link><source>News</source><pubDate>Fri, 23 Oct 2026 05:00:00 GMT</pubDate></item><item><title>HCG profit jumps - News</title><link>https://news.google.com/a</link><source>News</source></item><item><title>Unrelated company - News</title><link>https://news.google.com/b</link><source>News</source></item></channel></rss>"
        with (
            patch("app.market.request", return_value=xml),
            patch("app.attention.now", return_value=CLOCK),
        ):
            out = market.news(ASSET)
        self.assertEqual(len(out["articles"]), 1)
        self.assertEqual(out["activity"]["recent"], 1)
        self.assertEqual(out["articles"][0]["tone"]["direction"], "positive")


if __name__ == "__main__":
    unittest.main()
