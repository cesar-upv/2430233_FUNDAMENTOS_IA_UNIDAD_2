import math
import os
import sys
import unittest
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from expression_tree.evaluation import evaluate_tree
from expression_tree.evolution import EvolutionConfig, EvolutionRun
from expression_tree.generation import GenerationConfig
from expression_tree.metrics import calculate_metrics
from expression_tree.models import RepairConfig
from expression_tree.sampling import SamplePoint
from expression_tree.tree import to_infix_string
from expression_tree.ui.elite_comparison import EliteComparisonChart, EliteComparisonPanel


def config(**kwargs):
    return EvolutionConfig(generation=GenerationConfig(4, ("+", "*", "sqrt"), 42), population_size=8,
                           elite_count=3, max_generations=4, tolerance=0, **kwargs)


def reference():
    return tuple(SamplePoint(i / 10, (i / 10)**2 + .123) for i in range(-10, 11))


class EliteHistoryTests(unittest.TestCase):
    def test_snapshot_records_all_elites_and_survives_later_generations(self):
        run = EvolutionRun(config(), reference())
        run.initialize()
        first = run.elite_history[0]
        self.assertEqual([ind.id for ind in first.individuals], [ind.id for ind in sorted(run.population, key=lambda i: i.loss)[:3]])
        self.assertTrue(all(old.root is not current.root for old in first.individuals for current in run.population))
        original = [ind.expression for ind in first.individuals]
        for _ in range(3):
            run.advance()
        self.assertEqual([entry.generation for entry in run.elite_history], [0, 1, 2, 3])
        self.assertEqual([ind.expression for ind in first.individuals], original)
        self.assertEqual(len(run.elite_history[-1].individuals), 3)

    def test_live_predictions_are_exactly_the_values_used_by_fitness(self):
        run = EvolutionRun(config(), reference(), repairs=RepairConfig())
        run.initialize(); run.advance()
        elite = run.elite_history[-1].individuals[0]
        self.assertEqual([p.x for p in run.latest_elite_predictions], [p.x for p in run.reference])
        expected = [evaluate_tree(elite.root, {"x": p.x}, run.repairs, annotate=False, trace=False)[0] for p in run.reference]
        self.assertEqual([p.y for p in run.latest_elite_predictions], expected)
        metrics = calculate_metrics([p.y for p in run.reference], expected)
        self.assertEqual(metrics.values["mse"], elite.metrics["mse"])
        self.assertEqual(metrics.values["r2"], elite.metrics["r2"])

    def test_disabled_elitism_and_archive_still_record_the_generation_best(self):
        run = EvolutionRun(replace(config(), elite_count=0, hall_of_fame_size=0), reference())
        run.initialize(); run.advance()
        self.assertFalse(run.hall_of_fame)
        self.assertEqual(len(run.elite_history), 2)
        self.assertEqual(len(run.elite_history[-1].individuals), 1)
        self.assertEqual(run.elite_history[-1].individuals[0].id, run.best.id)


class EliteComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.run = EvolutionRun(config(), reference(), repairs=RepairConfig())
        self.run.initialize()
        self.panel = EliteComparisonPanel()
        self.panel.resize(900, 620)
        self.panel.show()
        self.panel.set_run(self.run)
        self.app.processEvents()

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()

    def test_live_view_follows_each_completed_generation(self):
        self.assertIsNone(self.panel.generation_picker.currentData())
        self.assertEqual(self.panel.selected_generation, 0)
        for i in range(1, 4):
            self.run.advance()
            self.panel.set_run(self.run)
            self.assertEqual(self.panel.selected_generation, i)
            self.assertEqual(self.panel.selected_individual.id, self.run.best.id)
            self.assertEqual(self.panel.chart.predictions, self.run.latest_elite_predictions)
            self.assertEqual(self.panel.generation_picker.count(), i + 2)

    def test_historical_generation_stays_pinned_until_live_is_selected(self):
        self.panel.generation_picker.setCurrentIndex(self.panel.generation_picker.findData(0))
        self.panel.elite_picker.setCurrentIndex(1)
        original_id = self.panel.selected_individual.id
        original_curve = self.panel.chart.predictions
        self.run.advance(); self.panel.set_run(self.run)
        self.assertEqual(self.panel.selected_generation, 0)
        self.assertEqual(self.panel.selected_individual.id, original_id)
        self.assertEqual(self.panel.chart.predictions, original_curve)
        self.panel.generation_picker.setCurrentIndex(0)
        self.assertEqual(self.panel.selected_generation, 1)

    def test_each_elite_uses_its_own_equation_metrics_and_prediction(self):
        self.panel.elite_picker.setCurrentIndex(2)
        elite = self.run.elite_history[0].individuals[2]
        expected = [evaluate_tree(elite.root, {"x": point.x}, self.run.repairs, annotate=False, trace=False)[0]
                    for point in self.run.reference]
        self.assertEqual(self.panel.selected_individual.id, elite.id)
        self.assertEqual(self.panel.equation.text(), "Predicción: " + elite.expression)
        self.assertEqual([p.y for p in self.panel.chart.predictions], expected)
        self.assertIn(f"MSE {elite.metrics['mse']:.6g}", self.panel.summary.text())

    def test_new_run_resets_history_and_uses_exact_unsorted_duplicate_csv_x(self):
        self.run.advance(); self.panel.set_run(self.run)
        self.panel.generation_picker.setCurrentIndex(1)
        self.panel.elite_picker.setCurrentIndex(2)
        cfg = replace(config(), generation=GenerationConfig(3, ("+", "*"), 7, variable="t"))
        points = tuple(SamplePoint(x, y) for x, y in ((13, 26), (12, 24), (12, 23), (.125, .25)))
        new = EvolutionRun(cfg, points)
        new.initialize(); self.panel.set_run(new)
        self.assertIsNone(self.panel.generation_picker.currentData())
        self.assertEqual(self.panel.generation_picker.count(), 2)
        self.assertEqual(self.panel.elite_picker.currentIndex(), 0)
        self.assertEqual(self.panel.chart.reference, points)
        self.assertEqual([p.x for p in self.panel.chart.predictions], [13, 12, 12, .125])
        self.assertEqual(self.panel.chart.variable, "t")
        self.assertEqual(self.panel.chart.order, [3, 1, 2, 0])

    def test_no_elitism_labels_best_without_changing_archive_behavior(self):
        run = EvolutionRun(replace(config(), elite_count=0, hall_of_fame_size=0), reference())
        run.initialize(); self.panel.set_run(run)
        self.assertEqual(self.panel.elite_picker.count(), 1)
        self.assertIn("Mejor individuo", self.panel.elite_picker.currentText())
        self.assertIn("Elitismo desactivado", self.panel.note.text())
        self.assertFalse(self.panel.elite_picker.isEnabled())
        self.assertEqual(self.panel.selected_individual.id, run.best.id)

    def test_invalid_domains_keep_reference_and_show_prediction_gaps(self):
        cfg = replace(config(), generation=GenerationConfig(2, ("sqrt",), 42))
        points = (SamplePoint(-1, 1), SamplePoint(0, 0), SamplePoint(1, 1))
        run = EvolutionRun(cfg, points, repairs=RepairConfig(enabled=False))
        run.initialize(); self.panel.set_run(run)
        self.assertEqual(len(self.panel.chart.reference), 3)
        self.assertIsNone(self.panel.chart.predictions[0].y)
        self.assertIn("fuera de dominio", self.panel.warning.text())
        self.assertFalse(self.panel.warning.isHidden())
        self.assertEqual([p.x for segment in self.panel.chart.segments(self.panel.chart.predictions) for p in segment], [0, 1])

    def test_protected_policy_matches_the_run_and_does_not_annotate_snapshot(self):
        cfg = replace(config(), generation=GenerationConfig(2, ("sqrt",), 42))
        run = EvolutionRun(cfg, (SamplePoint(-1, 1), SamplePoint(0, 0), SamplePoint(1, 1)), repairs=RepairConfig())
        run.initialize(); self.panel.set_run(run)
        self.assertEqual([p.y for p in self.panel.chart.predictions], [1, 0, 1])
        self.assertTrue(self.panel.chart.predictions[0].repaired)
        self.assertIn("1 predicciones reparadas", self.panel.note.text())
        self.assertIsNone(self.panel.selected_individual.root.evaluated)

    def test_hover_reads_both_values_of_the_same_sample(self):
        index = len(self.run.reference) // 2
        point = self.panel.chart.reference[index]
        position = self.panel.chart.map_point(point.x, point.y)
        QTest.mouseMove(self.panel.chart, position.toPoint())
        self.app.processEvents()
        self.assertIn(f"referencia = {point.y:.12g}", self.panel.coordinates.text())
        self.assertIn(f"predicción = {self.panel.chart.predictions[index].y:.6g}", self.panel.coordinates.text())


class EliteChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_chart_breaks_lines_at_missing_values_and_never_drops_pairs(self):
        chart = EliteComparisonChart()
        reference = tuple(SamplePoint(x, x*x) for x in (-1, 0, 1))
        predictions = (SamplePoint(-1, -1), SamplePoint(0, None), SamplePoint(1, 1))
        chart.set_data(reference, predictions, "x")
        self.assertEqual(len(chart.segments(predictions)), 2)
        self.assertEqual(chart.predictions, predictions)
        self.assertEqual(chart.reference, reference)

    def test_constant_single_point_and_extreme_axes_render_without_invalid_coordinates(self):
        chart = EliteComparisonChart()
        chart.resize(620, 300)
        for reference, predictions in (
            ((SamplePoint(12, 24),), (SamplePoint(12, 24),)),
            ((SamplePoint(-sys.float_info.max, -1e300), SamplePoint(sys.float_info.max, 1e300)),
             (SamplePoint(-sys.float_info.max, 0), SamplePoint(sys.float_info.max, 0)))):
            chart.set_data(reference, predictions, "x")
            for point in (*reference, *predictions):
                position = chart.map_point(point.x, point.y)
                self.assertTrue(math.isfinite(position.x()) and math.isfinite(position.y()))
                self.assertTrue(chart.plot_rect().adjusted(-1, -1, 1, 1).contains(position))
            self.assertFalse(chart.grab().isNull())

    def test_empty_chart_and_mismatched_x(self):
        chart = EliteComparisonChart()
        self.assertFalse(chart.grab().isNull())
        with self.assertRaises(ValueError):
            chart.set_data((SamplePoint(1, 2),), (SamplePoint(2, 2),), "x")


if __name__ == "__main__":
    unittest.main()
