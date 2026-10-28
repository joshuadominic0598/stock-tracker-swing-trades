import unittest
from unittest.mock import patch

from swing_signal.ai import intelligence

class IntelligenceTests(unittest.TestCase):
    def test_catalog_keeps_zone_direction_and_volume_units(self):
        source = dict(
            id="T1",
            as_of="2026-10-22",
            facts=dict(
                price=105,
                change=-1,
                rsi=35,
                rsi_delta=-2,
                k=20,
                d=30,
                volume_ratio=0.7,
                distance=5,
                demand=dict(low=98, high=99.75),
                change_3d=-2,
                change_20d=3,
            ),
        )
        facts = {
            f["id"]: f
            for f in intelligence.fact_catalog([source], dict(name="Test", market="NSE"), "1d")
        }
        self.assertIn("5.00% above", facts["T_ZONE"]["text"])
        self.assertIn("0.70 times", facts["T_VOLUME"]["text"])
        self.assertNotIn("negative volume", facts["T_VOLUME"]["text"])
        self.assertTrue(facts["T_VOLUME"]["counterpoint"])

    def test_financial_catalog_preserves_metric_periods_and_units(self):
        technical = dict(
            id="T1",
            as_of="2026-10-22",
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
        financial = dict(
            id="F1",
            facts=[
                dict(
                    id="FreeCashFlow",
                    metric="Free cash flow",
                    latest=dict(amount="INR 56.01 billion", period_end="2026-03-31"),
                    prior=dict(amount="INR 25.94 billion", period_end="2025-03-31"),
                    yoy=115.9,
                )
            ],
        )
        facts = {
            f["id"]: f
            for f in intelligence.fact_catalog(
                [technical, financial], dict(name="Test", market="NSE"), "1d"
            )
        }
        text = facts["F_FreeCashFlow"]["text"]
        self.assertIn("56.01 billion", text)
        self.assertIn("2026-03-31", text)
        self.assertIn("25.94 billion", text)
        self.assertIn("2025-03-31", text)
        self.assertEqual(facts["F_FreeCashFlow"]["source_ids"], ["F1"])

    def test_uninstalled_model_is_never_requested(self):
        with patch(
            "swing_signal.ai.intelligence.models",
            return_value=dict(available=True, models=["local-model"]),
        ):
            with self.assertRaisesRegex(ValueError, "already installed"):
                intelligence.generate(dict(symbol="ASIANPAINT"), "uninstalled-model")

    def test_model_service_failure_is_explicit(self):
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            status = intelligence.models()
        self.assertFalse(status["available"])
        self.assertEqual(status["models"], [])

if __name__ == "__main__":
    unittest.main()
