import unittest
import pandas as pd
from cost_engine import (
    build_estimate,
    update_estimate_quantities,
    remove_items,
    estimate_to_dataframe,
    estimate_to_download_dataframe,
)


class TestCostEngine(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame([
            {"id": 10, "item_no": "1.01", "chapter": "Excavation", "description": "Excavation in hard rock", "unit": "cum", "rate": 200.0, "kind": "volume"},
            {"id": 20, "item_no": "2.05", "chapter": "Sub Base", "description": "Granular Sub Base", "unit": "cum", "rate": 500.0, "kind": "volume"},
            {"id": 30, "item_no": "3.10", "chapter": "Surfacing", "description": "Bituminous Concrete", "unit": "sqm", "rate": 150.0, "kind": "area"},
        ]).set_index("id", drop=False)

    def test_build_estimate(self):
        selected = {10: 50.0, 20: 30.0}
        notes = {10: "Volume calculated", 20: "GSB Layer"}

        estimate = build_estimate(self.df, selected, gst_percent=18.0, calculation_notes=notes)

        self.assertEqual(len(estimate.items), 2)
        # item 10: 50 * 200 = 10,000
        # item 20: 30 * 500 = 15,000
        # subtotal: 25,000
        # GST 18%: 4,500
        # Total: 29,500
        self.assertEqual(estimate.subtotal, 25000.0)
        self.assertEqual(estimate.gst_amount, 4500.0)
        self.assertEqual(estimate.total, 29500.0)

    def test_update_estimate_quantities(self):
        selected = {10: 50.0}
        estimate = build_estimate(self.df, selected, gst_percent=18.0)
        self.assertEqual(estimate.subtotal, 10000.0)

        # Update quantity from 50 to 100
        update_estimate_quantities(estimate, {10: 100.0})
        # 100 * 200 = 20,000
        self.assertEqual(estimate.subtotal, 20000.0)
        self.assertEqual(estimate.gst_amount, 3600.0)
        self.assertEqual(estimate.total, 23600.0)

    def test_remove_items(self):
        selected = {10: 50.0, 20: 30.0}
        estimate = build_estimate(self.df, selected, gst_percent=18.0)
        self.assertEqual(len(estimate.items), 2)

        remove_items(estimate, {10})
        self.assertEqual(len(estimate.items), 1)
        self.assertEqual(estimate.items[0].id, 20)
        self.assertEqual(estimate.subtotal, 15000.0)

    def test_dataframes(self):
        selected = {10: 10.0}
        estimate = build_estimate(self.df, selected, gst_percent=18.0)
        disp_df = estimate_to_dataframe(estimate)
        self.assertFalse(disp_df.empty)
        self.assertIn("Amount", disp_df.columns)

        dl_df = estimate_to_download_dataframe(estimate)
        self.assertIn("Amount Including GST", dl_df.columns)
        self.assertEqual(dl_df.iloc[0]["Amount Including GST"], 2360.0)


if __name__ == "__main__":
    unittest.main()
