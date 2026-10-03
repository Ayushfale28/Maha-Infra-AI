import unittest
from app import format_crore_lakh, format_crore_lakh_verbal


class TestCroreLakhFormatting(unittest.TestCase):
    def test_zero_amount(self):
        self.assertEqual(format_crore_lakh(0.0), "₹ 0.00 Lakh")
        self.assertEqual(format_crore_lakh_verbal(0.0), "0.00 Lakhs")

    def test_lakh_range(self):
        # 45,000 -> 0.45 Lakh
        self.assertEqual(format_crore_lakh(45000), "₹ 0.45 Lakh")
        self.assertEqual(format_crore_lakh_verbal(45000), "0.45 Lakhs")

        # 8,50,000 -> 8.50 Lakh
        self.assertEqual(format_crore_lakh(850000), "₹ 8.50 Lakh")
        self.assertEqual(format_crore_lakh_verbal(850000), "8.50 Lakhs")

        # 78,92,000 -> 78.92 Lakh
        self.assertEqual(format_crore_lakh(7892000), "₹ 78.92 Lakh")
        self.assertEqual(format_crore_lakh_verbal(7892000), "78.92 Lakhs")

    def test_crore_range(self):
        # 1 Crore = 10,000,000
        self.assertEqual(format_crore_lakh(10000000), "₹ 1.00 Crore")
        self.assertEqual(format_crore_lakh_verbal(10000000), "1 Crore")

        # 9,31,00,000 -> 9.31 Crore
        self.assertEqual(format_crore_lakh(93100000), "₹ 9.31 Crore")
        self.assertEqual(format_crore_lakh_verbal(93100000), "9 Crore 31.00 Lakhs")

        # 1 Crore 45 Lakhs
        self.assertEqual(format_crore_lakh(14500000), "₹ 1.45 Crore")
        self.assertEqual(format_crore_lakh_verbal(14500000), "1 Crore 45.00 Lakhs")


if __name__ == "__main__":
    unittest.main()
