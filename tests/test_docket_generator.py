"""
Unit tests for docket_generator.py.
"""

import unittest
from schemas import CostEstimate, EstimateLineItem
from docket_generator import (
    generate_pwd_tender_html,
    number_to_inr_words,
    format_crore_lakh,
)


class TestDocketGenerator(unittest.TestCase):
    def test_number_to_inr_words(self):
        self.assertIn("Rupees 1 Crore 25 Lakh", number_to_inr_words(12500000.0))
        self.assertIn("Rupees 75 Lakh", number_to_inr_words(7500000.0))
        self.assertEqual("Zero Rupees Only", number_to_inr_words(0))

    def test_format_crore_lakh(self):
        self.assertEqual("₹ 1.25 Crore", format_crore_lakh(12500000.0))
        self.assertEqual("₹ 75.00 Lakh", format_crore_lakh(7500000.0))
        self.assertEqual("₹ 0.00 Lakh", format_crore_lakh(0.0))

    def test_generate_pwd_tender_html_empty(self):
        est = CostEstimate()
        html = generate_pwd_tender_html(est)
        self.assertIn("Government of Maharashtra", html)
        self.assertIn("Public Works Department", html)
        self.assertIn("GST @ 18.00%", html)
        self.assertIn("Labour Welfare Cess @ 1.00%", html)
        self.assertIn("Junior Engineer", html)
        self.assertIn("Superintending Engineer", html)

    def test_generate_pwd_tender_html_with_items(self):
        est = CostEstimate()
        est.items = [
            EstimateLineItem(
                id=1,
                item_no="24.12",
                chapter="Road Surfacing Course",
                description="Providing and laying Bituminous Macadam (BM)",
                unit="cum",
                rate=7250.0,
                quantity=100.0,
                amount=725000.0,
            )
        ]
        est.subtotal = 725000.0
        est.gst_amount = 725000.0 * 0.18
        est.total = est.subtotal + est.gst_amount

        html = generate_pwd_tender_html(
            estimate=est,
            project_title="NH-48 Resurfacing Work",
            work_category="Roads & Highways",
            location="Pune Division",
        )
        self.assertIn("NH-48 Resurfacing Work", html)
        self.assertIn("24.12", html)
        self.assertIn("Bituminous Macadam", html)
        self.assertIn("₹ 725,000.00", html)


if __name__ == "__main__":
    unittest.main()
