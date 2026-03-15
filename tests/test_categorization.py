import unittest

from leftover_detection.categorization import categorize_food


class CategorizationTests(unittest.TestCase):
    def test_categorize_food(self):
        self.assertEqual(categorize_food("Broccoli"), "Other")
        self.assertEqual(categorize_food("Spaghetti"), "Other")
        self.assertEqual(categorize_food("Apple slices"), "Other")
        self.assertEqual(categorize_food("Unknown dish"), "Other")


if __name__ == "__main__":
    unittest.main()
