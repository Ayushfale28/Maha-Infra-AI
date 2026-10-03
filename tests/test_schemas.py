import unittest
from schemas import (
    AnalysisResult,
    DefectObservation,
    SuggestedWork,
    SuggestedParameter,
    ProjectMeasurements,
    CostEstimate,
    EstimateLineItem,
)


class TestSchemas(unittest.TestCase):
    def test_analysis_result_from_dict_and_to_dict(self):
        raw = {
            "photo_quality": {"value": "good", "reason": "clear sunlight"},
            "site_type": {"value": "rural", "confidence": "high"},
            "recommended_mode": {"value": "repair", "confidence": "high", "reason": "potholes visible"},
            "road_type": {"value": "bitumen", "confidence": "high"},
            "surface_condition": "Ravelling and multiple potholes",
            "defects": [
                {"type": "pothole", "severity": "severe", "confidence": "high", "note": "deep depression"}
            ],
            "suggested_works": [
                {
                    "work": "pothole repair",
                    "reason": "safety hazard",
                    "suggested_chapters": ["Road Maintenance"],
                    "search_keywords": ["pothole", "premix"],
                    "confidence": "high",
                }
            ],
            "suggested_parameters": [
                {"name": "pothole dimensions", "why_needed": "estimate volume"}
            ],
            "limitations": "Edge condition not visible",
        }

        result = AnalysisResult.from_dict(raw)
        self.assertEqual(result.photo_quality, "good")
        self.assertEqual(result.site_type, "rural")
        self.assertEqual(result.recommended_mode, "repair")
        self.assertEqual(result.road_type, "bitumen")
        self.assertEqual(len(result.defects), 1)
        self.assertEqual(result.defects[0].type, "pothole")
        self.assertEqual(len(result.suggested_works), 1)

        d = result.to_dict()
        self.assertEqual(d["recommended_mode"]["value"], "repair")
        self.assertEqual(d["photo_quality"]["reason"], "clear sunlight")

    def test_project_measurements_properties(self):
        m = ProjectMeasurements(
            length_m=100.0,
            width_m=4.0,
            thickness_mm=150.0,
            pothole_count=5,
            pothole_avg_length_m=1.0,
            pothole_avg_width_m=1.0,
            pothole_avg_depth_m=0.1,
        )
        self.assertEqual(m.area_m2, 400.0)
        self.assertAlmostEqual(m.thickness_m, 0.15)
        self.assertAlmostEqual(m.volume_m3, 60.0)
        self.assertEqual(m.pothole_area_m2, 5.0)
        self.assertAlmostEqual(m.pothole_volume_m3, 0.5)
        self.assertAlmostEqual(m.length_km, 0.1)
        self.assertEqual(m.validate(), [])

    def test_project_measurements_validation(self):
        m = ProjectMeasurements(length_m=-10.0, width_m=-2.0)
        warnings = m.validate()
        self.assertTrue(any("Length cannot be negative" in w for w in warnings))
        self.assertTrue(any("Width cannot be negative" in w for w in warnings))

    def test_cost_estimate_calculations(self):
        item1 = EstimateLineItem(
            id=1,
            item_no="2.1",
            chapter="Excavation",
            description="Earthwork excavation",
            unit="cum",
            rate=120.0,
            quantity=50.0,
        )
        item2 = EstimateLineItem(
            id=2,
            item_no="4.5",
            chapter="Surfacing",
            description="Bituminous surfacing",
            unit="sqm",
            rate=250.0,
            quantity=200.0,
        )

        estimate = CostEstimate(items=[item1, item2], gst_percent=18.0)
        estimate.recalculate()

        # item1 amount = 50 * 120 = 6000
        # item2 amount = 200 * 250 = 50000
        # subtotal = 56000
        # gst = 56000 * 0.18 = 10080
        # total = 66080
        self.assertEqual(item1.amount, 6000.0)
        self.assertEqual(item2.amount, 50000.0)
        self.assertEqual(estimate.subtotal, 56000.0)
        self.assertEqual(estimate.gst_amount, 10080.0)
        self.assertEqual(estimate.total, 66080.0)
        self.assertEqual(len(estimate.warnings), 0)


if __name__ == "__main__":
    unittest.main()
