import unittest
import pandas as pd
from estimate_service import (
    generate_estimate,
    add_items_to_estimate,
    update_quantities_in_estimate,
    remove_items_from_estimate,
    get_estimate_display_df,
    get_estimate_export_csv,
    combine_ai_results,
)
from schemas import ProjectMeasurements


class TestEstimateService(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame([
            {"id": 1, "item_no": "2.01", "chapter": "Excavation", "description": "Earthwork excavation for roadway formation", "unit": "cum", "rate": 150.0, "kind": "volume"},
            {"id": 2, "item_no": "2.05", "chapter": "Road Sub Base and Base Course", "description": "Granular sub base GSB grading", "unit": "cum", "rate": 800.0, "kind": "volume"},
            {"id": 3, "item_no": "3.01", "chapter": "Rigid Pavement", "description": "Cement concrete CC pavement M30", "unit": "cum", "rate": 4500.0, "kind": "volume"},
            {"id": 4, "item_no": "5.02", "chapter": "Road Maintenance", "description": "Pothole repair using cold mix", "unit": "sqm", "rate": 300.0, "kind": "area"},
        ]).set_index("id", drop=False)

        self.measurements = ProjectMeasurements(
            length_m=100.0,
            width_m=4.0,
            thickness_mm=150.0,
            pothole_count=5,
            pothole_avg_length_m=1.0,
            pothole_avg_width_m=1.0,
            pothole_avg_depth_m=0.1,
        )

    def test_generate_estimate_cc_road(self):
        # Generate estimate without AI service (pure deterministic fallback)
        estimate = generate_estimate(
            df=self.df,
            mode="New Road Construction",
            road_kind="Concrete (CC)",
            measurements=self.measurements,
            use_ai_selection=False,
            gst_percent=18.0,
        )

        self.assertGreater(len(estimate.items), 0)
        self.assertGreater(estimate.subtotal, 0.0)
        self.assertGreater(estimate.total, estimate.subtotal)
        self.assertEqual(estimate.gst_percent, 18.0)

    def test_add_and_remove_items(self):
        # Start with new road chapters only
        estimate = generate_estimate(
            df=self.df,
            mode="New Road Construction",
            road_kind="Concrete (CC)",
            measurements=self.measurements,
            allowed_chapters=["Excavation", "Rigid Pavement"],
            use_ai_selection=False,
        )
        initial_len = len(estimate.items)

        # Manually add item 4 (pothole repair)
        updated_estimate = add_items_to_estimate(self.df, estimate, [4], self.measurements)
        self.assertEqual(len(updated_estimate.items), initial_len + 1)

        # Remove item 4
        removed_estimate = remove_items_from_estimate(updated_estimate, {4})
        self.assertEqual(len(removed_estimate.items), initial_len)

    def test_update_quantities(self):
        estimate = generate_estimate(
            df=self.df,
            mode="New Road Construction",
            road_kind="Concrete (CC)",
            measurements=self.measurements,
            use_ai_selection=False,
        )
        first_item_id = estimate.items[0].id
        original_qty = estimate.items[0].quantity

        # Double the quantity
        updated = update_quantities_in_estimate(estimate, {first_item_id: original_qty * 2})
        updated_item = next(it for it in updated.items if it.id == first_item_id)
        self.assertAlmostEqual(updated_item.quantity, original_qty * 2)

    def test_csv_export(self):
        estimate = generate_estimate(
            df=self.df,
            mode="New Road Construction",
            road_kind="Concrete (CC)",
            measurements=self.measurements,
            use_ai_selection=False,
        )
        csv_text = get_estimate_export_csv(estimate)
        self.assertTrue(len(csv_text) > 0)
        self.assertIn("GST Amount", csv_text)
        self.assertIn("Amount Including GST", csv_text)

    def test_combine_ai_results(self):
        results = [
            {
                "result": {
                    "site_type": {"value": "rural"},
                    "recommended_mode": {"value": "repair"},
                    "road_type": {"value": "bitumen"},
                    "defects": [{"type": "pothole", "severity": "moderate"}],
                    "suggested_works": [{"work": "patching"}],
                }
            },
            {
                "result": {
                    "site_type": {"value": "rural"},
                    "recommended_mode": {"value": "repair"},
                    "road_type": {"value": "bitumen"},
                    "defects": [{"type": "crack", "severity": "minor"}],
                    "suggested_works": [{"work": "seal coat"}],
                }
            }
        ]
        combined = combine_ai_results(results)
        self.assertIsNotNone(combined)
        self.assertEqual(combined["site_type"]["value"], "rural")
        self.assertEqual(combined["recommended_mode"]["value"], "repair")
        self.assertEqual(len(combined["defects"]), 2)
        self.assertEqual(len(combined["suggested_works"]), 2)

    def test_building_and_water_infra_estimates(self):
        from schemas import BuildingMeasurements, WaterSupplyMeasurements, InfraMeasurements
        from estimate_service import (
            generate_building_estimate,
            generate_water_supply_estimate,
            generate_infra_estimate,
        )

        rich_df = pd.DataFrame([
            {"id": 1, "item_no": "21.01", "chapter": "Excavation", "description": "Excavation for foundation in earth", "unit": "cum", "rate": 200.0, "kind": "volume"},
            {"id": 2, "item_no": "25.13", "chapter": "Reinforced Cement Concrete", "description": "RCC M-25 in situ", "unit": "cum", "rate": 7200.0, "kind": "volume"},
            {"id": 3, "item_no": "41.10", "chapter": "Water Supply and Sanitary Fitting", "description": "Providing 25 mm heavy grade pipe", "unit": "rm", "rate": 450.0, "kind": "length"},
            {"id": 4, "item_no": "11.08", "chapter": "Cross Drainage Works", "description": "Roadside drain running metre", "unit": "rm", "rate": 1900.0, "kind": "length"},
        ]).set_index("id", drop=False)

        b_est = generate_building_estimate(rich_df, BuildingMeasurements(plinth_area_m2=100.0, floors=2))
        self.assertGreater(len(b_est.items), 0)
        self.assertGreater(b_est.subtotal, 0)
        self.assertGreater(b_est.total, 0)

        w_est = generate_water_supply_estimate(rich_df, WaterSupplyMeasurements(network_length_m=150.0, pipe_diameter_mm=25))
        self.assertGreater(len(w_est.items), 0)
        self.assertGreater(w_est.total, 0)

        i_est = generate_infra_estimate(rich_df, InfraMeasurements(storm_drain_length_m=50.0))
        self.assertGreater(len(i_est.items), 0)
        self.assertGreater(i_est.total, 0)


if __name__ == "__main__":
    unittest.main()
