import unittest
from src.counting import count_classes, counting_metrics


class CountingTests(unittest.TestCase):
    def test_counts_empty_and_repeated_instances(self):
        self.assertEqual(count_classes([]), [0]*5)
        self.assertEqual(count_classes([0, 0, 3, 4]), [2, 0, 0, 1, 1])
        for bad in ([5], [-1], [0.5]):
            with self.assertRaises(ValueError):
                count_classes(bad)

    def test_class_errors_do_not_cancel_in_cell_mae(self):
        result = counting_metrics([[1, 0, 0, 0, 0]], [[0, 1, 0, 0, 0]])
        self.assertEqual(result["overall_cell_mae"], 0.4)
        self.assertEqual(result["total_count_mae"], 0)
        self.assertEqual(result["exact_five_class_accuracy"], 0)

    def test_exact_vectors_and_zero_baseline(self):
        true = [[1,2,0,0,0], [0,0,0,0,0]]
        self.assertEqual(counting_metrics(true, true)["exact_five_class_accuracy"], 1)
        zero = counting_metrics(true, [[0]*5]*2)
        self.assertEqual(zero["overall_cell_mae"], 0.3)
        self.assertEqual(zero["exact_five_class_accuracy"], 0.5)
