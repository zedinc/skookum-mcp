"""
Contextual resolution of ambiguous unit symbols (ADR 0004).

A symbol such as `pt` (pint or typographic point) or `C` (coulomb or Celsius) is resolved in layers:

1. Hard bindings: the per-call `assume` argument, then session defaults. These are never overridden.
2. Context: every candidate assignment is evaluated; only those that are dimensionally valid survive.
3. Soft preferences (only used to break ties among survivors): per-symbol config defaults, then the config profile.
4. Otherwise the caller receives a structured `AmbiguousUnitError` describing the surviving interpretations.
"""
import itertools
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from .types import MathematicalError

PROFILES = ("us", "imperial", "metric")
_ALL_PROFILES = frozenset(PROFILES)

MAX_AMBIGUOUS_TOKENS = 4
MAX_INTERPRETATIONS = 64
MAX_EXPRESSION_LENGTH = 500


class AssumptionError(ValueError):
    """Raised when an `assume` or session binding names an unknown symbol or candidate."""


@dataclass(frozen=True)
class Candidate:
    id: str
    unit: str  # A name the unit registry can resolve
    description: str
    tags: frozenset = frozenset()


def _c(id: str, unit: str, description: str, *tags: str) -> Candidate:
    return Candidate(id, unit, description, frozenset(tags))


_US_PINT = _c("us_pint", "pint", "US liquid pint, 473.176 mL", "us")
_IMPERIAL_PINT = _c("imperial_pint", "imperial_pint", "Imperial pint, 568.261 mL", "imperial")
_US_FLOZ = _c("us_fluid_ounce", "fluid_ounce", "US fluid ounce, 29.5735 mL", "us")
_IMPERIAL_FLOZ = _c("imperial_fluid_ounce", "imperial_fluid_ounce", "Imperial fluid ounce, 28.4131 mL", "imperial")

AMBIGUOUS: Dict[str, List[Candidate]] = {
    "ton": [
        _c("short_ton", "short_ton", "US short ton, 907.185 kg", "us"),
        _c("long_ton", "long_ton", "Imperial long ton, 1016.05 kg", "imperial"),
        _c("metric_ton", "metric_ton", "Metric tonne, 1000 kg", "metric"),
    ],
    "gal": [
        _c("us_gallon", "gallon", "US liquid gallon, 3.78541 L", "us"),
        _c("imperial_gallon", "imperial_gallon", "Imperial gallon, 4.54609 L", "imperial"),
    ],
    "qt": [
        _c("us_quart", "quart", "US liquid quart, 946.353 mL", "us"),
        _c("imperial_quart", "imperial_quart", "Imperial quart, 1136.52 mL", "imperial"),
    ],
    "pint": [_US_PINT, _IMPERIAL_PINT],
    "pt": [
        _US_PINT,
        _IMPERIAL_PINT,
        _c("typographic_point", "point", "Typographic point, 1/72 inch"),
    ],
    "floz": [_US_FLOZ, _IMPERIAL_FLOZ],
    "oz": [
        _c("ounce", "ounce", "Avoirdupois ounce (mass), 28.3495 g", *PROFILES),
        _US_FLOZ,
        _IMPERIAL_FLOZ,
    ],
    "cal": [
        _c("thermochemical_calorie", "thermochemical_calorie", "Thermochemical calorie, 4.184 J"),
        _c("international_calorie", "international_calorie", "International Table calorie, 4.1868 J"),
    ],
    "hp": [
        _c("mechanical_horsepower", "horsepower", "Mechanical horsepower, 745.7 W"),
        _c("metric_horsepower", "metric_horsepower", "Metric horsepower (PS), 735.499 W"),
    ],
    "C": [
        _c("coulomb", "coulomb", "Coulomb (electric charge)"),
        _c("celsius", "degC", "Degree Celsius (absolute temperature scale)"),
    ],
    "F": [
        _c("farad", "farad", "Farad (capacitance)"),
        _c("fahrenheit", "degF", "Degree Fahrenheit (absolute temperature scale)"),
    ],
}
AMBIGUOUS["gallon"] = AMBIGUOUS["gal"]
AMBIGUOUS["quart"] = AMBIGUOUS["qt"]
AMBIGUOUS["fluid_ounce"] = AMBIGUOUS["floz"]

# Unambiguous names: every candidate id works as an explicit qualification, plus a few shorthands.
ALIASES: Dict[str, str] = {c.id: c.unit for cands in AMBIGUOUS.values() for c in cands}
ALIASES.update({"R": "degR", "Cal": "kilocalorie"})

# Not preceded by a word character or '.', so `1e5` is not mistaken for the token `e5`.
_TOKEN = re.compile(r"(?<![\w.])[A-Za-z_][A-Za-z0-9_]*")


def find_candidate(symbol: str, candidate_id: str) -> Candidate:
    """Looks up a candidate for an ambiguous symbol, raising AssumptionError if either is unknown."""
    if symbol not in AMBIGUOUS:
        raise AssumptionError(
            f"'{symbol}' is not an ambiguous unit symbol. Ambiguous symbols: {', '.join(sorted(AMBIGUOUS))}."
        )
    for cand in AMBIGUOUS[symbol]:
        if cand.id == candidate_id:
            return cand
    options = ", ".join(c.id for c in AMBIGUOUS[symbol])
    raise AssumptionError(f"'{candidate_id}' is not a candidate for '{symbol}'. Options: {options}.")


def describe_candidate(cand: Candidate) -> Dict[str, Any]:
    """Machine-readable description of a candidate, including its physical dimension."""
    from .engine import resolve_unit
    from .types import Quantity
    dimension = Quantity(1, resolve_unit(cand.unit)).dimensionality
    return {"id": cand.id, "unit": cand.unit, "dimension": dimension, "description": cand.description}


def registry_listing() -> Dict[str, Any]:
    """The whole registry as JSON-ready data (used by the `units://ambiguous` resource)."""
    return {
        symbol: [dict(describe_candidate(c), tags=sorted(c.tags)) for c in cands]
        for symbol, cands in sorted(AMBIGUOUS.items())
    }


class AmbiguousUnitError(Exception):
    """More than one interpretation is valid in context and no default settles it."""
    def __init__(self, message: str, payload: Dict[str, Any]):
        super().__init__(message)
        self.message = message
        self.payload = payload


@dataclass
class Resolution:
    value: str
    notes: List[str] = field(default_factory=list)


Assignment = Tuple[Tuple[str, Candidate], ...]


def _tokens_in(text: str) -> List[str]:
    return [m.group(0) for m in _TOKEN.finditer(text)]


def _label(assignment: Assignment) -> Dict[str, str]:
    return {sym: cand.id for sym, cand in assignment}


def resolve_ambiguities(
    expression: str,
    target_unit: str,
    evaluate: Callable[[str, str], str],
    assume: Optional[Mapping[str, str]] = None,
    session: Optional[Mapping[str, str]] = None,
    defaults: Optional[Mapping[str, str]] = None,
    profile: Optional[str] = None,
) -> Resolution:
    """
    Evaluates `expression` -> `target_unit` via `evaluate`, resolving ambiguous unit symbols.
    `evaluate(expression, target)` must return the formatted result or raise on an invalid interpretation.
    """
    from .parser import preprocess_expression, normalize_unicode_symbols

    if len(expression) > MAX_EXPRESSION_LENGTH:
        # Let the evaluator raise its own length error before any scanning work
        return Resolution(evaluate(expression, target_unit))

    pre_expr = preprocess_expression(expression)
    target = normalize_unicode_symbols(target_unit).strip()
    expr_tokens, target_tokens = _tokens_in(pre_expr), _tokens_in(target)

    ambiguous = list(dict.fromkeys(t for t in expr_tokens + target_tokens if t in AMBIGUOUS))
    aliases = {t for t in expr_tokens + target_tokens if t in ALIASES and t not in AMBIGUOUS}
    if not ambiguous and not aliases:
        return Resolution(evaluate(expression, target_unit))

    if len(ambiguous) > MAX_AMBIGUOUS_TOKENS:
        from .parser import ExpressionParsingError
        raise ExpressionParsingError(
            f"Too many distinct ambiguous units ({', '.join(ambiguous)}); "
            f"qualify some explicitly (limit {MAX_AMBIGUOUS_TOKENS})."
        )

    # Hard bindings: `assume` beats session defaults. Both are validated.
    hard: Dict[str, Candidate] = {}
    for source in (session or {}, assume or {}):
        for sym, cid in source.items():
            hard[sym] = find_candidate(sym, cid)
    sources = {sym: ("assume" if sym in (assume or {}) else "session") for sym in hard}

    options = [[hard[s]] if s in hard else AMBIGUOUS[s] for s in ambiguous]
    total = 1
    for opts in options:
        total *= len(opts)
    if total > MAX_INTERPRETATIONS:  # pragma: no cover - bounded by MAX_AMBIGUOUS_TOKENS and registry size
        from .parser import ExpressionParsingError
        raise ExpressionParsingError("Too many ambiguous-unit interpretations to evaluate.")

    alias_map = {a: ALIASES[a] for a in aliases}
    assignments: List[Assignment] = [tuple(zip(ambiguous, combo)) for combo in itertools.product(*options)]

    def run(assignment: Assignment) -> str:
        mapping = dict(alias_map)
        mapping.update({sym: cand.unit for sym, cand in assignment})
        sub = lambda text: _TOKEN.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)
        return evaluate(sub(pre_expr), sub(target))

    if len(assignments) == 1:
        # Nothing to infer: evaluate directly so ordinary errors propagate unchanged
        result = run(assignments[0])
        notes = [f"{s} = {hard[s].id} ({sources[s]} binding)" for s in ambiguous if sources.get(s) == "session"]
        return Resolution(result, notes)

    survivors: List[Tuple[Assignment, str]] = []
    rejected: List[Tuple[Assignment, str]] = []
    for assignment in assignments:
        try:
            survivors.append((assignment, run(assignment)))
        except (TypeError, MathematicalError, ZeroDivisionError) as e:
            rejected.append((assignment, str(e)))

    if not survivors:
        detail = "; ".join(f"{_label(a)}: {msg}" for a, msg in rejected[:6])
        raise TypeError(
            f"No interpretation of ambiguous unit(s) {', '.join(repr(s) for s in ambiguous)} "
            f"is dimensionally valid in this expression. {detail}"
        )

    def distinct(rows: List[Tuple[Assignment, str]], sym: str) -> int:
        return len({dict(a)[sym].id for a, _ in rows})

    free = [s for s in ambiguous if s not in hard]
    by_context = {s: distinct(survivors, s) == 1 for s in free}

    # Soft preferences only break ties among the survivors context allowed
    for sym in free:
        if distinct(survivors, sym) > 1 and (defaults or {}).get(sym):
            kept = [row for row in survivors if dict(row[0])[sym].id == defaults[sym]]
            if kept:
                survivors = kept
    for sym in free:
        if distinct(survivors, sym) > 1 and profile:
            kept = [row for row in survivors if profile in dict(row[0])[sym].tags]
            if kept:
                survivors = kept

    if len(survivors) > 1:
        varying = [s for s in free if distinct(survivors, s) > 1]
        payload = {
            "tokens": {
                s: [describe_candidate(c) for c in
                    {dict(a)[s].id: dict(a)[s] for a, _ in survivors}.values()]
                for s in varying
            },
            "interpretations": [{"assume": _label(a), "result": r} for a, r in survivors],
            "rejected": [{"assume": _label(a), "reason": msg} for a, msg in rejected[:6]],
        }
        names = ", ".join(repr(s) for s in varying)
        message = (
            f"{names} has more than one valid interpretation in this expression. Re-call with "
            f"assume={{{', '.join(repr(s) + ': <id>' for s in varying)}}} (or use an explicit unit name), "
            f"call set_unit_default to settle it for this session, or set a default in the config file."
        )
        raise AmbiguousUnitError(message, payload)

    assignment, result = survivors[0]
    chosen = dict(assignment)
    notes = []
    for sym in ambiguous:
        if sources.get(sym) == "assume":
            continue
        if sources.get(sym) == "session":
            why = "session binding"
        elif by_context.get(sym):
            why = "only interpretation consistent with the rest of the expression"
        elif (defaults or {}).get(sym) == chosen[sym].id:
            why = "configured default"
        else:
            why = f"'{profile}' profile"
        notes.append(f"{sym} = {chosen[sym].id} ({why})")
    return Resolution(result, notes)
