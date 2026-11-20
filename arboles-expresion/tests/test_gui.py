import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from expression_tree.gui import MainWindow
from expression_tree.tree import tree_height, traverse_preorder


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.live_timer.stop()
        self.window.anim_timer.stop()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_generate_parse_curve_and_fold_in_both_directions(self):
        w = self.window
        w.generator.height.setValue(5)
        w.generator.seed.setText("17")
        QTest.mouseClick(w.generator.generate, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertLessEqual(tree_height(w.root_node), 5)
        self.assertEqual(w.expression_input.text().count("("), w.expression_input.text().count(")"))
        self.assertIsNotNone(w.curve.canvas.data)
        original = w.root_node
        result = w.session.result
        w.visible_levels.setValue(1)
        self.assertEqual(len(w.canvas.node_items), 1)
        self.assertIs(w.root_node, original)
        self.assertEqual(w.session.result, result)
        self.assertGreaterEqual(sum(item.collapsed for item in w.canvas.node_items.values()), 1)
        w.visible_levels.setValue(8)
        self.assertEqual(len(w.canvas.node_items), len(traverse_preorder(original)))
        w._load_preset("x 2 ^ 3 +", "postfix")
        self.assertEqual(w.session.result, 4)
        self.assertEqual(w.curve.canvas.data.variable, "x")

    def test_operator_validation_and_seed_reproducibility(self):
        w = self.window
        for control in w.generator.operators.values():
            control.setChecked(False)
        self.assertFalse(w.generator.generate.isEnabled())
        w.generator.operators["sin"].setChecked(True)
        w.generator.seed.setText("42")
        w.generator.request()
        expression = w.expression_input.text()
        w.generator.request()
        self.assertEqual(w.expression_input.text(), expression)
        w.generator.seed.setText("oops")
        self.assertFalse(w.generator.generate.isEnabled())

    def test_variable_and_interpreter_updates(self):
        w = self.window
        w._load_preset("a*x", "infix")
        w.evaluation.inputs["x"].setValue(3)
        w._execute("a = 4")
        self.assertEqual(w.session.result, 12)
        self.assertEqual(w.evaluation.inputs["a"].value(), 4)
        w._execute("a + x")
        self.assertEqual(w.session.result, 7)
        self.assertEqual(w.interpreter.history.count(), 2)

    def test_strict_and_repaired_curves_are_independent(self):
        w = self.window
        w._load_preset("sqrt(x)", "infix")
        self.assertGreater(w.curve.canvas.data.invalid_samples, 0)
        w.curve.repaired.setChecked(True)
        self.assertEqual(w.curve.canvas.data.invalid_samples, 0)
        w.evaluation.inputs["x"].setValue(-4)
        self.assertEqual(w.session.result, 2)
        self.assertTrue(w.root_node.repaired)
        w.curve.repaired.setChecked(False)
        self.assertIsNone(w.curve.canvas.current_point)
        w.curve.repaired.setChecked(True)
        self.assertEqual(w.curve.canvas.current_point, (-4, 2))
        w.evaluation.repair.setChecked(False)
        self.assertIsNone(w.session.result)
        self.assertIsNotNone(w.session.error)
        self.assertEqual(w.curve.canvas.current_point, (-4, 2))

    def test_curve_marker_tracks_selected_variable(self):
        w = self.window
        w._load_preset("x*y", "infix")
        w.evaluation.inputs["x"].setValue(2)
        w.evaluation.inputs["y"].setValue(3)
        w.curve.variable.setCurrentText("y")
        self.assertEqual(w.curve.canvas.current_point, (3, 6))

    def test_invalid_input_preserves_tree_and_recovers(self):
        w = self.window
        original = w.root_node
        w._load_preset("sin(1,2)", "infix")
        self.assertIs(w.root_node, original)
        self.assertFalse(w.error.isHidden())
        w._load_preset("x+1", "infix")
        self.assertTrue(w.error.isHidden())
        self.assertEqual(w.session.result, 2)

    def test_animation_and_export(self):
        w = self.window
        w._step_animation_forward()
        self.assertEqual(w.anim_index, 0)
        self.assertTrue(any(item.visit_order for item in w.canvas.node_items.values()))
        w._stop_animation()
        self.assertTrue(all(item.visit_order is None for item in w.canvas.node_items.values()))
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "tree.png")
            with patch("expression_tree.gui.QFileDialog.getSaveFileName", return_value=(path, "")):
                w._export_png()
            self.assertGreater(Path(path).stat().st_size, 500)

    def test_cosine_preset_csv_and_sampling_controls(self):
        import csv
        w = self.window
        w._example_selected(2)
        self.assertEqual(w.curve.minimum.value(), 0)
        self.assertEqual(w.curve.maximum.value(), 1)
        self.assertEqual(w.curve.step.value(), .001)
        self.assertEqual(len(w.curve.canvas.data.points), 1001)
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "curve.csv")
            with patch("expression_tree.ui.curve.QFileDialog.getSaveFileName", return_value=(path, "")):
                w.curve.export_csv()
            with open(path, newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(len(rows), 1002)
            self.assertEqual(rows[-1][0], "1.000")
        w.curve.step.setValue(.000001)
        self.assertIsNone(w.curve.canvas.data)
        self.assertFalse(w.curve.export.isEnabled())
        w.curve.step.setValue(.001)
        self.assertTrue(w.curve.export.isEnabled())
        w._example_selected(3)
        self.assertTrue(w.session.syntax_repairs)
        self.assertEqual(len(w.curve.canvas.data.points), 1001)

    def test_metrics_expression_and_stale_result_handling(self):
        w = self.window
        w._example_selected(2)
        w._open_metrics()
        metrics = w.metrics_window
        self.assertEqual(metrics.result.metrics.count, 1001)
        self.assertEqual(metrics.result.metrics.values["mse"], 0)
        self.assertEqual(metrics.result.metrics.values["r2"], 1)
        self.assertEqual(metrics.point_model.rowCount(), 1001)
        metrics.reference.setText("y = 6.87 + 11*cos(7.23*x^3) + 1")
        self.assertIsNone(metrics.result)
        metrics.calculate_metrics()
        self.assertAlmostEqual(metrics.result.metrics.values["mse"], 1)
        w.curve.step.setValue(.002)
        self.assertIsNone(metrics.result)
        self.assertEqual(metrics.point_model.rowCount(), 0)
        metrics.reference.setText("sin(1,2)")
        metrics.calculate_metrics()
        self.assertFalse(metrics.error.isHidden())
        self.assertIsNone(metrics.result)
        metrics.close()

    def test_metrics_csv_uses_exact_csv_x_values(self):
        w = self.window
        w._load_preset("2*x", "infix")
        w._open_metrics()
        metrics = w.metrics_window
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.csv"
            path.write_text("x,y\n12,24\n13,26\n")
            with patch("expression_tree.ui.metrics.QFileDialog.getOpenFileName", return_value=(str(path), "")):
                metrics.load_csv()
        self.assertEqual(metrics.result.metrics.count, 2)
        self.assertEqual(metrics.result.metrics.values["mse"], 0)
        self.assertEqual(metrics.point_model.rows[0].x, 12)
        metrics.close()

    def test_compact_size_and_every_tab_are_accessible(self):
        w = self.window
        w.resize(1024, 768)
        self.app.processEvents()
        self.assertLess(w.visual_splitter.width(), w.main_splitter.width())
        self.assertLess(w.curve.canvas.geometry().bottom(), w.curve.note.geometry().top())
        for index in range(w.tabs.count()):
            w.tabs.setCurrentIndex(index)
            self.app.processEvents()
            self.assertTrue(w.tabs.currentWidget().isVisible())
            self.assertGreater(w.tabs.currentWidget().width(), 500)


if __name__ == "__main__":
    unittest.main()
