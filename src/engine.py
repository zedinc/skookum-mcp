import pint
from typing import Any, Literal, Union
from sympy import Rational
from .types import Quantity, Unit, Cardinality, Temperature, Dimension, MathematicalError

# Central unit registry at the Converter boundary
ureg = pint.UnitRegistry()

def combine_cardinalities(a: Cardinality, b: Cardinality, op: Literal['add', 'sub']) -> Cardinality:
    """Explicit key-by-key exponent addition or subtraction across the 7 fundamental quantities."""
    keys = ["L", "M", "T", "Theta", "I", "N", "J"]
    res: Cardinality = {k: 0 for k in keys}
    for k in keys:
        val_a = a.get(k, 0)
        val_b = b.get(k, 0)
        if op == "add":
            res[k] = val_a + val_b
        else:
            res[k] = val_a - val_b
    return res

def resolve_unit(unit_name: str) -> Unit[Any]:
    """Dynamically queries the Pint registry to resolve unit scale factor, offset, and cardinality exponents."""
    # Preprocess common custom synonyms/aliases
    unit_name = unit_name.strip()
    lower_name = unit_name.lower()
    if lower_name == "mpg":
        unit_name = "mile / gallon"
    elif lower_name == "l/100km":
        unit_name = "liter / (100 * kilometer)"
    try:
        pint_qty = ureg(unit_name)
        canonical_name = str(pint_qty.units)
        name = canonical_name if pint_qty.magnitude == 1 else unit_name
    except Exception:
        try:
            pint_qty = ureg.Quantity(1, unit_name)
            canonical_name = str(pint_qty.units)
            name = canonical_name if pint_qty.magnitude == 1 else unit_name
        except Exception as e:
            from .parser import ExpressionParsingError
            raise ExpressionParsingError(f"Unrecognized unit or symbol '{unit_name}' in expression.")

    # Dynamic offset and scale factor resolution in base units
    try:
        unit_obj = pint_qty.units
        unit_mag = Rational(str(pint_qty.magnitude))
        
        zero_qty = ureg.Quantity(0, unit_obj).to_base_units()
        offset = Rational(str(zero_qty.magnitude)).limit_denominator(10**12) * unit_mag
        
        one_qty = ureg.Quantity(1, unit_obj).to_base_units()
        scale_factor = (Rational(str(one_qty.magnitude)).limit_denominator(10**12) * unit_mag) - offset
    except Exception:
        offset = Rational(0)
        scale_factor = Rational(1)

    dim_map = {
        '[length]': 'L',
        '[mass]': 'M',
        '[time]': 'T',
        '[temperature]': 'Theta',
        '[current]': 'I',
        '[substance]': 'N',
        '[luminosity]': 'J'
    }
    
    cardinality: Cardinality = {
        "L": 0, "M": 0, "T": 0, "Theta": 0, "I": 0, "N": 0, "J": 0
    }
    
    for pint_dim, exponent in pint_qty.dimensionality.items():
        our_key = dim_map.get(pint_dim)
        if our_key:
            cardinality[our_key] = int(exponent)
            
    return Unit(name, cardinality, scale_factor, offset)

def get_relative_temp_unit_for(abs_unit: Unit[Any]) -> Unit[Any]:
    """Resolves the corresponding relative delta temperature Unit for an absolute temperature Unit."""
    name = abs_unit.name
    if name in {"degree_Celsius", "degC"}:
        return Unit("delta_degree_Celsius", Temperature.CARDINALITY, abs_unit.scale_factor, 0)
    elif name in {"degree_Fahrenheit", "degF"}:
        return Unit("delta_degree_Fahrenheit", Temperature.CARDINALITY, abs_unit.scale_factor, 0)
    elif name in {"kelvin", "K"}:
        return Unit("delta_kelvin", Temperature.CARDINALITY, abs_unit.scale_factor, 0)
    elif name in {"rankine", "R"}:
        return Unit("delta_rankine", Temperature.CARDINALITY, abs_unit.scale_factor, 0)
    return Unit(f"delta_{name}", Temperature.CARDINALITY, abs_unit.scale_factor, 0)

def convert_quantity(qty: Quantity[Any], target_unit: Union[str, Unit[Any]]) -> Quantity[Any]:
    """
    Translates a Quantity to a target Unit.
    Supports standard linear scaling, non-linear absolute and gauge offsets,
    and reciprocal inversions algebraically.
    """
    if isinstance(target_unit, str):
        try:
            target_unit = resolve_unit(target_unit)
        except Exception:
            raise TypeError(f"Dimensional Mismatch: target unit '{target_unit}' is unknown.")

    # 1. Standard Match / Conversion (Uniformly handles linear and offset dimensions!)
    if qty.unit.cardinality == target_unit.cardinality:
        new_mag = (qty.value - target_unit.offset) / target_unit.scale_factor
        return Quantity(new_mag, target_unit)

    # 2. Reciprocal Inversion Solver (e.g. MPG vs L/100km)
    sum_card = combine_cardinalities(qty.unit.cardinality, target_unit.cardinality, "add")
    is_reciprocal = all(val == 0 for val in sum_card.values())

    if is_reciprocal:
        if qty.value == 0:
            raise MathematicalError("Nonsense: Zero-value quantity has no defined reciprocal.")
        inverted_val = 1 / qty.value
        inverted_unit = Unit(
            f"1 / ({qty.unit.name})",
            target_unit.cardinality,
            1 / qty.unit.scale_factor,
            0
        )
        inverted_qty = Quantity(inverted_val / inverted_unit.scale_factor, inverted_unit)
        return convert_quantity(inverted_qty, target_unit)

    # 3. Bubble up a clean, descriptive dimensional mismatch error
    raise TypeError(
        f"Dimensional Mismatch: Cannot convert quantity with unit '{qty.unit.name}' ({qty.unit.cardinality}) "
        f"to target unit '{target_unit.name}' ({target_unit.cardinality})."
    )
