import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from expression_tree.gui import MainWindow
from expression_tree.evolution import EvolutionRun
from expression_tree.genetics import MUTATIONS
from expression_tree.parsing import detect_and_parse
from expression_tree.tree import to_infix_string, traverse_preorder


class EvolutionGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.show()
        self.window._open_evolution()
        self.evo = self.window.evolution_window
        self.evo.population_size.setValue(12)
        self.evo.reference.setText("x^2+.123")
        self.evo.tolerance.setValue(0)
        self.evo.samples.setValue(21)
        self.app.processEvents()

    def tearDown(self):
        self.evo.running = False
        self.evo.timer.stop()
        self.wait_work()
        self.window.live_timer.stop()
        self.window.anim_timer.stop()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def wait_work(self):
        deadline = time.monotonic() + 10
        while self.evo.busy and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(self.evo.busy, "El trabajador debe terminar sin bloquear la interfaz.")
        self.app.processEvents()

    def initialize(self):
        self.evo.initialize()
        self.wait_work()
        self.assertTrue(self.evo.error.isHidden(), self.evo.error.text())
        self.assertIsNotNone(self.evo.run)

    def test_population_generation_archive_and_inspection_of_real_operations(self):
        e = self.evo
        self.initialize()
        self.assertEqual(e.population_table.rowCount(), 12)
        self.assertTrue(e.next.isEnabled())
        self.assertGreater(e.archive_table.rowCount(), 0)
        e.advance(); self.wait_work()
        self.assertEqual(e.run.generation, 1)
        self.assertEqual(e.history_table.rowCount(), 2)
        self.assertEqual(to_infix_string(e.population_tree.root), e.displayed[0].expression)
        self.assertEqual(e.population_tree.title.text(), f"Genotipo · #{e.displayed[0].id}")
        self.assertEqual(to_infix_string(e.archive_tree.root), e.archive_displayed[0].expression)
        self.assertGreater(e.event_picker.count(), 1)
        e.event_picker.setCurrentIndex(1)
        self.assertIs(e.workspace.currentWidget(), e.algorithm_page)
        self.assertIsNotNone(e.operation_window)
        self.assertEqual(len(e.operation_window.panes), 4)
        self.assertIsNone(e.last_change)

    def test_sus_selection_recovers_after_class_example_and_sets_parents(self):
        e = self.evo
        e.workspace.setCurrentIndex(1)
        e.demo_selection.setCurrentIndex(e.demo_selection.findData("sus"))
        e._example_cross()
        e.select_pair()
        self.assertEqual(len(e.selection_chart.result.pointers), 2)
        self.assertEqual(e.selection_table.rowCount(), 6)
        self.assertIsNotNone(e.parent_a.currentData())
        e.cross_parents()
        self.assertTrue(e.demo_error.isHidden(), e.demo_error.text())
        self.assertIsNotNone(e.cross_panes[2].root)
        selected = e.selection_chart.result
        self.initialize()
        e.advance(); self.wait_work()
        self.assertIs(e.selection_chart.result, selected)
        self.assertEqual(e.selection_table.rowCount(), 6)

    def test_class_cross_and_repair_are_visible(self):
        e = self.evo
        e._example_cross()
        e.cross_parents()
        self.assertEqual(to_infix_string(e.cross_panes[2].root), "2 + 5")
        self.assertEqual(to_infix_string(e.cross_panes[3].root), "3 * x - x / 2")
        e.demo_depth.setValue(1)
        e.cross_parents()
        self.assertIn("reparación", e.cross_note.text())
        self.assertTrue(any(item.highlight_color == "#9D4310" for item in e.cross_panes[3].canvas.node_items.values()))

    def test_switching_example_preserves_recessive_genes_when_opened_in_explorer(self):
        e = self.evo
        e._example_switch()
        e.mutate_tree()
        self.assertEqual(to_infix_string(e.mutation_after.root), "sqrt(x / 5)")
        self.assertTrue(e.mutation_after.canvas.recessive_ids)
        e.mutation_after.open.click()
        root = self.window.root_node
        self.assertEqual(len(root.children), 2)
        self.assertTrue(self.window.canvas.recessive_ids)
        self.window.evaluation.inputs["x"].setValue(20)
        self.assertEqual(self.window.session.result, 2)
        self.window.evaluation.repair.setChecked(False)
        self.assertIs(self.window.root_node, root)
        self.assertEqual(len(root.children), 2)

    def test_all_four_manual_mutations_and_invalid_input_recovery(self):
        e = self.evo
        for method in ("leaf", "operator", "switch", "subtree"):
            e._set_mutation_source(detect_and_parse("2*x+1", "infix", False)[0])
            e.lab_method.setCurrentIndex(e.lab_method.findData(method))
            e.mutate_tree()
            self.assertTrue(e.demo_error.isHidden(), e.demo_error.text())
            self.assertIsNotNone(e.mutation_after.root)
        e.lab_method.setCurrentIndex(e.lab_method.findData("leaf"))
        e.replacement.setText("1 + 2")
        e.mutate_tree()
        self.assertFalse(e.demo_error.isHidden())
        e.replacement.setText("3.2")
        e.mutate_tree()
        self.assertTrue(e.demo_error.isHidden())

    def test_changed_settings_require_new_population_and_reset_archive(self):
        e = self.evo
        self.initialize()
        e.depth.setValue(2)
        self.assertTrue(e.stale)
        self.assertFalse(e.next.isEnabled())
        self.assertFalse(e.play.isEnabled())
        e.initialize(); self.wait_work()
        self.assertFalse(e.stale)
        self.assertEqual(e.run.generation, 0)
        self.assertTrue(all(i.generation == 0 for i in e.run.hall_of_fame))
        e.archive_size.setValue(0)
        e.initialize(); self.wait_work()
        self.assertIsNone(e.archive_tree.root)
        self.assertFalse(e.archive_tree.open.isEnabled())

    def test_csv_reference_uses_exact_x_and_rejects_missing_y(self):
        e = self.evo
        e.source.setCurrentIndex(1)
        self.assertFalse(e.minimum.isEnabled())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "points.csv"
            path.write_text("x,y\n12,24\n13,26\n")
            with patch("expression_tree.ui.evolution.QFileDialog.getOpenFileName", return_value=(str(path), "")):
                e.load_csv()
            self.initialize()
            self.assertEqual([p.x for p in e.run.reference], [12, 13])
            path.write_text("x,y\n12,\n13,26\n")
            with patch("expression_tree.ui.evolution.QFileDialog.getOpenFileName", return_value=(str(path), "")):
                e.load_csv()
            self.assertFalse(e.error.isHidden())

    def test_invalid_reference_and_empty_operators_leave_previous_results_available(self):
        e = self.evo
        self.initialize()
        original = e.run
        e.reference.setText("sqrt(-1)")
        e.protected.setChecked(False)
        e.initialize()
        self.assertFalse(e.error.isHidden())
        self.assertIs(e.run, original)
        e.reference.setText("x")
        for control in e.operators.values():
            control.setChecked(False)
        e.initialize()
        self.assertIn("operador", e.error.text())
        self.assertIs(e.run, original)

    def test_automatic_evolution_stops_at_limit_and_can_pause(self):
        e = self.evo
        e.generations.setValue(2)
        self.initialize()
        e.toggle_running()
        deadline = time.monotonic() + 10
        while (e.running or e.busy) and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertEqual(e.run.generation, 2)
        self.assertFalse(e.running)
        self.assertFalse(e.play.isEnabled())
        self.assertIn("límite", e.status.text())

    def test_sections_and_actions_have_distinct_initial_states(self):
        e = self.evo
        self.assertEqual([e.workspace.tabText(i) for i in range(2)], ["Algoritmo completo", "Demostraciones"])
        self.assertEqual([e.tabs.tabText(i) for i in range(e.tabs.count())], ["Comparación", "Población", "Hall of Fame", "Progreso"])
        self.assertTrue(e.create.isVisible())
        self.assertTrue(e.play.isHidden())
        self.assertTrue(e.next.isHidden())
        self.assertTrue(e.advanced.isHidden())
        self.assertTrue(all(control.isHidden() for control in e.population_tree.view_controls))
        e.advanced_toggle.click()
        self.assertTrue(e.advanced.isVisible())
        e.workspace.setCurrentIndex(1)
        self.assertFalse(e.create.isVisible())
        self.assertFalse(e.settings.isVisible())
        self.assertTrue(e.select.isEnabled())
        self.assertIsNone(e.run)

    def test_primary_action_runs_the_entire_algorithm(self):
        e = self.evo
        e.generations.setValue(2)
        e.cross_probability.setValue(100)
        e.mutation_probability.setValue(100)
        QTest.mouseClick(e.create, Qt.MouseButton.LeftButton)
        deadline = time.monotonic() + 10
        while (e.running or e.busy) and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertIsNotNone(e.run)
        self.assertEqual(e.run.generation, 2)
        self.assertGreater(e.run.history[-1].crossovers, 0)
        self.assertGreater(e.run.history[-1].mutations, 0)
        self.assertEqual(e.run.config.elite_count, 1)
        self.assertTrue(e.run.hall_of_fame)
        self.assertIn("límite", e.status.text())

    def test_mutation_checkboxes_capture_a_subset_and_require_a_new_run_after_changes(self):
        e = self.evo
        self.assertEqual(e.configuration().mutations, tuple(MUTATIONS))
        self.assertTrue(all(control.isChecked() for control in e.mutation_types.values()))
        demo_method = e.lab_method.currentData()
        e.mutation_types["operator"].setChecked(False)
        e.mutation_types["switch"].setChecked(False)
        self.assertEqual(e.mutation_summary.text(), "2 / 4")
        e.mutation_probability.setValue(100)
        e.initialize()
        self.assertTrue(e.busy)
        self.assertTrue(all(not control.isEnabled() for control in e.mutation_types.values()))
        self.wait_work()
        self.assertEqual(e.run.config.mutations, ("leaf", "subtree"))
        e.advance(); self.wait_work()
        changes = [change for event in e.run.events for change in event.mutations]
        self.assertTrue(changes)
        self.assertTrue(all(change.name in ("Hojas", "Subrama aleatoria") for change in changes))
        self.assertTrue(all(control.isEnabled() for control in e.mutation_types.values()))
        e.mutation_types["operator"].setChecked(True)
        self.assertTrue(e.stale)
        self.assertFalse(e.next.isEnabled())
        self.assertFalse(e.play.isEnabled())
        self.assertEqual(e.run.config.mutations, ("leaf", "subtree"))
        self.assertEqual(e.lab_method.currentData(), demo_method)

    def test_no_mutation_types_runs_without_mutations_and_restores_probability_on_enable(self):
        e = self.evo
        e.mutation_probability.setValue(100)
        for control in e.mutation_types.values():
            control.setChecked(False)
        self.assertEqual(e.mutation_summary.text(), "Sin mutación")
        self.assertFalse(e.mutation_probability.isEnabled())
        self.assertEqual(e.configuration().mutations, ())
        self.initialize()
        e.advance(); self.wait_work()
        self.assertFalse(e.mutation_probability.isEnabled())
        self.assertEqual(e.run.history[-1].mutations, 0)
        self.assertTrue(all(not event.mutations for event in e.run.events))
        e.mutation_types["switch"].setChecked(True)
        self.assertTrue(e.mutation_probability.isEnabled())
        self.assertEqual(e.mutation_probability.value(), 100)
        self.assertEqual(e.configuration().mutations, ("switch",))
        self.assertTrue(e.stale)

    def test_comparison_updates_automatically_and_keeps_historical_selection(self):
        e = self.evo
        e.elite.setValue(3)
        self.initialize()
        self.assertEqual(e.comparison.selected_generation, 0)
        self.assertEqual(e.comparison.elite_picker.count(), 3)
        e.advance(); self.wait_work()
        self.assertEqual(e.comparison.selected_generation, 1)
        self.assertEqual(e.comparison.chart.reference, e.run.reference)
        self.assertEqual(e.comparison.chart.predictions, e.run.latest_elite_predictions)
        e.comparison.generation_picker.setCurrentIndex(e.comparison.generation_picker.findData(0))
        historical_id = e.comparison.selected_individual.id
        e.advance(); self.wait_work()
        self.assertEqual(e.comparison.selected_generation, 0)
        self.assertEqual(e.comparison.selected_individual.id, historical_id)
        e.comparison.generation_picker.setCurrentIndex(0)
        self.assertEqual(e.comparison.selected_generation, 2)

    def test_starting_new_run_focuses_comparison_without_affecting_demos(self):
        e = self.evo
        e.generations.setValue(2)
        e._example_switch(); e.mutate_tree()
        demo = to_infix_string(e.mutation_after.root)
        e.tabs.setCurrentIndex(e.tabs.count() - 1)
        e.start_run()
        deadline = time.monotonic() + 10
        while (e.running or e.busy) and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertEqual(e.tabs.currentIndex(), 0)
        self.assertEqual(e.comparison.selected_generation, e.run.generation)
        self.assertEqual(e.comparison.selected_individual.id, e.run.best.id)
        self.assertEqual(to_infix_string(e.mutation_after.root), demo)

    def test_demonstrations_ignore_invalid_formal_settings_and_keep_errors_separate(self):
        e = self.evo
        e.seed.setText("invalid")
        for control in e.operators.values():
            control.setChecked(False)
        e.initialize()
        self.assertFalse(e.error.isHidden())
        e.workspace.setCurrentIndex(1)
        e.select_pair()
        e.cross_parents()
        e._example_switch()
        e.mutate_tree()
        self.assertTrue(e.demo_error.isHidden(), e.demo_error.text())
        self.assertEqual(to_infix_string(e.mutation_after.root), "sqrt(x / 5)")
        self.assertFalse(e.error.isHidden())
        self.assertIsNone(e.run)

    def test_demo_controls_and_randomness_never_change_formal_run(self):
        e = self.evo
        self.initialize()
        run = e.run
        expected = EvolutionRun(run.config, run.reference, variables=run.variables, repairs=run.repairs)
        expected.initialize()
        e.workspace.setCurrentIndex(1)
        e.demo_depth.setValue(2)
        e.demo_selection.setCurrentIndex(2)
        e.select_pair()
        e.cross_parents()
        e._example_switch()
        e.mutate_tree()
        demo_result = to_infix_string(e.mutation_after.root)
        self.assertFalse(e.stale)
        self.assertIs(e.run, run)
        for _ in range(2):
            e.advance(); self.wait_work()
            expected.advance()
        def genes(ind):
            return [(node.kind, node.value, len(node.children)) for node in traverse_preorder(ind.root)]
        self.assertEqual([(genes(i), i.loss) for i in run.population], [(genes(i), i.loss) for i in expected.population])
        self.assertEqual(to_infix_string(e.mutation_after.root), demo_result)
        self.assertFalse(e.stale)

    def test_population_import_is_an_explicit_independent_snapshot(self):
        e = self.evo
        self.initialize()
        e.demo_source.setCurrentIndex(e.demo_source.findData("run"))
        original = [i.expression for i in e.demo_population]
        self.assertEqual(len(e.demo_population), 12)
        self.assertIsNot(e.demo_population[0].root, e.displayed[0].root)
        e.advance(); self.wait_work()
        self.assertEqual([i.expression for i in e.demo_population], original)
        self.assertIn("generación 0", e.demo_population_note.text())
        e.refresh_demo.click()
        self.assertIn("generación 1", e.demo_population_note.text())
        self.assertEqual([i.expression for i in e.demo_population], [i.expression for i in e.displayed])

    def test_switching_to_demos_preserves_run_and_can_pause_on_return(self):
        e = self.evo
        e.start_run()
        e.workspace.setCurrentIndex(1)
        e.select_pair()
        e.workspace.setCurrentIndex(0)
        e.toggle_running()
        self.wait_work()
        generation = e.run.generation
        QTest.qWait(250)
        self.assertEqual(e.run.generation, generation)
        self.assertFalse(e.running)
        e.workspace.setCurrentIndex(0)
        self.assertTrue(e.play.isVisible())
        self.assertEqual(e.play.text(), "Continuar ejecución")
        self.assertTrue(e.next.isVisible())

    def test_continuing_mutation_keeps_source_label_and_root_consistent(self):
        e = self.evo
        e.mutation_source.setCurrentIndex(e.mutation_source.findData("switch"))
        e.mutate_tree()
        result = to_infix_string(e.mutation_after.root)
        e.continue_mutation.click()
        self.assertEqual(e.mutation_source.currentData(), "result")
        self.assertEqual(to_infix_string(e.mutation_root), result)
        self.assertFalse(e.continue_mutation.isEnabled())

    def test_compact_tabs_and_entire_tree_remain_accessible(self):
        e = self.evo
        e.resize(1024, 768)
        self.initialize()
        for index in range(e.tabs.count()):
            e.tabs.setCurrentIndex(index)
            self.app.processEvents()
            self.assertTrue(e.tabs.currentWidget().isVisible())
            self.assertGreater(e.tabs.currentWidget().width(), 500)
        e.workspace.setCurrentIndex(1)
        for index in range(e.lab.count()):
            e.lab.setCurrentIndex(index)
            self.app.processEvents()
            self.assertTrue(e.lab.currentWidget().isVisible())
            self.assertGreater(e.lab.currentWidget().width(), 800)
        e.lab.setCurrentIndex(1)
        e._example_cross(); e.cross_parents()
        QTest.qWait(20)
        for pane in e.cross_panes:
            viewport_rect = pane.canvas.mapToScene(pane.canvas.viewport().rect()).boundingRect()
            for item in pane.canvas.node_items.values():
                self.assertTrue(viewport_rect.contains(item.sceneBoundingRect()))


if __name__ == "__main__":
    unittest.main()
