"""
Quantity literals from number-unit juxtaposition (ADR 0006).

The preprocessor marks the multiplications it inserts between a number and a unit with `@` (same
precedence as `*`, so tree shapes are unchanged). This pass uses those marks to bind `number unit` as one
literal, so `10 m / 2 s` is `(10 m) / (2 s)` and not `((10 m) / 2) * s`:

* a number followed by a unit forms a literal, absorbing following `/ unit-only` operands (`2 m/s`);
* a leading unit-free run is one number (`3 * 4 m`);
* `unit-free / number unit` (`10 / 2 s`) is genuinely ambiguous and becomes a ReadingQuestion.

Explicit `*` is never regrouped: `10 m / 2 * s` stays left to right.
"""
import ast
from typing import List, Optional, Tuple

from .readings import FRACTION_KEY, ReadingContext, ReadingQuestion

_FLAT_OPS = (ast.Mult, ast.Div, ast.MatMult)
_CONSTANT_NAMES = {"pi", "E"}
Item = Tuple[Optional[ast.operator], ast.AST]


def _unit_names(node: ast.AST) -> set:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} - _CONSTANT_NAMES


def _is_pure_number(node: ast.AST) -> bool:
    return not _unit_names(node)


def _is_pure_unit(node: ast.AST) -> bool:
    """Unit names combined with * / and integer-ish powers; no numeric factors."""
    if isinstance(node, ast.Name):
        return node.id not in _CONSTANT_NAMES
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            return _is_pure_unit(node.left) and _is_pure_number(node.right)
        if isinstance(node.op, (ast.Mult, ast.Div)):
            return _is_pure_unit(node.left) and _is_pure_unit(node.right)
    return False


def _binop(left: ast.AST, op: ast.operator, right: ast.AST) -> ast.BinOp:
    node = ast.BinOp(left=left, op=op, right=right)
    node.lineno, node.col_offset = left.lineno, left.col_offset
    node.end_lineno, node.end_col_offset = right.end_lineno, right.end_col_offset
    return node


def _fold(items: List[Item]) -> ast.AST:
    node = items[0][1]
    for op, operand in items[1:]:
        node = _binop(node, ast.Mult() if isinstance(op, ast.MatMult) else op, operand)
    return node


def _flatten(node: ast.BinOp) -> List[Item]:
    """Left-associative chain of * / @ operands. A parenthesised left child starts earlier and stays one operand."""
    items: List[Item] = []
    cur = node
    while True:
        items.append((cur.op, cur.right))
        left = cur.left
        if isinstance(left, ast.BinOp) and isinstance(left.op, _FLAT_OPS) and left.col_offset == cur.col_offset:
            cur = left
        else:
            items.append((None, left))
            break
    items.reverse()  # now [(None, first), (op, second), ...]: each op precedes its operand
    return items


class _Rewriter(ast.NodeTransformer):
    def __init__(self, ctx: ReadingContext):
        self.ctx = ctx

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        if not isinstance(node.op, _FLAT_OPS):
            return self.generic_visit(node)
        items = [(op, self.visit(operand)) for op, operand in _flatten(node)]
        out: List[Item] = []
        i = 0
        while i < len(items):
            op, operand = items[i]
            nxt = items[i + 1] if i + 1 < len(items) else None
            if nxt and isinstance(nxt[0], ast.MatMult) and _is_pure_number(operand) and _is_pure_unit(nxt[1]):
                unit_expr, j = nxt[1], i + 2
                while j < len(items) and isinstance(items[j][0], ast.Div) and _is_pure_unit(items[j][1]):
                    unit_expr = _binop(unit_expr, ast.Div(), items[j][1])
                    j += 1
                out = self._attach(out, op, operand, unit_expr)
                i = j
            else:
                out.append((op, operand))
                i += 1
        return _fold(out)

    def _attach(self, out: List[Item], op: Optional[ast.operator], number: ast.AST, unit_expr: ast.AST) -> List[Item]:
        literal = _binop(number, ast.Mult(), unit_expr)
        if not (isinstance(op, ast.Div) and out and all(_is_pure_number(o) for _, o in out)):
            return out + [(op, literal)]

        # A unit-free run divided by `number unit`: (run/number) unit, or run/(number unit)?
        run = _fold(out)
        key = (number.col_offset, number.end_col_offset)
        run_t, num_t, unit_t = ast.unparse(run), ast.unparse(number), ast.unparse(unit_expr)
        label = f"{run_t} / {num_t} {unit_t}"
        readings = {"scalar": f"({run_t}/{num_t}) {unit_t}", "divisor": f"{run_t}/({num_t} {unit_t})"}
        decided = self.ctx.decision(FRACTION_KEY, key)
        if decided is None:
            raise ReadingQuestion(
                key, FRACTION_KEY, label, FRACTION_KEY, readings,
                f"'{label}' can be read as {readings['scalar']} or as {readings['divisor']}.",
                f"add parentheses, e.g. {readings['scalar']} or {readings['divisor']}",
            )
        choice, why = decided
        self.ctx.notes.append(f"'{label}' read as {readings[choice]} ({why})")
        if choice == "scalar":
            return [(None, _binop(_binop(run, ast.Div(), number), ast.Mult(), unit_expr))]
        return out + [(ast.Div(), literal)]


def rewrite_juxtaposition(tree: ast.AST, ctx: ReadingContext) -> ast.AST:
    return ast.fix_missing_locations(_Rewriter(ctx).visit(tree))
