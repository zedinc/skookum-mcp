import pytest
from hypothesis import given, strategies as st, settings
from sympy import Rational
from src.types import Quantity
from src.engine import ureg

# ==========================================
# 1. RATIONAL PRECISION & ROUND-TRIPPING
# ==========================================

@pytest.mark.conversion
def test_reciprocal_conversion_preserves_exact_rational_value_without_float_drift(make_quantity):
    """Verify that exact rational arithmetic prevents float precision drift in reciprocal round-trips."""
    # Arrange
    # 1 meter converted to inches and back to meters
    # Standard float conversion drift: 1 * 39.3700787 * 0.0254 = 0.99999999898
    qty = make_quantity(1, "meter")

    # Act
    inches_qty = qty.to("inch")
    back_to_meters = inches_qty.to("meter")

    # Assert
    assert back_to_meters.value == Rational(1)  # Exact integer 1
    assert qty == back_to_meters


# ==========================================
# 2. THERMODYNAMIC TEMPERATURE GUARD TESTS
# ==========================================

@pytest.mark.temperature
def test_subtracting_absolute_temperatures_correctly_returns_delta_scale(make_quantity):
    """Verify that subtracting two absolute temperatures yields a temperature difference delta scale."""
    # Arrange
    t1 = make_quantity(30, "degC")
    t2 = make_quantity(10, "degC")

    # Act
    difference = t1 - t2

    # Assert
    assert difference.unit_name == "delta_degree_Celsius"
    assert difference.value == Rational(20)


@pytest.mark.temperature
def test_adding_delta_temperature_to_absolute_shifts_absolute_coordinate(make_quantity):
    """Verify that adding a delta temperature offset to an absolute temperature shifts the coordinate."""
    # Arrange
    temp = make_quantity(30, "degC")
    delta = make_quantity(10, "delta_degC")

    # Act
    res_add1 = temp + delta
    res_add2 = delta + temp

    # Assert
    assert res_add1.unit_name == "degree_Celsius"
    assert res_add1.expressed_value == Rational(40)
    assert res_add2.unit_name == "degree_Celsius"
    assert res_add2.expressed_value == Rational(40)


@pytest.mark.temperature
def test_adding_absolute_temperatures_raises_type_error_for_nonsense_addition(make_quantity):
    """Verify that adding two absolute temperatures raises a TypeError to block nonsense operations."""
    # Arrange
    t1 = make_quantity(30, "degC")
    t2 = make_quantity(10, "degC")

    # Act & Assert
    with pytest.raises(TypeError, match="Nonsense: Cannot add two absolute temperatures"):
        _ = t1 + t2


@pytest.mark.temperature
def test_multiplying_absolute_temperatures_raises_type_error_for_nonsense_scaling(make_quantity):
    """Verify that multiplying or scaling absolute temperatures raises a TypeError."""
    # Arrange
    t1 = make_quantity(30, "degC")

    # Act & Assert
    with pytest.raises(TypeError, match="Nonsense: Cannot multiply absolute temperatures"):
        _ = t1 * 2


@pytest.mark.temperature
def test_quantity_temperature_subtraction_absolute_minus_delta(make_quantity):
    """Verify subtracting a relative delta temperature from an absolute temperature coordinate."""
    abs_temp = make_quantity(30, "degC")
    delta_temp = make_quantity(10, "delta_degC")
    res = abs_temp - delta_temp
    assert res.unit_name == "degree_Celsius"
    assert res.expressed_value == Rational(20)


@pytest.mark.temperature
def test_quantity_temperature_subtraction_delta_minus_absolute_raises_type_error(make_quantity):
    """Verify subtracting an absolute temperature from a temperature difference raises a TypeError."""
    abs_temp = make_quantity(30, "degC")
    delta_temp = make_quantity(10, "delta_degC")
    with pytest.raises(TypeError, match="Cannot subtract an absolute temperature from a temperature difference"):
        _ = delta_temp - abs_temp


@pytest.mark.temperature
def test_absolute_temperature_multiplication_and_division_guards(make_quantity):
    """Verify absolute temperature multiplication and division guards."""
    abs_temp = make_quantity(30, "degC")
    
    with pytest.raises(TypeError, match="Cannot multiply absolute temperatures"):
        _ = 2 * abs_temp
        
    with pytest.raises(TypeError, match="Cannot divide absolute temperatures"):
        _ = abs_temp / 2
        
    with pytest.raises(TypeError, match="Cannot divide absolute temperatures"):
        _ = 2 / abs_temp


# ==========================================
# 3. TYPES COVERAGE EDGE CASES
# ==========================================

@pytest.mark.conversion
def test_quantity_init_with_pint_quantity(make_quantity):
    """Verify Quantity initialization with a Pint Quantity directly."""
    pint_q = ureg.Quantity(5, "meter")
    qty = Quantity(2, pint_q)
    assert qty.unit_name == "meter"
    assert qty.value == Rational(10)


@pytest.mark.conversion
def test_quantity_init_with_invalid_string_unit_fallback():
    """Verify Quantity fallback behavior for registry lookup failures."""
    from unittest.mock import MagicMock
    import src.engine
    cls = type(src.engine.ureg)
    original_call = cls.__call__
    try:
        cls.__call__ = MagicMock(side_effect=ValueError("Mocked error"))
        qty = Quantity(5, "meter")
        assert qty.unit_name == "meter"
        assert qty.value == Rational(5)
    finally:
        cls.__call__ = original_call


@pytest.mark.conversion
def test_quantity_init_with_unsupported_value_type_fallback():
    """Verify fallback to direct rational initialization when sympify fails."""
    class DummyStr:
        def __str__(self):
            return "42/5"
    qty = Quantity(DummyStr(), "meter")
    assert qty.value == Rational(42, 5)


@pytest.mark.conversion
def test_expressed_value_fallback_on_unrecognized_unit():
    """Verify expressed_value fallback for unrecognized custom units."""
    from unittest.mock import MagicMock
    import src.engine
    qty = Quantity(10, "meter")
    cls = type(src.engine.ureg)
    original_call = cls.__call__
    try:
        cls.__call__ = MagicMock(side_effect=ValueError("Mocked error"))
        val = qty.expressed_value
        assert val == Rational(10)
    finally:
        cls.__call__ = original_call


@pytest.mark.conversion
def test_quantity_equality_mismatch_exception_handling(make_quantity):
    """Verify quantity comparison returns False instead of raising exceptions for incompatible dimensions."""
    qty1 = make_quantity(10, "meter")
    qty2 = make_quantity(5, "second")
    assert not (qty1 == qty2)


@pytest.mark.conversion
def test_quantity_subtraction_with_raw_scalar(make_quantity):
    """Verify subtracting a raw dimensionless scalar from a quantity."""
    qty = make_quantity(5, "dimensionless")
    res = qty - 2
    assert res.value == Rational(3)


@pytest.mark.conversion
def test_quantity_standard_subtraction_and_mismatch(make_quantity):
    """Verify standard subtraction arithmetic and dimensional mismatches."""
    qty1 = make_quantity(10, "meter")
    qty2 = make_quantity(3, "meter")
    assert (qty1 - qty2).value == Rational(7)
    
    qty3 = make_quantity(5, "kilogram")
    with pytest.raises(TypeError, match="Dimensional Mismatch: Cannot subtract incompatible dimensions"):
        _ = qty1 - qty3


@pytest.mark.conversion
def test_quantity_division_by_raw_scalar(make_quantity):
    """Verify dividing a standard physical quantity by a raw scalar."""
    qty = make_quantity(10, "meter")
    res = qty / 2
    assert res.value == Rational(5)
    assert res.unit_name == "meter"


@pytest.mark.pressure
@pytest.mark.force
def test_adding_incompatible_derived_quantities_raises_type_error(make_quantity):
    """Verify that adding incompatible derived quantities raises a dimensional mismatch TypeError."""
    # Arrange
    force = make_quantity(10, "N")
    pressure = make_quantity(5, "Pa")
    # Act & Assert
    with pytest.raises(TypeError, match="Dimensional Mismatch"):
        _ = force + pressure


# ==========================================
# 4. PROPERTY-BASED TESTS (HYPOTHESIS)
# ==========================================

@pytest.mark.property
@settings(max_examples=100)
@given(val=st.floats(min_value=1e-3, max_value=1e6, allow_nan=False, allow_infinity=False))
def test_round_tripping_linear_units_preserves_mathematical_identity_invariant(val):
    """Property-based test verifying that converting linear units back and forth preserves identity."""
    # Arrange
    # Using Hypothesis to fuzz inputs for round-trip length conversion
    qty = Quantity(val, "meter")

    # Act
    feet_qty = qty.to("foot")
    back_to_meters = feet_qty.to("meter")

    # Assert
    # Mathematically prove that the round-tripped rational value preserves strict identity
    assert qty == back_to_meters


@pytest.mark.conversion
def test_quantity_init_with_pint_unit():
    """Verify Quantity initialization when a Pint Unit is passed directly (line 156)."""
    pint_unit = ureg.meter
    qty = Quantity(5, pint_unit)
    assert qty.unit_name == "meter"
    assert qty.value == Rational(5)


@pytest.mark.conversion
def test_quantity_dimensionality_with_exponents(make_quantity):
    """Verify dimensionality string rendering for derived units with non-one exponents (line 204)."""
    area_qty = make_quantity(10, "meter**2")
    assert "[length] ** 2" in area_qty.dimensionality


@pytest.mark.conversion
def test_quantity_to_with_string_target(make_quantity):
    """Verify that quantity.to() works when passed a string unit name (lines 212-214)."""
    qty = make_quantity(1, "meter")
    res = qty.to("inch")
    assert res.unit_name == "inch"
    assert res.value == Rational(1)


@pytest.mark.conversion
def test_quantity_to_with_unit_object_target(make_quantity):
    """Verify that quantity.to() works when passed a Unit object target (lines 212-214)."""
    qty = make_quantity(1, "meter")
    target_unit = qty.to("inch").unit
    res = qty.to(target_unit)
    assert res.unit_name == "inch"
    assert res.value == Rational(1)


@pytest.mark.conversion
def test_number_divided_by_quantity(make_quantity):
    """Verify dividing a raw number by a physical quantity (lines 320-330)."""
    qty = make_quantity(5, "second")
    res = 10 / qty
    assert res.value == Rational(2)
    assert res.unit_name == "1 / second"
    assert res.unit.cardinality["T"] == -1


@pytest.mark.temperature
def test_number_divided_by_absolute_temperature_raises_type_error(make_quantity):
    """Verify dividing a number by an absolute temperature raises a TypeError (lines 318-320)."""
    abs_temp = make_quantity(30, "degC")
    with pytest.raises(TypeError, match="Cannot divide absolute temperatures"):
        _ = 10 / abs_temp


@pytest.mark.conversion
def test_quantity_division_by_quantity(make_quantity):
    """Verify dividing a quantity by another quantity computes the correct resulting cardinality (op == 'sub')."""
    q1 = make_quantity(10, "meter")
    q2 = make_quantity(2, "second")
    res = q1 / q2
    assert res.value == Rational(5)
    assert res.unit.cardinality["L"] == 1
    assert res.unit.cardinality["T"] == -1
    assert res.unit_name == "meter / second"


@pytest.mark.temperature
def test_absolute_temperature_conversion(make_quantity):
    """Verify successful absolute temperature conversion via to() (lines 107-110)."""
    qty = make_quantity(0, "degC")
    res = qty.to("degF")
    assert res.unit_name == "degree_Fahrenheit"
    assert res == make_quantity(32, "degF")


@pytest.mark.temperature
def test_absolute_temperature_conversion_exception_handling(make_quantity):
    """Verify exception handling in absolute temperature conversion (lines 111-112)."""
    qty = make_quantity(30, "degC")
    with pytest.raises(TypeError, match="Dimensional Mismatch"):
        _ = qty.to("meter")


@pytest.mark.temperature
def test_temperature_subtraction_for_different_units(make_quantity):
    """Verify subtraction of Fahrenheit, Kelvin, and Rankine absolute temperatures (lines 82-88)."""
    # Fahrenheit
    tf1 = make_quantity(50, "degF")
    tf2 = make_quantity(32, "degF")
    diff_f = tf1 - tf2
    assert diff_f.unit_name == "delta_degree_Fahrenheit"
    assert diff_f.expressed_value == Rational(18)

    # Kelvin
    tk1 = make_quantity(300, "K")
    tk2 = make_quantity(200, "K")
    diff_k = tk1 - tk2
    assert diff_k.unit_name == "delta_kelvin"
    assert diff_k.expressed_value == Rational(100)

    # Rankine
    tr1 = make_quantity(500, "rankine")
    tr2 = make_quantity(400, "rankine")
    diff_r = tr1 - tr2
    assert diff_r.unit_name == "delta_degree_Rankine"
    assert diff_r.expressed_value == Rational(100)
    
    # Direct get_relative_temp_unit_for test for rankine branch coverage
    from src.engine import get_relative_temp_unit_for
    from src.types import Unit, Temperature
    rankine_unit = Unit("rankine", Temperature.CARDINALITY, 1)
    res_rankine = get_relative_temp_unit_for(rankine_unit)
    assert res_rankine.name == "delta_rankine"
    
    # Custom absolute temperature fallback
    custom_temp_unit = Unit("custom_temp", Temperature.CARDINALITY, 2)
    qty1 = Quantity(10, custom_temp_unit)
    qty2 = Quantity(5, custom_temp_unit)
    diff_custom = qty1 - qty2
    assert diff_custom.unit_name == "delta_custom_temp"


@pytest.mark.conversion
def test_combine_cardinalities_invalid_op():
    """Verify combine_cardinalities behaves correctly with an invalid/unsupported op."""
    from src.engine import combine_cardinalities
    from src.types import Length, Mass
    from typing import cast, Any
    res = combine_cardinalities(Length.CARDINALITY, Mass.CARDINALITY, cast(Any, "other"))
    # Since op is not 'add', it defaults to subtraction
    expected = combine_cardinalities(Length.CARDINALITY, Mass.CARDINALITY, "sub")
    assert res == expected



@pytest.mark.conversion
def test_empty_dimension_subclass_defaults_cardinality_to_zeroes():
    """Verify that a Dimension subclass with empty/missing cardinality defaults to all zeroes."""
    from src.types import Dimension
    
    class EmptyDimension(Dimension):
        CARDINALITY = {}
        
    assert all(val == 0 for val in EmptyDimension.CARDINALITY.values())


@pytest.mark.temperature
@pytest.mark.temperature
def test_absolute_temperature_multiplication_construction_and_guards(make_quantity):
    """Verify high-precision absolute temperature multiplication construction rules and guard exceptions."""
    from src.types import Quantity, Unit, MathematicalError
    from src.engine import resolve_unit
    from sympy import Rational
    
    # 1. __neg__ checks
    abs_temp = make_quantity(1, "degC")
    with pytest.raises(TypeError, match="Cannot negate absolute temperatures"):
        _ = -abs_temp
        
    normal_qty = make_quantity(5, "meter")
    assert (-normal_qty).value == Rational(-5)
    
    # 2. __mul__ absolute temp * scalar MUST fail cleanly now (zero workarounds/surprises!)
    with pytest.raises(TypeError, match="Cannot multiply absolute temperatures"):
        _ = abs_temp * 5
        
    abs_temp_large = make_quantity(10, "degC")
    with pytest.raises(TypeError, match="Cannot multiply absolute temperatures"):
        _ = abs_temp_large * 5
        
    # 3. __mul__ dimensionless quantity * absolute temp MUST fail cleanly
    dimless_qty = make_quantity(5, "dimensionless")
    with pytest.raises(TypeError, match="Cannot multiply absolute temperatures"):
        _ = dimless_qty * abs_temp
        
    with pytest.raises(TypeError, match="Cannot multiply absolute temperatures"):
        _ = dimless_qty * abs_temp_large
        
    # 4. __rmul__ with Rational scalar on absolute temp MUST fail cleanly
    with pytest.raises(TypeError, match="Cannot multiply absolute temperatures"):
        _ = Rational(5, 9) * make_quantity(1, "degF")
        
    with pytest.raises(TypeError, match="Cannot multiply absolute temperatures"):
        _ = 5 * abs_temp_large

    # 5. Native Unit Algebra & Construction (Allowed and clean!)
    degC_unit = resolve_unit("degC")
    res_mul1 = 5 * degC_unit
    assert res_mul1.expressed_value == Rational(5)
    assert res_mul1.unit_name == "degree_Celsius"
    
    res_mul2 = degC_unit * 5
    assert res_mul2.expressed_value == Rational(5)
    assert res_mul2.unit_name == "degree_Celsius"

    # Compound units
    m_unit = resolve_unit("m")
    s_unit = resolve_unit("s")
    
    m_s_unit = m_unit * s_unit
    assert m_s_unit.cardinality["L"] == 1
    assert m_s_unit.cardinality["T"] == 1
    
    m_per_s_unit = m_unit / s_unit
    assert m_per_s_unit.cardinality["L"] == 1
    assert m_per_s_unit.cardinality["T"] == -1
    
    recip_s_qty = 10 / s_unit
    assert recip_s_qty.value == Rational(10)
    assert recip_s_qty.unit.cardinality["T"] == -1
    
    m_sq_unit = m_unit ** 2
    assert m_sq_unit.cardinality["L"] == 2

    # Insecure string rational parsing value error checks
    with pytest.raises(ValueError, match="Invalid or insecure numerical value"):
        _ = Quantity("__import__('os').system('ls')", "m")

    # Zero-value reciprocal MathematicalError checks
    zero_s = make_quantity(0, "s")
    with pytest.raises(MathematicalError, match="Zero-value quantity has no defined reciprocal"):
        _ = zero_s.to("Hz")

    # 6. Unit NotImplemented checks
    with pytest.raises(TypeError):
        _ = m_unit * "invalid"
    with pytest.raises(TypeError):
        _ = m_unit / "invalid"
    with pytest.raises(TypeError):
        _ = "invalid" / m_unit
    with pytest.raises(TypeError):
        _ = m_unit ** "invalid"
        
    # Quantity fallback fallback
    class DummyBadStr:
        def __str__(self):
            return "not_a_rational"
    with pytest.raises(ValueError, match="Invalid or insecure numerical value"):
        _ = Quantity(DummyBadStr(), "meter")





