from __future__ import annotations

from .models import ExprNode
from .operators import BINARY_OPS

def traverse_inorder(root: ExprNode | None) -> list[ExprNode]:
    if root is None:
        return []
    if root.is_leaf:
        return [root]
    if len(root.children) == 1:
        return [root] + traverse_inorder(root.children[0])
    res: list[ExprNode] = []
    res.extend(traverse_inorder(root.children[0]))
    res.append(root)
    for child in root.children[1:]:
        res.extend(traverse_inorder(child))
    return res


def traverse_preorder(root: ExprNode | None) -> list[ExprNode]:
    if root is None:
        return []
    res = [root]
    for child in root.children:
        res.extend(traverse_preorder(child))
    return res


def traverse_postorder(root: ExprNode | None) -> list[ExprNode]:
    if root is None:
        return []
    res: list[ExprNode] = []
    for child in root.children:
        res.extend(traverse_postorder(child))
    res.append(root)
    return res


def traverse_active(root: ExprNode | None) -> list[ExprNode]:
    if root is None:
        return []
    return [root] + [node for child in root.active_children for node in traverse_active(child)]


def to_infix_string(node: ExprNode | None, parent_prec: int = 0, is_right: bool = False) -> str:
    if node is None:
        return ""
    if node.is_leaf:
        if node.kind == "number" and node.value.startswith("-") and parent_prec >= 3:
            return f"({node.value})"
        return node.value
    if node.kind == "unary":
        child = node.children[0]
        inner = to_infix_string(child)
        if child.kind in ("op", "unary"):
            inner = f"({inner})"
        s = f"{'-' if node.value == 'u-' else '+'}{inner}"
        return f"({s})" if parent_prec >= 2 else s
    if node.kind == "func":
        args_str = ", ".join(to_infix_string(c, 0, False) for c in node.active_children)
        return f"{node.value}({args_str})"
    if node.kind == "op":
        prec, assoc, _ = BINARY_OPS.get(node.value, (1, "L", lambda a, b: 0.0))
        left_s = to_infix_string(node.children[0], prec, False)
        right_s = to_infix_string(node.children[1], prec, True)
        s = f"{left_s} {node.value} {right_s}"
        need_parens = prec < parent_prec or (
            prec == parent_prec
            and ((is_right and assoc == "L") or (not is_right and assoc == "R"))
        )
        return f"({s})" if need_parens else s
    return node.value


def extract_variables(root: ExprNode | None) -> list[str]:
    if root is None:
        return []
    found: list[str] = []
    for node in traverse_active(root):
        if node.kind == "variable" and node.value not in found:
            found.append(node.value)
    return found


def compute_tree_layout(
    root: ExprNode | None,
    h_spacing: float = 92.0,
    v_spacing: float = 108.0,
) -> tuple[int, int]:
    if root is None:
        return 0, 0

    subtree_slots: dict[int, float] = {}
    max_depth = 0
    total_nodes = 0

    def measure(node: ExprNode, depth: int) -> float:
        nonlocal max_depth, total_nodes
        total_nodes += 1
        node.depth = depth
        if depth > max_depth:
            max_depth = depth
        if node.is_leaf:
            subtree_slots[node.id] = 1.0
            return 1.0
        if len(node.children) == 1:
            w = max(1.0, measure(node.children[0], depth + 1))
            subtree_slots[node.id] = w
            return w
        total_w = 0.0
        for i, child in enumerate(node.children):
            if i > 0:
                total_w += 0.35
            total_w += measure(child, depth + 1)
        subtree_slots[node.id] = max(1.0, total_w)
        return subtree_slots[node.id]

    measure(root, 0)

    def place(node: ExprNode, left_slot: float) -> None:
        w = subtree_slots[node.id]
        node.y = node.depth * v_spacing
        if node.is_leaf:
            node.x = (left_slot + w / 2.0) * h_spacing
            return
        if len(node.children) == 1:
            place(node.children[0], left_slot)
            node.x = node.children[0].x
            return

        cur = left_slot
        for i, child in enumerate(node.children):
            if i > 0:
                cur += 0.35
            cw = subtree_slots[child.id]
            place(child, cur)
            cur += cw
        node.x = 0.5 * (node.children[0].x + node.children[-1].x)

    place(root, 0.0)

    offset_x = root.x
    for n in traverse_preorder(root):
        n.x -= offset_x

    return total_nodes, max_depth


def tree_height(root: ExprNode | None) -> int:
    """Height in levels: a single leaf has height 1."""
    return 0 if root is None else 1 + max((tree_height(c) for c in root.children), default=0)
