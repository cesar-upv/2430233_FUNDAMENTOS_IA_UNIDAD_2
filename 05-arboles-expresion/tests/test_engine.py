import math
import unittest
from dataclasses import replace

from expression_tree.core import (
    GENERATOR_OPERATORS, GenerationConfig, ParseError, RepairConfig, detect_and_parse,
    evaluate_tree, extract_variables, generate_tree, rewrite_tree_with_structural_repairs,
    format_number, sample_curve, to_infix_string, traverse_postorder, traverse_preorder, tree_height,
)
from expression_tree.session import ExpressionSession


def parse(expression, mode="infix", repair=False):
    return detect_and_parse(expression, mode, repair)[0]


def shape(node):
    return node.kind, node.value, tuple(shape(child) for child in node.children)


class ParserTests(unittest.TestCase):
    def test_math_precedence_and_scientific_notation(self):
        for text, expected in (("-2^2", -4), ("2^-3", .125), ("(-2)^2", 4), ("2^3^2", 512), ("1e-6 + 2E+2", 200.000001), ("sen(pi/2)", 1), ("8 mod 3", 2), ("1.01^61", 1.01**61)):
            with self.subTest(text=text):
                value, _, error, _ = evaluate_tree(parse(text), {}, RepairConfig(enabled=False))
                self.assertIsNone(error)
                self.assertAlmostEqual(value, expected)

    def test_round_trip_preserves_tree_in_all_notations(self):
        for text in ("-(2*3)", "(-2)^2", "2^-3", "(x^2)^3", "x-(2-3)", "x/(2/3)", "sen(-x) + x ^ 2 / 6", "-(x + 2) * -x"):
            root = parse(text)
            with self.subTest(text=text):
                self.assertEqual(shape(root), shape(parse(to_infix_string(root))))
                for mode, traverse in (("prefix", traverse_preorder), ("postfix", traverse_postorder)):
                    expression = " ".join(n.token_label for n in traverse(root))
                    self.assertEqual(shape(root), shape(parse(expression, mode)))

    def test_negative_scientific_atoms_in_prefix_and_postfix(self):
        for expression, mode in (("-1e-3 2 *", "postfix"), ("* -1e-3 2", "prefix")):
            root = parse(expression, mode)
            self.assertAlmostEqual(evaluate_tree(root, {})[0], -.002)
            self.assertAlmostEqual(evaluate_tree(parse(to_infix_string(root)), {})[0], -.002)

    def test_repairs_are_reported_and_strict_mode_rejects(self):
        expression = "(3 + * 5) 2 + sqrt(-9"
        with self.assertRaises(ParseError):
            parse(expression)
        root, _, notes = detect_and_parse(expression, "infix", True)
        self.assertTrue(notes)
        self.assertEqual(evaluate_tree(root, {})[0], 33)

    def test_limits_and_invalid_tokens(self):
        for expression in ("1e999", "1..2", "__import__('os')", "(" * 2000 + "1" + ")" * 2000, "+".join(["1"] * 600)):
            with self.subTest(expression=expression[:30]), self.assertRaises(ParseError):
                parse(expression)


class EvaluationTests(unittest.TestCase):
    def test_domain_repairs_and_strict_domain_errors(self):
        for expression, expected in (("sqrt(-16)", 4), ("12/(5-5)", 0), ("ln(-e^2)", 2), ("(-9)^.5", 3), ("log(0)", -6), ("asin(2)", math.pi/2), ("tan(pi/2)", 0)):
            with self.subTest(expression=expression):
                root = parse(expression)
                value, steps, error, notes = evaluate_tree(root, {})
                self.assertIsNone(error)
                self.assertAlmostEqual(value, expected)
                self.assertTrue(notes)
                self.assertEqual(steps[-1].stack_snapshot, [format_number(value)])
                self.assertIsNotNone(evaluate_tree(root, {}, RepairConfig(enabled=False))[2])

    def test_zero_policies_and_explicit_rewrite_agree(self):
        for strategy, expected in (("zero", 0), ("epsilon", 2000000), ("numerator", 2), ("one", 1)):
            cfg = RepairConfig(div_zero_strategy=strategy)
            root = parse("2 / 0")
            self.assertEqual(evaluate_tree(root, {}, cfg)[0], expected)
            expression, changes = rewrite_tree_with_structural_repairs(root, {}, cfg)
            self.assertTrue(changes)
            self.assertAlmostEqual(evaluate_tree(parse(expression), {}, RepairConfig(enabled=False))[0], expected)

    def test_rewrite_respects_root_policy_and_modulo_sign(self):
        for text, cfg in (("sqrt(-9)", RepairConfig(neg_root_strategy="zero")), ("(-9)^.5", RepairConfig(neg_root_strategy="zero")), ("-3 % 0", RepairConfig(div_zero_strategy="epsilon"))):
            root = parse(text)
            expected = evaluate_tree(root, {}, cfg)[0]
            expression, _ = rewrite_tree_with_structural_repairs(root, {}, cfg)
            self.assertAlmostEqual(evaluate_tree(parse(expression), {}, RepairConfig(enabled=False))[0], expected)

    def test_overflow_is_bounded_and_preserves_sign(self):
        for text, expected in (("(-2)^1001", -1e12), ("10^1000", 1e12), ("exp(1000)", 1e12), ("0^-10000", 0)):
            value, _, error, notes = evaluate_tree(parse(text), {})
            self.assertIsNone(error)
            self.assertEqual(value, expected)
            self.assertTrue(notes)
        self.assertIsNotNone(evaluate_tree(parse("10^1000"), {}, RepairConfig(enabled=False))[2])

    def test_undefined_and_nonfinite_variables(self):
        root = parse("x+1")
        self.assertIsNotNone(evaluate_tree(root, {})[2])
        self.assertIsNotNone(evaluate_tree(root, {"x": float("inf")}, RepairConfig(enabled=False))[2])


class GeneratorTests(unittest.TestCase):
    def test_height_budget_operators_variable_and_roundtrip(self):
        for height in range(1, 9):
            for seed in range(25):
                selected = ("+", "sqrt", "sin") if seed % 2 else GENERATOR_OPERATORS
                root = generate_tree(GenerationConfig(height, selected, seed))
                self.assertLessEqual(tree_height(root), height)
                self.assertLessEqual(len(traverse_preorder(root)), 63)
                self.assertIn("x", extract_variables(root))
                self.assertTrue(all(n.value in selected for n in traverse_preorder(root) if n.children))
                self.assertEqual(shape(root), shape(parse(to_infix_string(root))))

    def test_seed_is_reproducible_and_configuration_validated(self):
        cfg = GenerationConfig(seed=42)
        self.assertEqual(shape(generate_tree(cfg)), shape(generate_tree(cfg)))
        for cfg in (GenerationConfig(operators=()), GenerationConfig(max_height=0), GenerationConfig(operators=("eval",)), GenerationConfig(max_nodes=0)):
            with self.assertRaises(ValueError):
                generate_tree(cfg)


class CurveTests(unittest.TestCase):
    def test_sampling_is_pure_and_handles_holes(self):
        root = parse("sqrt(x)")
        evaluate_tree(root, {"x": -4})
        original = [(n.evaluated, n.repaired, n.repair_note) for n in traverse_preorder(root)]
        strict = sample_curve(root, {"x": -4}, x_min=-5, x_max=5)
        fixed = sample_curve(root, {"x": -4}, x_min=-5, x_max=5, repair_config=RepairConfig())
        self.assertGreater(strict.invalid_samples, 0)
        self.assertEqual(fixed.invalid_samples, 0)
        self.assertGreater(fixed.repaired_samples, 0)
        self.assertEqual(original, [(n.evaluated, n.repaired, n.repair_note) for n in traverse_preorder(root)])

    def test_poles_do_not_connect_across_asymptotes(self):
        for expression in ("1/x", "tan(x)"):
            data = sample_curve(parse(expression), {}, x_min=-4, x_max=4)
            self.assertGreater(len(data.segments), 1)
            if expression == "1/x":
                self.assertTrue(all(not (segment[0][0] < 0 < segment[-1][0]) for segment in data.segments))

    def test_no_domain_constant_and_invalid_intervals(self):
        self.assertEqual(sample_curve(parse("sqrt(-1)"), {}).valid_samples, 0)
        data = sample_curve(parse("3"), {})
        self.assertEqual(data.valid_samples, 601)
        self.assertLess(data.y_min, 3)
        self.assertGreater(data.y_max, 3)
        with self.assertRaises(ValueError):
            sample_curve(parse("x"), {}, x_min=5, x_max=1)


class SessionTests(unittest.TestCase):
    def test_interpreter_assignment_updates_existing_tree(self):
        session = ExpressionSession()
        session.parse("x+a")
        session.execute("a = 3")
        self.assertEqual(session.result, 4)
        session.execute("a * 2")
        self.assertEqual(session.result, 6)
        for command in ("sin = 3", "pi = 2", "x = unknown"):
            with self.assertRaises(ParseError):
                session.execute(command)

    def test_failed_parse_preserves_last_valid_tree(self):
        session = ExpressionSession()
        session.parse("x+2")
        before = session.root
        with self.assertRaises(ParseError):
            session.parse("sin(1,2)")
        self.assertIs(session.root, before)


if __name__ == "__main__":
    unittest.main()
