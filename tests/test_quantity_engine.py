import unittest
from quantity_engine import (
    calculate_quantity,
    quantity_note,
    calculate_all_quantities,
)
from schemas import ProjectMeasurements
import pandas as pd


class TestQuantityEngine(unittest.TestCase):
    def setUp(self):
        self.measurements = ProjectMeasurements(
            length_m=200.0,
            width_m=3.75,
            thickness_mm=200.0,
            pothole_count=10,
            pothole_avg_length_m=1.2,
            pothole_avg_width_m=0.8,
            pothole_avg_depth_m=0.075,
            drain_length_m=150.0,
        )

    def test_area_calculation(self):
        # Road area = 200 * 3.75 = 750 sqm
        qty = calculate_quantity("area", "Bituminous Surface Dressing", "Road Surfacing Course", self.measurements)
        self.assertEqual(qty, 750.0)

        # Pothole area = 10 * 1.2 * 0.8 = 9.6 sqm
        pothole_qty = calculate_quantity("area", "Pothole repair using premix", "Road Maintenance", self.measurements)
        self.assertAlmostEqual(pothole_qty, 9.6, places=2)

    def test_volume_calculation(self):
        # Road volume = 200 * 3.75 * 0.200 = 150 cum
        qty = calculate_quantity("volume", "Granular Sub-base", "Road Sub Base and Base Course", self.measurements)
        self.assertAlmostEqual(qty, 150.0, places=2)

        # Pothole volume = 10 * 1.2 * 0.8 * 0.075 = 0.72 cum
        pothole_vol = calculate_quantity("volume", "Pothole filling with WMM", "Road Maintenance", self.measurements)
        self.assertAlmostEqual(pothole_vol, 0.72, places=2)

    def test_length_and_km(self):
        # Drainage length = 150 m
        drain_qty = calculate_quantity("length", "Construction of roadside drain", "Cross Drainage Works", self.measurements)
        self.assertEqual(drain_qty, 150.0)

        # Standard road length = 200 m
        road_qty = calculate_quantity("length", "Road painting centerline", "Road Furniture", self.measurements)
        self.assertEqual(road_qty, 200.0)

        # Km = 200 / 1000 = 0.2 km
        km_qty = calculate_quantity("km", "Maintenance per km", "Road Maintenance", self.measurements)
        self.assertEqual(km_qty, 0.2)

    def test_layer_specific_thickness(self):
        m = ProjectMeasurements(
            length_m=100.0,
            width_m=4.0,
            thickness_mm=300.0,
            layers=[
                {"name": "gsb", "thickness_mm": 150.0},
                {"name": "wmm", "thickness_mm": 100.0},
                {"name": "pcc", "thickness_mm": 50.0},
            ]
        )
        # GSB layer: 100 * 4 * 0.150 = 60 cum
        gsb_qty = calculate_quantity("volume", "Providing GSB layer", "Road Sub Base", m)
        self.assertAlmostEqual(gsb_qty, 60.0)

        # WMM layer: 100 * 4 * 0.100 = 40 cum
        wmm_qty = calculate_quantity("volume", "Providing WMM layer", "Road Base Course", m)
        self.assertAlmostEqual(wmm_qty, 40.0)

    def test_quantity_notes(self):
        note1 = quantity_note("area", 750.0, "Surface", "Surfacing")
        self.assertIn("length × width", note1)

        note2 = quantity_note("volume", 150.0, "Pothole repair", "Road Maintenance")
        self.assertIn("pothole", note2.lower())

        note_manual = quantity_note("weight", 0.0)
        self.assertIn("manual", note_manual.lower())


if __name__ == "__main__":
    unittest.main()
