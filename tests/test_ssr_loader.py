import unittest
import io
import pandas as pd
from ssr_loader import (
    load_ssr,
    infer_kind,
    match_chapters,
    search,
    ssr_health_summary,
)


class TestSSRLoader(unittest.TestCase):
    def test_infer_kind(self):
        self.assertEqual(infer_kind("sqm"), "area")
        self.assertEqual(infer_kind("cum"), "volume")
        self.assertEqual(infer_kind("m"), "length")
        self.assertEqual(infer_kind("km"), "km")
        self.assertEqual(infer_kind("nos"), "nos")
        self.assertEqual(infer_kind("tonne"), "weight")
        self.assertEqual(infer_kind("litre"), "liquid")
        self.assertEqual(infer_kind("hour"), "time")
        self.assertEqual(infer_kind("acre"), "acre")
        self.assertEqual(infer_kind("xyz_unknown"), "unknown")

    def test_load_ssr_csv_buffer(self):
        csv_data = """Item No,Chapter,Description,Unit,Rate
1.01,Excavation,Clearing jungle,sqm,15.50
2.29a,Road Sub Base,Granular Sub Base GSB,cum,850.00
3.05,Cross Drainage,Providing Hume Pipe,m,1200.00
4.12,Road Safety,Cautionary Sign Board,nos,2500.00
"""
        buf = io.StringIO(csv_data)
        df = load_ssr(buf)

        self.assertEqual(len(df), 4)
        self.assertIn("id", df.columns)
        self.assertIn("kind", df.columns)
        # Verify letter-suffix item preservation
        self.assertIn("2.29a", list(df["item_no"]))
        # Verify rates are numeric
        self.assertEqual(df.loc[df["item_no"] == "2.29a", "rate"].values[0], 850.0)
        # Verify kind inference
        self.assertEqual(df.loc[df["item_no"] == "2.29a", "kind"].values[0], "volume")

    def test_match_chapters(self):
        all_chapters = ["Excavation", "Road Sub grade", "Bridge Works", "Water Supply"]
        wanted = ["Excavation", "Road Sub grade", "Non Existent"]
        matched = match_chapters(all_chapters, wanted)
        self.assertEqual(matched, ["Excavation", "Road Sub grade"])

    def test_search_and_health_summary(self):
        df = pd.DataFrame([
            {"id": 1, "item_no": "1.01", "chapter": "Excavation", "description": "Excavation in soil", "unit": "cum", "rate": 100.0, "kind": "volume"},
            {"id": 2, "item_no": "2.01", "chapter": "Pavement", "description": "Bituminous concrete", "unit": "sqm", "rate": 200.0, "kind": "area"},
        ]).set_index("id", drop=False)

        res = search(df, chapters=["Excavation"], keywords=["soil"])
        self.assertEqual(len(res), 1)
        self.assertEqual(res.iloc[0]["item_no"], "1.01")

        summary = ssr_health_summary(df)
        self.assertEqual(summary["total_items"], 2)
        self.assertEqual(summary["zero_or_missing_rates"], 0)


if __name__ == "__main__":
    unittest.main()
