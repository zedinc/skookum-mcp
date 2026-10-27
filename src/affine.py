"""
Point-vs-interval inference for offset-scale temperatures (ADR 0005).

A temperature such as `5 degC` is either a point on a scale or an interval. `Quantity` stays strict and
refuses to scale an offset-scale unit; this module is the expression layer that decides what each
occurrence means *before* arithmetic happens:

1. Forced interval: the other operand has the same scale in a rate denominator (`kJ/(kg*degC) * 5 degC`).
2. Unforced point: converted to its zero-based scale (degC -> K, degF -> degR) by physical convention.
3. Competing readings (the other operand is a "per kelvin" rate): raised as a ReadingQuestion for the caller.
"""
import ast
from typing import Any, Dict, Optional, Tuple

from .engine import convert_quantity, resolve_unit
from .readings import FRACTION_CHOICES, FRACTION_KEY, ReadingContext, ReadingQuestion
from .types import Quantity, Unit

# canonical point-scale name -> (interval unit, zero-based scale used for multiplicative operations, short symbol)
OFFSET_SCALES: Dict[str, Tuple[str, str, str]] = {
    "degree_Celsius": ("delta_degree_Celsius", "kelvin", "degC"),
    "degree_Fahrenheit": ("delta_degree_Fahrenheit", "degree_Rankine", "degF"),
}
KIND_NAMES = ("point", "interval")
TEMPERATURE_TOPIC = "temperature_kind"


def canonical_scale_name(symbol: str) -> Optional[str]:
    """Canonical offset-scale name for a unit symbol (degC, degree_Celsius, ...), else None."""
    try:
        name = resolve_unit(symbol).name
    except Exception:
        return None
    return name if name in OFFSET_SCALES else None


def normalize_reading(key: str, value: str) -> Tuple[str, str]:
    """
    Validates a recorded reading decision and returns its canonical (key, choice):
    ('fraction_unit', 'scalar'|'divisor') or (<canonical scale name>, 'point'|'interval').
    """
    if key == FRACTION_KEY:
        if value not in FRACTION_CHOICES:
            raise ValueError(f"'{value}' is not a choice for '{FRACTION_KEY}'. Options: {', '.join(FRACTION_CHOICES)}.")
        return key, value
    scale = canonical_scale_name(key)
    if scale is None:
        raise ValueError(f"'{key}' is not a reading question. Use '{FRACTION_KEY}', or degC / degF with "
                         f"'point' or 'interval'.")
    if value not in KIND_NAMES:
        raise ValueError(f"'{value}' is not a choice for '{key}'. Options: {', '.join(KIND_NAMES)}.")
    return scale, value


# --- AST helpers ---

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
                   ctx: ReadingContext) -> Quantity:
    name = point.unit.name
    interval_name, absolute_name, symbol = OFFSET_SCALES[name]
    literal = f"{_fmt(point.expressed_value)} {name}"
    key = (point_node.col_offset, point_node.end_col_offset)

    as_interval = Quantity(point.expressed_value, resolve_unit(interval_name))
    as_absolute = convert_quantity(point, resolve_unit(absolute_name))

    if name in _rate_scales(other_node):
        kind, reason = "interval", f"the other operand is a rate per {symbol}"
    else:
        decided = ctx.decision(name, key)
        if decided is None:
            if _per_kelvin(other):
                raise ReadingQuestion(
                    key, TEMPERATURE_TOPIC, literal, symbol,
                    {
                        "point": f"temperature reading, converted to {_fmt(as_absolute.expressed_value)} {absolute_name}",
                        "interval": f"temperature difference of {_fmt(point.expressed_value)} {interval_name}",
                    },
                    f"'{literal}' could be a temperature reading (converted to its zero-based scale before "
                    f"multiplying) or a temperature difference.",
                    "write the unit you mean (K, delta_degC, delta_degF)",
                )
            kind, reason = "point", None
        else:
            kind, reason = decided

    if kind == "interval":
        ctx.notes.append(f"{literal} treated as {interval_name} ({reason})")
        return as_interval
    ctx.notes.append(f"{literal} converted to {_fmt(as_absolute.expressed_value)} {absolute_name} "
                     f"({reason or 'offset-scale temperature in a multiplicative operation'})")
    return as_absolute


def prepare_multiplicative(left: Any, right: Any, left_node: ast.AST, right_node: ast.AST,
                           ctx: ReadingContext) -> Tuple[Any, Any]:
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


def prepare_power_base(base: Any, base_node: ast.AST, ctx: ReadingContext) -> Any:
    """A point raised to a power is converted to its zero-based scale, like any other multiplicative use."""
    if _is_point(base):
        _, absolute_name, _ = OFFSET_SCALES[base.unit.name]
        converted = convert_quantity(base, resolve_unit(absolute_name))
        ctx.notes.append(f"{_fmt(base.expressed_value)} {base.unit.name} converted to "
                         f"{_fmt(converted.expressed_value)} {absolute_name} (offset-scale temperature raised to a power)")
        return converted
    return base
