import pytest
from src.engine import convert_quantity

# ==========================================
# 1. GENERALIZED RECIPROCAL INVERSION TESTS
# ==========================================

@pytest.mark.inversion
@pytest.mark.parametrize(
    "source_val, source_unit, target_unit, expected_val, precision",
    [
        (30, "mile/gallon", "liter / (100 * kilometer)", 7.8405, 4),
        ("235214583 / 30000000", "liter / (100 * kilometer)", "mile/gallon", 30.0, 1),
    ]
)
def test_generalized_inversion_solver_mpg_and_metric_consumption_conversions(
    make_quantity, source_val, source_unit, target_unit, expected_val, precision
):
    """Verify that the generalized reciprocal inversion solver handles non-linear conversions (e.g. MPG to L/100km)."""
    # Arrange
    qty = make_quantity(source_val, source_unit)

    # Act
    converted = convert_quantity(qty, target_unit)

    # Assert
    assert round(float(converted.expressed_value), precision) == expected_val


@pytest.mark.conversion
def test_convert_quantity_raises_type_error_for_incompatible_dimensions(make_quantity):
    """Verify that converting to an incompatible dimension raises a TypeError."""
    # Arrange
    qty = make_quantity(10, "meter")
    
    # Act & Assert
    with pytest.raises(TypeError, match="Dimensional Mismatch: Cannot convert quantity with unit 'meter'"):
        _ = convert_quantity(qty, "kilogram")


@pytest.mark.conversion
def test_convert_quantity_raises_type_error_for_unknown_target_unit(make_quantity):
    """Verify that converting to an unknown unit name raises a TypeError containing 'unknown'."""
    # Arrange
    qty = make_quantity(10, "meter")
    
    # Act & Assert
    with pytest.raises(TypeError, match="unknown"):
        _ = convert_quantity(qty, "flugelhorn")


@pytest.mark.conversion
def test_resolve_unit_with_custom_dimension():
    """Verify that dim_map.get returning None is handled correctly (branch 72->70)."""
    from unittest.mock import patch, MagicMock
    from src.engine import resolve_unit
    
    mock_qty = MagicMock()
    mock_qty.units = "custom_unit"
    mock_qty.magnitude = 1
    # We return a custom dimension name not in dim_map, along with a standard one
    mock_qty.dimensionality = {"[length]": 1, "[unknown_dim]": 1}
    
    with patch("src.engine.ureg", return_value=mock_qty):
        unit = resolve_unit("custom_unit")
        assert unit.cardinality["L"] == 1
        assert unit.cardinality.get("unknown_dim") is None


@pytest.mark.conversion
def test_resolve_unit_scale_factor_fallback():
    """Verify that scale_factor defaults to 1 when Pint resolution raises exception (branch 53-54)."""
    from unittest.mock import patch, MagicMock
    from sympy import Rational
    from src.engine import resolve_unit
    
    mock_qty = MagicMock()
    mock_qty.units = "fallback_unit"
    mock_qty.magnitude = 1
    mock_qty.dimensionality = {"[length]": 1}
    
    # We patch ureg.__call__ to return mock_qty, but we patch ureg.Quantity to raise ValueError
    with patch("src.engine.ureg", return_value=mock_qty) as mock_ureg:
        # mock_ureg behaves as a callable returning mock_qty
        # but mock_qty.to_base_units should raise an exception
        mock_qty.to_base_units.side_effect = ValueError("Base units error")
        mock_ureg.Quantity.side_effect = ValueError("Quantity error")
        
        unit = resolve_unit("fallback_unit")
        assert unit.scale_factor == Rational(1)


@pytest.mark.conversion
def test_resolve_unit_synonyms():
    """Verify that resolve_unit resolves custom synonyms 'mpg' and 'l/100km' successfully."""
    from src.engine import resolve_unit
    
    unit_mpg = resolve_unit("mpg")
    assert unit_mpg.name == "mile / gallon"
    
    unit_l100km = resolve_unit("l/100km")
    assert unit_l100km.name == "liter / (100 * kilometer)"

