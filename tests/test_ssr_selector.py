import unittest
import pandas as pd
from ssr_selector import (
    find_candidates,
    score_item,
    validate_selected_items,
    rank_items_by_relevance,
    candidates_to_ai_payload,
)


class TestSSRSelector(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame([
            {"id": 1, "item_no": "2.01", "chapter": "Excavation", "description": "Earthwork excavation for road formation", "unit": "cum", "rate": 150.0, "kind": "volume"},
            {"id": 2, "item_no": "2.02", "chapter": "Road Sub grade", "description": "Compacting ground of subgrade", "unit": "sqm", "rate": 50.0, "kind": "area"},
            {"id": 3, "item_no": "3.01", "chapter": "Rigid Pavement", "description": "Providing cement concrete pavement M30", "unit": "cum", "rate": 4500.0, "kind": "volume"},
            {"id": 4, "item_no": "4.01", "chapter": "Road Surfacing Course", "description": "Bituminous Concrete premix surfacing", "unit": "sqm", "rate": 350.0, "kind": "area"},
            {"id": 5, "item_no": "5.01", "chapter": "Road Maintenance", "description": "Pot hole repair with bituminous mix", "unit": "sqm", "rate": 200.0, "kind": "area"},
            {"id": 6, "item_no": "5.01", "chapter": "Road Maintenance", "description": "Pot hole repair duplicate item", "unit": "sqm", "rate": 200.0, "kind": "area"},
        ]).set_index("id", drop=False)

    def test_score_item_new_cc_road(self):
        row_cc = self.df.loc[3]
        score, reasons = score_item(row_cc, mode="New Road Construction", road_kind="Concrete (CC)")
        self.assertGreater(score, 0)
        self.assertTrue(any("concrete" in r.lower() for r in reasons))

    def test_score_item_repair_road(self):
        row_repair = self.df.loc[5]
        score, reasons = score_item(row_repair, mode="Repair (Existing Road)", road_kind=None)
        self.assertGreater(score, 0)
        self.assertTrue(any("repair" in r.lower() for r in reasons))

    def test_find_candidates_deduplication(self):
        # Items 5 and 6 have the same item_no ("5.01"). Only one should be kept.
        candidates = find_candidates(self.df, mode="Repair (Existing Road)", road_kind=None)
        self.assertFalse(candidates.empty)
        # Check no duplicate item numbers
        item_nos = list(candidates["item_no"])
        self.assertEqual(len(item_nos), len(set(item_nos)))

    def test_validate_selected_items(self):
        # 1 and 3 exist; 999 and 'abc' do not
        raw_ids = [1, 999, "3", "invalid", 1]
        valid = validate_selected_items(self.df, raw_ids)
        self.assertEqual(valid, [1, 3])

    def test_rank_items_by_relevance(self):
        ranked = rank_items_by_relevance(self.df, [1, 3, 5], mode="New Road Construction", road_kind="Concrete (CC)")
        # Item 3 (Concrete) should outrank or be among the top for CC road
        self.assertIn(3, ranked)
        self.assertIn(1, ranked)

    def test_candidates_to_ai_payload(self):
        candidates = self.df.head(2)
        payload = candidates_to_ai_payload(candidates)
        self.assertEqual(len(payload), 2)
        self.assertIn("id", payload[0])
        self.assertIn("description", payload[0])
        self.assertNotIn("rate", payload[0])  # Rates not leaked to AI selector


if __name__ == "__main__":
    unittest.main()
