import csv
import math
import tempfile
import unittest
from pathlib import Path

from expression_tree.csv_io import read_points_csv, write_points_csv
from expression_tree.metrics import calculate_metrics, compare_against_points
from expression_tree.models import RepairConfig
from expression_tree.parsing import detect_and_parse
from expression_tree.plotting import sample_curve
from expression_tree.presets import COSINE_EXPRESSION
from expression_tree.sampling import MAX_SAMPLES, SamplePoint, SamplingConfig, sample_points
from expression_tree.tree import traverse_preorder
from expression_tree.evaluation import evaluate_tree


def parse(expression, repair=False):
    return detect_and_parse(expression, "infix", repair)[0]


class SamplingTests(unittest.TestCase):
    def test_exact_step_and_inclusive_endpoints(self):
        xs = SamplingConfig().grid()
        self.assertEqual(len(xs), 1001)
        self.assertEqual(xs[:3], (0, .001, .002))
        self.assertEqual(xs[-1], 1)
        self.assertEqual(xs, tuple(i / 1000 for i in range(1001)))
        self.assertEqual(SamplingConfig(0, 1, .3).grid(), (0, .3, .6, .9))
        self.assertEqual(SamplingConfig(-.002, .002, .001).grid(), (-.002, -.001, 0, .001, .002))

    def test_bad_or_excessive_sampling_is_rejected(self):
        for config in (SamplingConfig(step=0), SamplingConfig(step=-1), SamplingConfig(1, 0), SamplingConfig(0, math.inf), SamplingConfig(step=1e-6), SamplingConfig(step=2)):
            with self.subTest(config=config), self.assertRaises(ValueError):
                config.grid()
        self.assertEqual(len(SamplingConfig(0, 1, .0001).grid()), MAX_SAMPLES)

    def test_user_expression_repair_and_assignment_form_agree(self):
        correct = parse(COSINE_EXPRESSION)
        broken = parse("(6.87 + 11 *  *cos(7.23*  x^3))", repair=True)
        assigned = parse("y = 6.87 + 11 * cos(7.23*x^3)")
        xs = SamplingConfig().grid()
        expected = sample_points(correct, {}, xs)
        self.assertEqual(expected, sample_points(broken, {}, xs))
        self.assertEqual(expected, sample_points(assigned, {}, xs))
        self.assertAlmostEqual(expected[0].y, 17.87)
        self.assertAlmostEqual(expected[-1].y, 6.87 + 11 * math.cos(7.23))
        curve = sample_curve(correct, {}, x_min=0, x_max=1, step=.001)
        self.assertEqual(curve.points, expected)
        self.assertEqual(curve.valid_samples, 1001)


class CsvTests(unittest.TestCase):
    def test_export_exact_grid_without_rounding_predictions_to_two_decimals(self):
        points = sample_points(parse(COSINE_EXPRESSION), {}, SamplingConfig().grid())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "curve.csv"
            self.assertEqual(write_points_csv(path, points), 1001)
            with path.open(newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(rows[0], ["x", "y"])
            self.assertEqual(rows[1], ["0.000", "17.87"])
            self.assertEqual(rows[2][0], "0.001")
            self.assertEqual(rows[-1][0], "1.000")
            imported = read_points_csv(path)
        for actual, reference in zip(imported, points):
            self.assertEqual(actual.x, reference.x)
            self.assertAlmostEqual(actual.y, reference.y, places=12)

    def test_undefined_y_keeps_its_row_and_is_not_fabricated_as_zero(self):
        points = sample_points(parse("1/x"), {}, (-1, 0, 1))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "holes.csv"
            write_points_csv(path, points, step=1, x_min=-1)
            self.assertIn("0.000,\n", path.read_text())
            imported = read_points_csv(path)
        self.assertEqual(len(imported), 3)
        self.assertIsNone(imported[1].y)

    def test_bom_spaces_semicolons_and_reversed_column_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.csv"
            path.write_text("\ufeff y ; x\n 2.75 ; 0.000\n3.27 ; 0.001\n", encoding="utf-8")
            points = read_points_csv(path)
        self.assertEqual([(p.x, p.y) for p in points], [(0, 2.75), (.001, 3.27)])

    def test_bad_csv_reports_errors(self):
        for content in ("a,b\n1,2\n", "x,y\n", "x,y\n0,NaN\n", "x,y\ninf,2\n", "x,y\n1,nope\n", "x,y\n1,2,3\n"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "bad.csv"
                path.write_text(content)
                with self.assertRaises(ValueError):
                    read_points_csv(path)


class MetricTests(unittest.TestCase):
    def test_known_regression_values(self):
        result = calculate_metrics([3, -.5, 2, 7], [2.5, 0, 2, 8])
        self.assertEqual(result.count, 4)
        expected = {"mse": .375, "rmse": .6123724356957945, "r2": .9486081370449679, "nmse": .05139186295503212, "mae": .5, "medae": .5, "max_error": 1, "bias": .25, "mape": 32.73809523809524}
        for key, value in expected.items():
            with self.subTest(metric=key):
                self.assertAlmostEqual(result.values[key], value)

    def test_perfect_prediction_and_negative_r2(self):
        perfect = calculate_metrics([1, 2, 3], [1, 2, 3]).values
        self.assertEqual(perfect["r2"], 1)
        self.assertTrue(all(value == 0 for key, value in perfect.items() if key != "r2"))
        self.assertEqual(calculate_metrics([1, 2, 3], [0, 0, 0]).values["r2"], -6)

    def test_constant_reference_and_single_pair_are_undefined(self):
        for reference, prediction in (([2, 2, 2], [2, 2, 2]), ([1], [3])):
            result = calculate_metrics(reference, prediction)
            self.assertIsNone(result.values["r2"])
            self.assertIsNone(result.values["nmse"])
            self.assertTrue(result.notes)
        result = calculate_metrics([0, 0], [1, 1])
        self.assertIsNone(result.values["mape"])
        self.assertEqual(result.mape_count, 0)
        self.assertEqual(calculate_metrics([0, 1, 2], [1, 2, 1]).values["mape"], 75)

    def test_invalid_and_overflowing_values_are_rejected(self):
        for reference, prediction in (([], []), ([1], [1, 2]), ([math.nan], [1]), ([1], [math.inf]), ([1e300], [-1e300])):
            with self.assertRaises(ValueError):
                calculate_metrics(reference, prediction)

    def test_comparison_is_pure_and_excluded_pairs_are_reported(self):
        root = parse("sqrt(x)")
        evaluate_tree(root, {"x": -1})
        before = [(n.evaluated, n.repaired, n.error) for n in traverse_preorder(root)]
        reference = [SamplePoint(-1, 1), SamplePoint(0, 0), SamplePoint(1, 1)]
        strict = compare_against_points(root, {}, reference)
        self.assertEqual(strict.excluded, 1)
        self.assertEqual(strict.metrics.count, 2)
        self.assertEqual(strict.metrics.values["mse"], 0)
        repaired = compare_against_points(root, {}, reference, repair_config=RepairConfig())
        self.assertEqual(repaired.metrics.count, 3)
        self.assertEqual(repaired.repaired, 1)
        self.assertEqual(before, [(n.evaluated, n.repaired, n.error) for n in traverse_preorder(root)])
        with self.assertRaises(ValueError):
            compare_against_points(root, {}, [SamplePoint(-1, 1)])


if __name__ == "__main__":
    unittest.main()
