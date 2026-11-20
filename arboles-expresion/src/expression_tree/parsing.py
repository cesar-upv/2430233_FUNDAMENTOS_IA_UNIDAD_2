from __future__ import annotations

import math
import re

from .models import ExprNode, ParseError
from .operators import CONSTANTS, FUNCTIONS, BINARY_OPS, canonical_token

def _is_number_token(tok: str) -> bool:
    try:
        float(tok)
        return True
    except ValueError:
        return False


def _is_identifier_token(tok: str) -> bool:
    return bool(tok) and (tok[0].isalpha() or tok[0] in ("_", "π"))


def tokenize(expr: str, allow_unknown_strip: bool = False) -> tuple[list[str], list[str]]:
    """
    Tokenize expression and optionally strip unrecognized characters with repair notes.
    Returns (tokens, syntax_repairs).
    """
    repairs: list[str] = []
    expr = expr.strip()
    if not expr:
        return [], repairs

    expr = (
        expr.replace("**", "^")
        .replace("×", "*")
        .replace("÷", "/")
        .replace("−", "-")
        .replace("[", "(")
        .replace("]", ")")
        .replace("{", "(")
        .replace("}", ")")
    )
    tokens: list[str] = []
    i = 0
    n = len(expr)
    while i < n:
        ch = expr[i]
        if ch.isspace():
            i += 1
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and expr[i + 1].isdigit()):
            match = re.match(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", expr[i:])
            token = match.group()
            tokens.append(token)
            i += len(token)
            continue
        if ch.isalpha() or ch in ("_", "π"):
            start = i
            i += 1
            while i < n and (expr[i].isalnum() or expr[i] in ("_", "π")):
                i += 1
            tokens.append(canonical_token(expr[start:i]))
            continue
        if ch in "+-*/%^(),":
            tokens.append(ch)
            i += 1
            continue
        if allow_unknown_strip:
            repairs.append(f"Carácter inválido '{ch}' eliminado en posición {i + 1}")
            i += 1
            continue
        raise ParseError(f"Carácter no reconocido: '{ch}' en posición {i + 1}")
    return tokens, repairs


def repair_infix_tokens(tokens: list[str]) -> tuple[list[str], list[str]]:
    """
    Repairs common syntactic errors in infix token streams:
    - Empty parentheses `()` -> `( 0 )`
    - Missing function parentheses `sqrt -9` or `sin x` -> `sqrt ( -9 )`, `sin ( x )`
    - Unbalanced parentheses `((a + b)` or `a + b)`
    - Implicit multiplication `2(x + 1)`, `(a+b)(c+d)`, `3x`, `2pi`
    - Consecutive binary operators `3 + * 5` -> `3 * 5`
    - Leading or trailing binary operators `* 5 + 2` or `3 + 5 *` -> neutral element or trim
    """
    repairs: list[str] = []
    if not tokens:
        return ["0"], ["Expresión vacía reemplazada por 0"]

    # 1. Balance parentheses
    balanced: list[str] = []
    open_count = 0
    prepend_opens = 0
    for tok in tokens:
        if tok == "(":
            open_count += 1
            balanced.append(tok)
        elif tok == ")":
            if open_count > 0:
                open_count -= 1
                balanced.append(tok)
            else:
                prepend_opens += 1
                balanced.append(tok)
        else:
            balanced.append(tok)

    if prepend_opens > 0:
        balanced = ["("] * prepend_opens + balanced
        repairs.append(
            f"Se agregó {prepend_opens} paréntesis de apertura '(' faltante(s) al inicio"
        )
    if open_count > 0:
        balanced = balanced + [")"] * open_count
        repairs.append(
            f"Se cerró automáticamente {open_count} paréntesis ')' faltante(s) al final"
        )

    # 2. Wrap bare function arguments when user writes `sqrt -16` or `sqrt 16` without `(`
    func_fixed: list[str] = []
    i = 0
    while i < len(balanced):
        tok = balanced[i]
        low = tok.lower()
        if low in FUNCTIONS and (i + 1 >= len(balanced) or balanced[i + 1] != "("):
            arity, _ = FUNCTIONS[low]
            func_fixed.append(tok)
            func_fixed.append("(")
            if i + 1 < len(balanced):
                # Consume optional unary sign + next atom
                i += 1
                if balanced[i] in ("+", "-") and i + 1 < len(balanced):
                    func_fixed.append(balanced[i])
                    i += 1
                func_fixed.append(balanced[i])
                if arity == 2:
                    func_fixed.extend([",", "0"])
            else:
                func_fixed.extend(["0"] if arity == 1 else ["0", ",", "0"])
            func_fixed.append(")")
            repairs.append(f"Se agregaron paréntesis faltantes a la función '{tok}(...)'")
        else:
            func_fixed.append(tok)
        i += 1

    # 3. Replace empty parentheses `()` with `(0)`
    non_empty: list[str] = []
    i = 0
    while i < len(func_fixed):
        if func_fixed[i] == "(" and i + 1 < len(func_fixed) and func_fixed[i + 1] == ")":
            # Check if preceded by a function
            prev = non_empty[-1].lower() if non_empty else ""
            arity = FUNCTIONS[prev][0] if prev in FUNCTIONS else 1
            non_empty.append("(")
            if arity == 2:
                non_empty.extend(["0", ",", "0"])
            else:
                non_empty.append("0")
            non_empty.append(")")
            repairs.append("Paréntesis vacíos '()' completados con operando neutro 0")
            i += 2
        else:
            non_empty.append(func_fixed[i])
            i += 1

    # 4. Insert implicit multiplication `*`:
    #    e.g., `2 (x)` -> `2 * (x)`, `(a)(b)` -> `(a) * (b)`, `3 x` -> `3 * x`, `) 2` -> `) * 2`
    mult_fixed: list[str] = []
    for idx, tok in enumerate(non_empty):
        if mult_fixed:
            prev = mult_fixed[-1]
            prev_is_val = (
                _is_number_token(prev)
                or (_is_identifier_token(prev) and prev.lower() not in FUNCTIONS)
                or prev == ")"
            )
            curr_is_val_or_open = (
                _is_number_token(tok)
                or _is_identifier_token(tok)
                or tok == "("
            )
            if prev_is_val and curr_is_val_or_open:
                mult_fixed.append("*")
                repairs.append(f"Multiplicación implícita insertada: '{prev} * {tok}'")
        mult_fixed.append(tok)

    # 5. Repair consecutive binary operators or leading/trailing binary operators
    cleaned: list[str] = []
    for tok in mult_fixed:
        if tok in BINARY_OPS:
            if not cleaned or cleaned[-1] in ("(", ","):
                if tok in ("+", "-"):
                    # Valid unary operator
                    cleaned.append(tok)
                else:
                    neutral = "1" if tok in ("*", "/", "^") else "0"
                    cleaned.append(neutral)
                    cleaned.append(tok)
                    repairs.append(
                        f"Operando neutro '{neutral}' insertado antes del operador '{tok}'"
                    )
            elif cleaned[-1] in BINARY_OPS:
                if tok in ("+", "-"):
                    # Keep as unary sign on next operand
                    cleaned.append(tok)
                else:
                    old_op = cleaned[-1]
                    cleaned[-1] = tok
                    repairs.append(
                        f"Operadores consecutivos '{old_op} {tok}' reparados como '{tok}'"
                    )
            else:
                cleaned.append(tok)
        elif tok in (")", ","):
            # If preceded by binary/unary operator, insert neutral operand before closing
            if cleaned and cleaned[-1] in BINARY_OPS:
                last_op = cleaned[-1]
                neutral = "1" if last_op in ("*", "/", "^") else "0"
                cleaned.append(neutral)
                repairs.append(
                    f"Operando faltante completado con '{neutral}' después de '{last_op}'"
                )
            cleaned.append(tok)
        else:
            cleaned.append(tok)

    # Check if expression ends with a dangling operator
    if cleaned and cleaned[-1] in BINARY_OPS:
        last_op = cleaned[-1]
        neutral = "1" if last_op in ("*", "/", "^") else "0"
        cleaned.append(neutral)
        repairs.append(
            f"Expresión incompleta al final: se agregó '{neutral}' tras '{last_op}'"
        )

    return cleaned, repairs


class NodeFactory:
    def __init__(self) -> None:
        self._counter = 0

    def create(
        self,
        value: str,
        kind: str,
        children: list[ExprNode] | None = None,
        num_value: float | None = None,
    ) -> ExprNode:
        self._counter += 1
        return ExprNode(
            id=self._counter,
            value=value,
            kind=kind,
            children=children or [],
            num_value=num_value,
        )

    def create_atom(self, token: str) -> ExprNode:
        try:
            val = float(token)
            if not math.isfinite(val):
                raise ParseError("El número es demasiado grande; usa un valor finito.")
            return self.create(token, "number", num_value=val)
        except ValueError:
            pass
        low = token.lower()
        if low in CONSTANTS:
            return self.create(token, "constant", num_value=CONSTANTS[low])
        if low in FUNCTIONS or token in BINARY_OPS or token in ("(", ")", ","):
            raise ParseError(f"Token inesperado como operando: '{token}'")
        if not token.isidentifier() and token != "π":
            raise ParseError(f"Operando no válido: '{token}'")
        return self.create(token, "variable")


def parse_infix(tokens: list[str], factory: NodeFactory) -> ExprNode:
    if not tokens:
        raise ParseError("La expresión está vacía.")

    pos = 0

    def peek() -> str | None:
        return tokens[pos] if pos < len(tokens) else None

    def consume(expected: str | None = None) -> str:
        nonlocal pos
        tok = peek()
        if tok is None:
            if expected:
                raise ParseError(f"Se esperaba '{expected}' al final de la expresión.")
            raise ParseError("Fin inesperado de la expresión.")
        if expected is not None and tok != expected:
            raise ParseError(f"Se esperaba '{expected}', pero se encontró '{tok}'.")
        pos += 1
        return tok

    def parse_expr() -> ExprNode:
        node = parse_term()
        while peek() in ("+", "-"):
            op = consume()
            right = parse_term()
            node = factory.create(op, "op", [node, right])
        return node

    def parse_term() -> ExprNode:
        node = parse_unary()
        while peek() in ("*", "/", "%"):
            op = consume()
            right = parse_unary()
            node = factory.create(op, "op", [node, right])
        return node

    def parse_unary() -> ExprNode:
        if peek() in ("+", "-"):
            op = consume()
            operand = parse_unary()
            if op == "-":
                return factory.create("u-", "unary", [operand])
            return operand
        return parse_power()

    def parse_power() -> ExprNode:
        node = parse_primary()
        if peek() == "^":
            op = consume()
            right = parse_unary()
            node = factory.create(op, "op", [node, right])
        return node

    def parse_primary() -> ExprNode:
        tok = peek()
        if tok is None:
            raise ParseError("Se esperaba un número, variable o subexpresión.")
        if tok == "(":
            consume("(")
            if peek() == ")":
                raise ParseError("Paréntesis vacíos '()' no permitidos.")
            node = parse_expr()
            consume(")")
            return node
        if tok in (")", ",") or tok in BINARY_OPS:
            raise ParseError(f"Token inesperado '{tok}'.")

        consume()
        low = tok.lower()
        if low in FUNCTIONS:
            arity, _ = FUNCTIONS[low]
            if peek() != "(":
                raise ParseError(f"La función '{tok}' requiere paréntesis, ej: {tok}(x).")
            consume("(")
            args: list[ExprNode] = []
            if peek() == ")":
                raise ParseError(f"La función '{tok}' requiere {arity} argumento(s).")
            args.append(parse_expr())
            while peek() == ",":
                consume(",")
                args.append(parse_expr())
            consume(")")
            if len(args) != arity:
                raise ParseError(
                    f"La función '{tok}' espera {arity} argumento(s), pero recibió {len(args)}."
                )
            return factory.create(low, "func", args)

        return factory.create_atom(tok)

    root = parse_expr()
    if pos < len(tokens):
        raise ParseError(f"Token inesperado '{tokens[pos]}' después de completar la expresión.")
    return root


def _tokenize_space_or_std(expr: str, allow_repair: bool = False) -> tuple[list[str], list[str]]:
    expr = expr.strip()
    if not expr:
        return [], []
    raw_parts = expr.split()
    repairs: list[str] = []
    if len(raw_parts) > 1:
        result: list[str] = []
        for part in raw_parts:
            if part in ("-u", "u-"):
                result.append("u-")
            elif _is_number_token(part):
                result.append(part)
            else:
                sub_toks, sub_rep = tokenize(part, allow_unknown_strip=allow_repair)
                result.extend(sub_toks)
                repairs.extend(sub_rep)
        return result, repairs
    return tokenize(expr, allow_unknown_strip=allow_repair)


def parse_postfix(
    expr: str, factory: NodeFactory, allow_repair: bool = False
) -> tuple[ExprNode, list[str]]:
    tokens, repairs = _tokenize_space_or_std(expr, allow_repair=allow_repair)
    if not tokens:
        raise ParseError("La expresión postfija está vacía.")
    stack: list[ExprNode] = []
    for tok in tokens:
        low = tok.lower()
        if tok in ("(", ")", ","):
            if allow_repair:
                repairs.append(f"Delimitador '{tok}' ignorado en modo postfijo")
                continue
            raise ParseError("La notación postfija no debe contener paréntesis ni comas.")
        if tok in ("u-", "-u", "~"):
            if len(stack) < 1:
                if allow_repair:
                    stack.append(factory.create("0", "number", num_value=0.0))
                    repairs.append("Operando 0 insertado para negación unaria en pila vacía")
                else:
                    raise ParseError("Falta operando para el operador unario '-'.")
            child = stack.pop()
            stack.append(factory.create("u-", "unary", [child]))
        elif tok in BINARY_OPS:
            if len(stack) < 2:
                if allow_repair:
                    neutral = 1.0 if tok in ("*", "/", "^") else 0.0
                    neutral_s = "1" if neutral == 1.0 else "0"
                    while len(stack) < 2:
                        stack.insert(0, factory.create(neutral_s, "number", num_value=neutral))
                    repairs.append(
                        f"Operando neutro '{neutral_s}' agregado en la pila para el operador '{tok}'"
                    )
                else:
                    raise ParseError(f"Faltan operandos en la pila para el operador '{tok}'.")
            right = stack.pop()
            left = stack.pop()
            stack.append(factory.create(tok, "op", [left, right]))
        elif low in FUNCTIONS:
            arity, _ = FUNCTIONS[low]
            if len(stack) < arity:
                if allow_repair:
                    while len(stack) < arity:
                        stack.append(factory.create("0", "number", num_value=0.0))
                    repairs.append(
                        f"Argumento(s) faltante(s) completados con 0 para la función '{tok}'"
                    )
                else:
                    raise ParseError(f"Faltan argumentos en la pila para la función '{tok}'.")
            args = [stack.pop() for _ in range(arity)][::-1]
            stack.append(factory.create(low, "func", args))
        else:
            stack.append(factory.create_atom(tok))

    if len(stack) > 1:
        if allow_repair:
            while len(stack) > 1:
                right = stack.pop()
                left = stack.pop()
                stack.append(factory.create("+", "op", [left, right]))
            repairs.append("Subárboles sueltos en la pila postfija unidos con '+'")
        else:
            raise ParseError(
                f"Expresión postfija inválida: quedaron {len(stack)} elementos en la pila (faltan operadores)."
            )
    return stack[0], repairs


def parse_prefix(
    expr: str, factory: NodeFactory, allow_repair: bool = False
) -> tuple[ExprNode, list[str]]:
    tokens, repairs = _tokenize_space_or_std(expr, allow_repair=allow_repair)
    if not tokens:
        raise ParseError("La expresión prefija está vacía.")
    stack: list[ExprNode] = []
    for tok in reversed(tokens):
        low = tok.lower()
        if tok in ("(", ")", ","):
            if allow_repair:
                repairs.append(f"Delimitador '{tok}' ignorado en modo prefijo")
                continue
            raise ParseError("La notación prefija no debe contener paréntesis ni comas.")
        if tok in ("u-", "-u", "~"):
            if len(stack) < 1:
                if allow_repair:
                    stack.append(factory.create("0", "number", num_value=0.0))
                    repairs.append("Operando 0 insertado para operador unario prefijo")
                else:
                    raise ParseError("Falta operando para el operador unario '-'.")
            child = stack.pop()
            stack.append(factory.create("u-", "unary", [child]))
        elif tok in BINARY_OPS:
            if len(stack) < 2:
                if allow_repair:
                    neutral = 1.0 if tok in ("*", "/", "^") else 0.0
                    neutral_s = "1" if neutral == 1.0 else "0"
                    while len(stack) < 2:
                        stack.append(factory.create(neutral_s, "number", num_value=neutral))
                    repairs.append(
                        f"Operando neutro '{neutral_s}' insertado para el operador prefijo '{tok}'"
                    )
                else:
                    raise ParseError(f"Faltan operandos para el operador prefijo '{tok}'.")
            left = stack.pop()
            right = stack.pop()
            stack.append(factory.create(tok, "op", [left, right]))
        elif low in FUNCTIONS:
            arity, _ = FUNCTIONS[low]
            if len(stack) < arity:
                if allow_repair:
                    while len(stack) < arity:
                        stack.append(factory.create("0", "number", num_value=0.0))
                    repairs.append(
                        f"Argumento faltante completado con 0 para la función prefija '{tok}'"
                    )
                else:
                    raise ParseError(f"Faltan argumentos para la función prefija '{tok}'.")
            args = [stack.pop() for _ in range(arity)]
            stack.append(factory.create(low, "func", args))
        else:
            stack.append(factory.create_atom(tok))

    if len(stack) > 1:
        if allow_repair:
            while len(stack) > 1:
                left = stack.pop()
                right = stack.pop()
                stack.append(factory.create("+", "op", [left, right]))
            repairs.append("Subárboles sueltos en notación prefija unidos con '+'")
        else:
            raise ParseError(
                f"Expresión prefija inválida: quedaron {len(stack)} subárboles sin conectar."
            )
    return stack[0], repairs


def _detect_and_parse(
    expr: str, mode: str = "auto", allow_syntax_repair: bool = True
) -> tuple[ExprNode, str, list[str]]:
    """
    Parse an expression in 'auto', 'infix', 'prefix', or 'postfix' mode.
    If `allow_syntax_repair` is True, repairs malformed syntax when strict parsing fails.
    Returns (root_node, detected_mode, syntax_repairs).
    """
    expr = expr.strip()
    if not expr:
        raise ParseError("Ingresa una expresión matemática para construir el árbol.")

    def _parse_infix_mode(strict_first: bool = True) -> tuple[ExprNode, list[str]]:
        if strict_first:
            try:
                toks, _ = tokenize(expr, allow_unknown_strip=False)
                return parse_infix(toks, NodeFactory()), []
            except ParseError:
                if not allow_syntax_repair:
                    raise
        raw_toks, tok_repairs = tokenize(expr, allow_unknown_strip=allow_syntax_repair)
        fixed_toks, struct_repairs = repair_infix_tokens(raw_toks)
        return parse_infix(fixed_toks, NodeFactory()), tok_repairs + struct_repairs

    if mode == "infix":
        root, rep = _parse_infix_mode()
        return root, "infix", rep
    if mode == "postfix":
        try:
            root, rep = parse_postfix(expr, NodeFactory(), allow_repair=False)
            return root, "postfix", rep
        except ParseError:
            if not allow_syntax_repair:
                raise
            root, rep = parse_postfix(expr, NodeFactory(), allow_repair=True)
            return root, "postfix", rep
    if mode == "prefix":
        try:
            root, rep = parse_prefix(expr, NodeFactory(), allow_repair=False)
            return root, "prefix", rep
        except ParseError:
            if not allow_syntax_repair:
                raise
            root, rep = parse_prefix(expr, NodeFactory(), allow_repair=True)
            return root, "prefix", rep

    # Auto mode:
    tokens, _ = _tokenize_space_or_std(expr, allow_repair=True)
    if not tokens:
        raise ParseError("Ingresa una expresión matemática.")

    if "(" in tokens or ")" in tokens:
        root, rep = _parse_infix_mode()
        return root, "infix", rep

    if len(tokens) >= 3 and tokens[0] in BINARY_OPS:
        try:
            root, rep = parse_prefix(expr, NodeFactory(), allow_repair=False)
            return root, "prefix", rep
        except ParseError:
            pass

    if len(tokens) >= 3 and tokens[-1] in BINARY_OPS:
        try:
            root, rep = parse_postfix(expr, NodeFactory(), allow_repair=False)
            return root, "postfix", rep
        except ParseError:
            pass

    # Try strict first across all three notations
    for candidate_mode, fn in (
        ("infix", lambda: (parse_infix(tokenize(expr)[0], NodeFactory()), [])),
        ("postfix", lambda: parse_postfix(expr, NodeFactory(), allow_repair=False)),
        ("prefix", lambda: parse_prefix(expr, NodeFactory(), allow_repair=False)),
    ):
        try:
            root, rep = fn()
            return root, candidate_mode, rep
        except ParseError:
            continue

    # If strict fails and syntax repair is enabled, repair as infix (or prefix/postfix if space-separated)
    if allow_syntax_repair:
        root, rep = _parse_infix_mode(strict_first=False)
        return root, "infix", rep

    root, rep = _parse_infix_mode(strict_first=True)
    return root, "infix", rep




def detect_and_parse(expr: str, mode: str = "auto", allow_syntax_repair: bool = True) -> tuple[ExprNode, str, list[str]]:
    if mode in {"auto", "infix"}:
        expr = re.sub(r"^\s*y\s*=\s*", "", expr, count=1, flags=re.IGNORECASE)
    if mode not in {"auto", "infix", "prefix", "postfix"}:
        raise ParseError(f"Notación desconocida: {mode}")
    if len(expr) > 4000:
        raise ParseError("La expresión es demasiado larga (máximo 4000 caracteres).")
    try:
        root, detected, repairs = _detect_and_parse(expr, mode, allow_syntax_repair)
        pending = [(root, 1)]
        count = 0
        while pending:
            node, level = pending.pop()
            count += 1
            if level > 64 or count > 511:
                raise ParseError("El árbol excede 64 niveles o 511 nodos. Reduce la expresión.")
            pending.extend((child, level + 1) for child in node.children)
        return root, detected, repairs
    except RecursionError as exc:
        raise ParseError("La expresión tiene demasiados niveles. Reduce los paréntesis o las potencias.") from exc
