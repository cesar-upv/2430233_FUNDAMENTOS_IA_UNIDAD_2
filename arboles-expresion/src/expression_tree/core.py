"""Public compatibility imports; implementation lives in focused engine modules."""
from .models import EvalStep, ExprNode, ParseError, RepairConfig, format_number
from .operators import BINARY_OPS, CONSTANTS, FUNCTIONS, GENERATOR_OPERATORS, OPERATORS, OperatorSpec
from .parsing import NodeFactory, detect_and_parse, parse_infix, parse_postfix, parse_prefix, repair_infix_tokens, tokenize
from .evaluation import evaluate_tree, rewrite_tree_with_structural_repairs
from .tree import compute_tree_layout, extract_variables, to_infix_string, traverse_inorder, traverse_postorder, traverse_preorder, tree_height
from .generation import GenerationConfig, generate_tree
from .plotting import CurveData, sample_curve

from .sampling import SamplePoint, SamplingConfig, sample_points
from .csv_io import read_points_csv, write_points_csv
from .metrics import METRICS, calculate_metrics, compare_against_points
