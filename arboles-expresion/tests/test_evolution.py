import math
import random
import unittest
from dataclasses import replace
from itertools import combinations

from expression_tree.evaluation import evaluate_tree
from expression_tree.evolution import EvolutionConfig, EvolutionRun, Individual, evaluate_individual, select_parents
from expression_tree.generation import GenerationConfig, generate_tree
from expression_tree.genetics import MUTATIONS, at_path, clone_tree, crossover, mutate, repair_tree, tree_paths
from expression_tree.models import RepairConfig
from expression_tree.operators import OPERATORS
from expression_tree.parsing import detect_and_parse
from expression_tree.sampling import SamplePoint
from expression_tree.tree import extract_variables, to_infix_string, traverse_preorder, tree_height


def parse(text):
    return detect_and_parse(text, "infix", False)[0]


def signature(node):
    return node.kind, node.value, tuple(signature(child) for child in node.children)


def check_tree(test, root, config):
    nodes = traverse_preorder(root)
    test.assertLessEqual(tree_height(root), config.max_height)
    test.assertLessEqual(len(nodes), config.max_nodes)
    test.assertEqual(len({node.id for node in nodes}), len(nodes))
    for node in nodes:
        if node.children:
            arity = OPERATORS[node.value].arity
            test.assertTrue(len(node.children) == arity or arity == 1 and len(node.children) == 2)
        else:
            test.assertIn(node.kind, ("number", "constant", "variable"))


class GeneticOperatorTests(unittest.TestCase):
    def test_class_crossover_exchanges_connections_without_changing_parents(self):
        first, second = parse("2+3*x"), parse("5-x/2")
        original = (signature(first), signature(second))
        change = crossover(first, second, GenerationConfig(), random.Random(1), (1,), (0,))
        self.assertEqual([to_infix_string(r) for r in change.after], ["2 + 5", "3 * x - x / 2"])
        self.assertEqual(original, (signature(first), signature(second)))
        change.after[1].children[0].children[0].value = "99"
        self.assertEqual(first.right.left.value, "3")
        self.assertEqual(change.before[0].right.left.value, "3")
        for root in change.after:
            self.assertEqual(len({n.id for n in traverse_preorder(root)}), len(traverse_preorder(root)))

    def test_crossover_uses_edges_and_handles_single_leaf_parents(self):
        with self.assertRaises(ValueError):
            crossover(parse("x+1"), parse("x*2"), GenerationConfig(), random.Random(1), (), (0,))
        change = crossover(parse("3"), parse("x*2"), GenerationConfig(), random.Random(1))
        self.assertFalse(change.applied)
        self.assertEqual(to_infix_string(change.after[0]), "3")

    def test_height_repair_promotes_nearest_operand_and_prefers_left_on_ties(self):
        cfg = GenerationConfig(max_height=3)
        a, b = parse("(5-2)*(3+x)"), parse("(pi + (5*x))-1")
        change = crossover(a, b, cfg, random.Random(1), (1, 1), (0,))
        self.assertEqual(to_infix_string(change.after[0]), "(5 - 2) * (3 + pi)")
        self.assertIn((1, 1), change.repairs[0])
        self.assertGreater(tree_height(change.raw[0]), cfg.max_height)
        check_tree(self, change.after[0], cfg)
        root, _ = repair_tree(parse("(1+2)+(3*4)"), 1)
        self.assertEqual(root.value, "1")
        root, _ = repair_tree(parse("(1+2)+x"), 1)
        self.assertEqual(root.value, "x")  # nearest leaf, not the deepest leftmost leaf

    def test_leaf_mutation_and_invalid_leaf_replacement(self):
        root = parse("3+x")
        change = mutate(root, "leaf", GenerationConfig(), random.Random(2), (0,), operand="3.2")
        self.assertEqual(evaluate_tree(change.after[0], {"x": 1})[0], 4.2)
        with self.assertRaises(ValueError):
            mutate(root, "leaf", GenerationConfig(), random.Random(2), (), operand="5")

    def test_recessive_gene_is_ignored_in_evaluation_variables_and_phenotype(self):
        root = parse("2 * (1/unknown)")
        change = mutate(root, "operator", GenerationConfig(), random.Random(2), (), operator="sqrt")
        root = change.after[0]
        self.assertEqual(len(root.children), 2)
        self.assertEqual(extract_variables(root), [])
        self.assertEqual(to_infix_string(root), "sqrt(2)")
        value, steps, error, _ = evaluate_tree(root, {}, RepairConfig(enabled=False))
        self.assertIsNone(error)
        self.assertAlmostEqual(value, math.sqrt(2))
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[-1].stack_snapshot, [format(value, ".6g")])
        self.assertIsNone(root.right.evaluated)
        self.assertIsNone(root.right.error)

    def test_switching_activates_recessive_gene_and_binary_mutation_restores_it(self):
        root = parse("2*x + x/5")
        root.value, root.kind = "sqrt", "func"
        change = mutate(root, "switch", GenerationConfig(), random.Random(2), ())
        switched = change.after[0]
        self.assertEqual(to_infix_string(switched), "sqrt(x / 5)")
        self.assertEqual(evaluate_tree(switched, {"x": 20})[0], 2)
        restored = mutate(switched, "operator", GenerationConfig(), random.Random(2), (), operator="+").after[0]
        self.assertEqual(evaluate_tree(restored, {"x": 20})[0], 44)

    def test_unary_to_binary_generates_missing_branch(self):
        root = mutate(parse("sqrt(x)"), "operator", GenerationConfig(), random.Random(4), (), operator="+").after[0]
        self.assertEqual(len(root.children), 2)
        self.assertIsNone(evaluate_tree(root, {"x": 1})[2])

    def test_subtree_mutation_includes_root_and_obeys_remaining_depth(self):
        cfg = GenerationConfig(max_height=3, operators=("+", "*"))
        root = parse("(x+2)*(x-1)")
        replacement = mutate(root, "subtree", cfg, random.Random(5), ()).after[0]
        check_tree(self, replacement, cfg)
        replacement = mutate(root, "subtree", cfg, random.Random(5), (0, 0)).after[0]
        self.assertTrue(replacement.left.left.is_leaf)
        self.assertEqual(signature(root.right), signature(replacement.right))

    def test_generated_variation_preserves_structure_and_limits(self):
        for height in (1, 3, 5, 8):
            cfg = GenerationConfig(max_height=height, max_nodes=31)
            for seed in range(12):
                root = generate_tree(replace(cfg, seed=seed))
                other = generate_tree(replace(cfg, seed=seed + 100))
                for method in ("leaf", "operator", "switch", "subtree"):
                    child = mutate(root, method, cfg, random.Random(seed)).after[0]
                    check_tree(self, child, cfg)
                    self.assertIsNone(evaluate_tree(child, {"x": 2})[2])
                    # The phenotype remains a valid expression with identical semantics.
                    self.assertEqual(evaluate_tree(parse(to_infix_string(child)), {"x": 2})[0],
                                     evaluate_tree(child, {"x": 2})[0])
                for child in crossover(root, other, cfg, random.Random(seed)).after:
                    check_tree(self, child, cfg)

    def test_node_budget_repair_also_counts_dormant_branches(self):
        root = parse("(x+1)*(x+2)")
        root.value, root.kind = "sqrt", "func"
        repaired, paths = repair_tree(root, 8, 3)
        check_tree(self, repaired, GenerationConfig(max_height=8, max_nodes=3))
        self.assertTrue(paths)


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.population = [Individual(i, parse("x"), 0, loss=loss) for i, loss in enumerate((0, 1, math.inf))]

    def test_tournament_winner_is_best_of_distinct_contestants(self):
        result = select_parents(self.population, 30, "tournament", random.Random(1), 2)
        for winner, contestants in zip(result.indices, result.contestants):
            self.assertEqual(len(set(contestants)), 2)
            self.assertEqual(self.population[winner].loss, min(self.population[i].loss for i in contestants))

    def test_roulette_probabilities_minimize_error_and_exclude_invalids(self):
        result = select_parents(self.population, 100, "roulette", random.Random(7))
        self.assertEqual(result.probabilities, (2/3, 1/3, 0))
        self.assertNotIn(2, result.indices)
        self.assertGreater(result.indices.count(0), result.indices.count(1))

    def test_sus_has_single_random_start_even_spacing_and_expected_counts(self):
        result = select_parents(self.population, 6, "sus", random.Random(17))
        self.assertEqual(result.indices.count(0), 4)
        self.assertEqual(result.indices.count(1), 2)
        for a, b in zip(result.pointers, result.pointers[1:]):
            self.assertAlmostEqual(b - a, 1/6)

    def test_all_invalid_uses_uniform_probabilities(self):
        for ind in self.population:
            ind.loss = math.inf
        result = select_parents(self.population, 6, "sus", random.Random(17))
        self.assertEqual(result.probabilities, (1/3, 1/3, 1/3))
        self.assertEqual([result.indices.count(i) for i in range(3)], [2, 2, 2])


class EvolutionTests(unittest.TestCase):
    def setUp(self):
        self.points = tuple(SamplePoint(i/10, (i/10)**2 + .123) for i in range(-10, 11))
        self.cfg = EvolutionConfig(GenerationConfig(4, ("+", "-", "*", "sqrt"), 42), population_size=15,
                                   max_generations=4, tolerance=0, mutation_probability=.5)

    def test_reproducibility_population_size_elitism_and_archive(self):
        a, b = EvolutionRun(self.cfg, self.points), EvolutionRun(self.cfg, self.points)
        a.initialize(); b.initialize()
        previous = a.best.loss
        for _ in range(4):
            a.advance(); b.advance()
            self.assertEqual(len(a.population), 15)
            self.assertEqual([signature(i.root) for i in a.population], [signature(i.root) for i in b.population])
            self.assertEqual([i.loss for i in a.population], [i.loss for i in b.population])
            self.assertLessEqual(a.best.loss, previous)
            self.assertEqual(sum(i.origin == "Élite" for i in a.population), 1)
            self.assertLessEqual(len(a.hall_of_fame), self.cfg.hall_of_fame_size)
            self.assertEqual(len({signature(i.root) for i in a.hall_of_fame}), len(a.hall_of_fame))
            self.assertLessEqual(a.hall_of_fame[0].loss, a.best.loss)
            previous = a.best.loss
        self.assertIsNotNone(a.stop_reason)
        a.advance()
        self.assertEqual(a.generation, 4)

    def test_zero_probabilities_elitism_and_archive_can_be_disabled(self):
        run = EvolutionRun(replace(self.cfg, elite_count=0, hall_of_fame_size=0,
                                  mutation_probability=0, crossover_probability=0), self.points)
        run.initialize(); run.advance()
        self.assertEqual(run.hall_of_fame, [])
        self.assertTrue(all(i.origin == "Copia" for i in run.population))
        self.assertEqual((run.history[-1].crossovers, run.history[-1].mutations), (0, 0))

    def test_each_selection_and_mutation_integrates_into_generations(self):
        for selection in ("tournament", "roulette", "sus"):
            for mutation in ("leaf", "operator", "switch", "subtree"):
                run = EvolutionRun(replace(self.cfg, selection=selection, mutations=(mutation,), mutation_probability=1), self.points)
                run.initialize(); run.advance()
                self.assertEqual(len(run.population), self.cfg.population_size)
                for ind in run.population:
                    check_tree(self, ind.root, self.cfg.generation)

    def test_default_pool_uses_all_four_mutations_and_reports_the_actual_type(self):
        self.assertEqual(self.cfg.mutations, tuple(MUTATIONS))
        run = EvolutionRun(replace(self.cfg, mutation_probability=1), self.points)
        run.initialize()
        applied = set()
        for _ in range(4):
            run.advance()
            children = {ind.id: ind for ind in run.population}
            for event in run.events:
                self.assertEqual(len(event.mutations), len(event.children))
                for child_id, change in zip(event.children, event.mutations):
                    child = children[child_id]
                    self.assertEqual(signature(child.root), signature(change.after[0]))
                    if change.applied:
                        applied.add(change.name)
                        self.assertTrue(child.origin.endswith(" + " + change.name.lower()))
        self.assertEqual(applied, set(MUTATIONS.values()))

    def test_every_mutation_subset_keeps_valid_trees_and_one_attempt_per_child(self):
        for count in range(5):
            for active in combinations(MUTATIONS, count):
                with self.subTest(active=active):
                    cfg = replace(self.cfg, mutations=active, mutation_probability=1, elite_count=2)
                    run = EvolutionRun(cfg, self.points)
                    run.initialize()
                    for _ in range(2):
                        run.advance()
                        changes = [change for event in run.events for change in event.mutations]
                        self.assertEqual(len(changes), cfg.population_size - cfg.elite_count if active else 0)
                        self.assertTrue(all(change.name in {MUTATIONS[key] for key in active} for change in changes))
                        self.assertEqual(run.history[-1].mutations, sum(change.applied for change in changes))
                        self.assertEqual(sum(ind.origin == "Élite" for ind in run.population), 2)
                        for ind in run.population:
                            check_tree(self, ind.root, cfg.generation)

    def test_hall_of_fame_is_independent_and_survives_population_loss(self):
        run = EvolutionRun(replace(self.cfg, elite_count=0), self.points)
        run.initialize()
        old_best = signature(run.hall_of_fame[0].root)
        self.assertFalse(any(run.hall_of_fame[0].root is ind.root for ind in run.population))
        for ind in run.population:
            ind.root = parse("999")
            ind.loss = 1e6
        run.advance()
        self.assertEqual(signature(run.hall_of_fame[0].root), old_best)

    def test_invalid_prediction_is_never_rewarded_by_dropping_points(self):
        individual = Individual(1, parse("sqrt(x)"), 0)
        evaluate_individual(individual, self.points, {}, "x", RepairConfig(enabled=False), "mse")
        self.assertEqual(individual.loss, math.inf)
        self.assertIn("10 de 21", individual.error)
        evaluate_individual(individual, self.points, {}, "x", RepairConfig(), "mse")
        self.assertTrue(math.isfinite(individual.loss))
        self.assertEqual(individual.repaired_samples, 10)

    def test_r2_is_maximized_by_minimizing_one_minus_r2(self):
        individual = Individual(1, parse("x^2+.123"), 0)
        evaluate_individual(individual, self.points, {}, "x", RepairConfig(), "r2")
        self.assertEqual(individual.loss, 0)
        self.assertEqual(individual.metrics["r2"], 1)
        run = EvolutionRun(replace(self.cfg, tolerance=1e99), self.points)
        run.initialize()
        self.assertIn("objetivo", run.stop_reason)
        run.advance()
        self.assertEqual(run.generation, 0)

    def test_configuration_and_reference_validation(self):
        invalid = [replace(self.cfg, elite_count=15), replace(self.cfg, mutation_probability=1.1),
                   replace(self.cfg, mutations=("unknown",)), replace(self.cfg, mutations=("leaf", "leaf")),
                   replace(self.cfg, mutations="leaf"),
                   replace(self.cfg, selection="ranking"), replace(self.cfg, tolerance=float("nan")),
                   replace(self.cfg, population_size=1), replace(self.cfg, hall_of_fame_size=-1)]
        for cfg in invalid:
            with self.assertRaises(ValueError):
                EvolutionRun(cfg, self.points)
        for points in ((), (SamplePoint(0, None),), (SamplePoint(float("inf"), 2),)):
            with self.assertRaises(ValueError):
                EvolutionRun(self.cfg, points)
        for metric in ("nmse", "r2"):
            with self.assertRaises(ValueError):
                EvolutionRun(replace(self.cfg, metric=metric), (SamplePoint(0, 1), SamplePoint(1, 1)))


if __name__ == "__main__":
    unittest.main()
