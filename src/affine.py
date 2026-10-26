"""
Point-vs-interval inference for offset-scale temperatures (ADR 0005).

A temperature such as `5 degC` is either a point on a scale or an interval. `Quantity` stays strict and
refuses to scale an offset-scale unit; this module is the expression layer that decides what each
occurrence means *before* arithmetic happens:

1. Forced interval: the other operand has the same scale in a rate denominator (`kJ/(kg*degC) * 5 degC`).
2. Unforced point: converted to its zero-based scale (degC -> K, degF -> degR) by physical convention.
3. Competing readings (the other operand is a "per kelvin" rate): both are evaluated and reported.
"""
import ast
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .engine import convert_quantity, resolve_unit
from .types import MathematicalError, Quantity, Unit

# canonical point-scale name -> (interval unit, zero-based scale used for multiplicative operations, short symbol)
OFFSET_SCALES: Dict[str, Tuple[str, str, str]] = {
    "degree_Celsius": ("delta_degree_Celsius", "kelvin", "degC"),
    "degree_Fahrenheit": ("delta_degree_Fahrenheit", "degree_Rankine", "degF"),
}
KIND_NAMES = ("point", "interval")
MAX_AMBIGUOUS_OCCURRENCES = 3


class KindQuestion(Exception):
    """Internal: raised at an occurrence whose reading is not settled by the expression."""
    def __init__(self, key: Any, literal: str, symbol: str, readings: Dict[str, str]):
        super().__init__(literal)
        self.key, self.literal, self.symbol, self.readings = key, literal, symbol, readings


class AmbiguousKindError(Exception):
    """More than one reading of an offset-scale temperature is valid, and nothing settles it."""
    def __init__(self, message: str, payload: Dict[str, Any]):
        super().__init__(message)
        self.message = message
        self.payload = payload


@dataclass
class KindContext:
    assume: Dict[str, str] = field(default_factory=dict)        # canonical scale name -> point|interval
    overrides: Dict[Any, str] = field(default_factory=dict)     # occurrence key -> point|interval (branching)
    notes: List[str] = field(default_factory=list)


def canonical_scale_name(symbol: str) -> Optional[str]:
    """Canonical offset-scale name for a unit symbol (degC, degree_Celsius, ...), else None."""
    try:
        name = resolve_unit(symbol).name
    except Exception:
        return None
    return name if name in OFFSET_SCALES else None


# --- AST helpers ---

def _is_number(node: ast.AST) -> bool:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        node = node.operand
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float))


def _is_offset_name(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and canonical_scale_name(node.id) is not None


class _RegroupLiterals(ast.NodeTransformer):
    """
    Binds `<number> <offset unit>` as one literal: `A * 5 * degC` -> `A * (5 * degC)` and
    `A / 5 * degC` -> `A / (5 * degC)`. Implicit multiplication would otherwise fold the number into A.
    """
    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        inner = node.left
        if (isinstance(node.op, ast.Mult) and _is_offset_name(node.right)
                and isinstance(inner, ast.BinOp) and isinstance(inner.op, (ast.Mult, ast.Div))
                and _is_number(inner.right)):
            literal = ast.copy_location(ast.BinOp(left=inner.right, op=ast.Mult(), right=node.right), inner.right)
            literal.end_lineno, literal.end_col_offset = node.end_lineno, node.end_col_offset
            return ast.copy_location(ast.BinOp(left=inner.left, op=inner.op, right=literal), node)
        return node


def regroup_temperature_literals(tree: ast.AST) -> ast.AST:
    return ast.fix_missing_locations(_RegroupLiterals().visit(tree))


def _scale_exponents(node: ast.AST, sign: int = 1) -> Dict[str, int]:
    """Net exponent of each offset-scale unit name within the multiplicative structure of `node`."""
    if isinstance(node, ast.Name):
        name = canonical_scale_name(node.id)
        return {name: sign} if name else {}
    if isinstance(node, ast.UnaryOp):
        return _scale_exponents(node.operand, sign)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Div)):
        out = dict(_scale_exponents(node.left, sign))
        right_sign = sign if isinstance(node.op, ast.Mult) else -sign
        for name, exp in _scale_exponents(node.right, right_sign).items():
            out[name] = out.get(name, 0) + exp
        return out
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow) and isinstance(node.right, ast.Constant) \
            and isinstance(node.right.value, int):
        return _scale_exponents(node.left, sign * node.right.value)
    return {}


def _rate_scales(node: ast.AST) -> set:
    return {name for name, exp in _scale_exponents(node).items() if exp < 0}


# --- Operand preparation ---

def _is_bare_offset_unit(x: Any) -> bool:
    return isinstance(x, Unit) and x.offset != 0 and x.name in OFFSET_SCALES


def _is_point(x: Any) -> bool:
    return isinstance(x, Quantity) and x.unit.offset != 0 and x.unit.name in OFFSET_SCALES


def _per_kelvin(other: Any) -> bool:
    unit = other.unit if isinstance(other, Quantity) else other
    return isinstance(unit, Unit) and unit.cardinality.get("Theta", 0) < 0


def _fmt(value: Any) -> str:
    return f"{float(value):.6g}"


def _resolve_point(point: Quantity, other: Any, point_node: ast.AST, other_node: ast.AST,
                   ctx: KindContext) -> Quantity:
    name = point.unit.name
    interval_name, absolute_name, symbol = OFFSET_SCALES[name]
    literal = f"{_fmt(point.expressed_value)} {name}"
    key = (point_node.col_offset, point_node.end_col_offset)

    as_interval = Quantity(point.expressed_value, resolve_unit(interval_name))
    as_absolute = convert_quantity(point, resolve_unit(absolute_name))

    if name in _rate_scales(other_node):
        kind, reason = "interval", f"the other operand is a rate per {symbol}"
    else:
        kind = ctx.overrides.get(key)
        reason = "one possible reading" if kind else None
        if kind is None:
            kind = ctx.assume.get(name)
            reason = "assumed by caller" if kind else None
        if kind is None:
            if _per_kelvin(other):
                raise KindQuestion(key, literal, symbol, {
                    "point": f"temperature reading, converted to {_fmt(as_absolute.expressed_value)} {absolute_name}",
                    "interval": f"temperature difference of {_fmt(point.expressed_value)} {interval_name}",
                })
            kind = "point"

    if kind == "interval":
        ctx.notes.append(f"{literal} treated as {interval_name} ({reason})")
        return as_interval
    ctx.notes.append(f"{literal} converted to {_fmt(as_absolute.expressed_value)} {absolute_name} "
                     f"({reason or 'offset-scale temperature in a multiplicative operation'})")
    return as_absolute


def prepare_multiplicative(left: Any, right: Any, left_node: ast.AST, right_node: ast.AST,
                           ctx: KindContext) -> Tuple[Any, Any]:
    """Applies the ADR 0005 rules to the operands of `*` and `/` before the Quantity arithmetic runs."""
    out = []
    for x, other, x_node, other_node in ((left, right, left_node, right_node), (right, left, right_node, left_node)):
        if _is_bare_offset_unit(x) and isinstance(other, Quantity):
            # `4.18 kJ/degC`: an offset unit inside a compound unit denotes a scale step (interval)
            out.append(resolve_unit(OFFSET_SCALES[x.name][0]))
        elif _is_point(x):
            out.append(_resolve_point(x, other, x_node, other_node, ctx))
        else:
            out.append(x)
    return out[0], out[1]


def prepare_power_base(base: Any, base_node: ast.AST, ctx: KindContext) -> Any:
    """A point raised to a power is converted to its zero-based scale, like any other multiplicative use."""
    if _is_point(base):
        _, absolute_name, _ = OFFSET_SCALES[base.unit.name]
        converted = convert_quantity(base, resolve_unit(absolute_name))
        ctx.notes.append(f"{_fmt(base.expressed_value)} {base.unit.name} converted to "
                         f"{_fmt(converted.expressed_value)} {absolute_name} (offset-scale temperature raised to a power)")
        return converted
    return base


# --- Branching over unsettled readings ---

def resolve_kinds(run: Callable[[KindContext], str], assume: Optional[Dict[str, str]] = None) -> Tuple[str, List[str]]:
    """
    Calls `run(ctx)` (parse, evaluate, convert, format). If an occurrence is unsettled, re-runs under each
    reading and either settles on the single valid one or raises AmbiguousKindError.
    """
    assume = dict(assume or {})
    leaves: List[Tuple[Dict[Any, str], str, List[str]]] = []
    rejected: List[Tuple[Dict[Any, str], str]] = []
    literals: Dict[Any, str] = {}
    symbols: set = set()
    readings: Dict[str, Dict[str, str]] = {}

    def branch(overrides: Dict[Any, str]) -> None:
        ctx = KindContext(assume=assume, overrides=dict(overrides))
        try:
            text = run(ctx)
        except KindQuestion as q:
            if len(overrides) >= MAX_AMBIGUOUS_OCCURRENCES:
                raise TypeError("Too many ambiguous temperature readings in one expression; "
                                "write K or delta_degC explicitly.")
            literals[q.key] = q.literal
            symbols.add(q.symbol)
            readings[q.literal] = q.readings
            for kind in KIND_NAMES:
                branch({**overrides, q.key: kind})
            return
        except (TypeError, MathematicalError, ZeroDivisionError) as err:
            if not overrides:
                raise
            rejected.append((overrides, str(err)))
            return
        leaves.append((overrides, text, ctx.notes))

    branch({})

    def label(overrides: Dict[Any, str]) -> Dict[str, str]:
        return {literals[k]: kind for k, kind in overrides.items()}

    if not leaves:
        detail = "; ".join(f"{label(o)}: {m}" for o, m in rejected[:4])
        raise TypeError(f"No reading of the ambiguous temperature(s) is valid in this expression. {detail}")
    if len(leaves) == 1:
        overrides, text, notes = leaves[0]
        extra = [f"{lit} read as a {kind} (the other reading is invalid here)" for lit, kind in label(overrides).items()]
        return text, notes + extra

    names = ", ".join(repr(lit) for lit in readings)
    hint = ", ".join(f"'{sym}': 'point' | 'interval'" for sym in sorted(symbols))
    raise AmbiguousKindError(
        f"{names} could be a temperature reading (converted to its zero-based scale before multiplying) or a "
        f"temperature difference. Re-call with assume={{{hint}}}, or write the unit you mean "
        f"(K, delta_degC, delta_degF).",
        {
            "occurrences": readings,
            "interpretations": [{"treat": label(o), "result": t, "assumptions": n} for o, t, n in leaves],
            "rejected": [{"treat": label(o), "reason": m} for o, m in rejected[:4]],
        },
    )
