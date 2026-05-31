import pytest
from unittest.mock import patch

# ==========================================
# 1. MCP SERVER ENDPOINT TESTS
# ==========================================

@pytest.mark.conversion
def test_mcp_dimensional_compute_endpoint_success():
    """Verify that the primary MCP tool endpoint parses and computes expressions correctly."""
    # Arrange & Act
    from src.server import dimensional_compute
    res = dimensional_compute("10 m/s * 5 s", "foot")
    # Assert
    assert "approx. 164.042" in res


@pytest.mark.conversion
def test_mcp_dimensional_compute_endpoint_error_handling():
    """Verify that the primary MCP tool endpoint returns a clean string with error info on calculation failures."""
    # Arrange & Act
    from src.server import dimensional_compute
    err_res = dimensional_compute("10 m + 5 kg", "meter")
    # Assert
    assert "Type Error: Dimensional Mismatch: Cannot add incompatible dimensions" in err_res


@pytest.mark.conversion
def test_mcp_dimensional_compute_dimensionless_numbers():
    """Verify that the primary MCP tool handles pure dimensionless inputs correctly."""
    from src.server import dimensional_compute
    res = dimensional_compute("2 * 5", "dimensionless")
    assert "Result: 10 dimensionless" in res


@pytest.mark.security
def test_mcp_dimensional_compute_security_error_handling():
    """Verify that the primary MCP tool endpoint catches and formats AST security errors."""
    from src.server import dimensional_compute
    res = dimensional_compute("__import__('os').system('ls')", "meter")
    assert "Security Error: Unauthorized operation 'Call' detected in expression." in res


@pytest.mark.conversion
def test_mcp_dimensional_compute_parsing_error_handling():
    """Verify that the primary MCP tool endpoint catches and formats AST parsing errors."""
    from src.server import dimensional_compute
    res = dimensional_compute("10 * flugelhorn", "meter")
    assert "Parsing Error: Unrecognized unit or symbol 'flugelhorn' in expression." in res


@pytest.mark.conversion
def test_mcp_dimensional_compute_zero_division_error_handling():
    """Verify that the primary MCP tool endpoint catches and formats math/division-by-zero errors."""
    from src.server import dimensional_compute
    res = dimensional_compute("10 m / 0", "meter")
    assert "Math Error: Nonsense: Division by zero." in res


@pytest.mark.conversion
def test_mcp_dimensional_compute_unexpected_error_handling():
    """Verify that the primary MCP tool endpoint catches and formats unexpected exceptions cleanly."""
    from src.server import dimensional_compute
    from unittest.mock import patch
    with patch("src.server.parse_and_evaluate", side_effect=RuntimeError("Unexpected crash")):
        res = dimensional_compute("10 m", "meter")
        assert "Error: Unexpected error during evaluation" in res


@pytest.mark.conversion
def test_mcp_server_main_method_coordination():
    """Verify that the FastMCP server main method runs mcp.run() coordination successfully."""
    from src.server import main
    from unittest.mock import patch
    with patch("src.server.mcp.run") as mock_run:
        main()
        mock_run.assert_called_once()


@pytest.mark.conversion
def test_mcp_list_supported_units_resource_succeeds():
    """Verify that the supported units resource lists physical dimensions successfully."""
    # Arrange & Act
    from src.server import list_supported_units
    supported_units_json = list_supported_units()
    # Assert
    assert "length" in supported_units_json
    assert "degree_Celsius" in supported_units_json


@pytest.mark.conversion
def test_mcp_verify_dimensional_consistency_prompt_template_succeeds():
    """Verify that the consistency prompt template resolves successfully."""
    # Arrange & Act
    from src.server import verify_dimensional_consistency
    prompt_text = verify_dimensional_consistency("F = m * a")
    # Assert
    assert "physics and engineering validator" in prompt_text
    assert "F = m * a" in prompt_text


# ==========================================
# 2. TYPES & ARITHMETIC TESTS
# ==========================================

@pytest.mark.conversion
def test_quantity_init_pint_quantity():
    """Verify Quantity correctly parses a pint.Quantity magnitude and unit."""
    from src.types import Quantity
    from src.engine import ureg
    pint_q = ureg.Quantity(5, "meter")
    qty = Quantity(2, pint_q)
    assert qty.unit_name == "meter"
    assert qty.expressed_value == 10


@pytest.mark.conversion
def test_quantity_init_pint_unit():
    """Verify Quantity correctly parses a pint.Unit input."""
    from src.types import Quantity
    from src.engine import ureg
    pint_u = ureg("meter").units
    qty = Quantity(15, pint_u)
    assert qty.unit_name == "meter"
    assert qty.expressed_value == 15


@pytest.mark.conversion
def test_quantity_str_representation():
    """Verify clean string representations format of physical quantities."""
    from src.types import Quantity
    qty = Quantity("2/3", "meter")
    assert str(qty) == "2/3 meter"
    assert repr(qty) == "2/3 meter"


@pytest.mark.conversion
def test_quantity_equality_cases():
    """Verify equality rules on physical quantities (checking matching dimensional cardinalities)."""
    from src.types import Quantity
    q1 = Quantity(10, "meter")
    q2 = Quantity(10, "meter")
    q3 = Quantity(10, "second")
    assert q1 == q2
    assert q1 != q3
    assert q1 != "not_a_quantity"


@pytest.mark.conversion
def test_quantity_addition_with_dimensionless():
    """Verify adding dimensionless scalar or raw number to physical quantity."""
    from src.types import Quantity
    q_dimless = Quantity(5, "dimensionless")
    res1 = q_dimless + 2
    res2 = 2 + q_dimless
    assert res1.expressed_value == 7
    assert res2.expressed_value == 7


@pytest.mark.conversion
def test_quantity_addition_mismatch_raises_type_error():
    """Verify adding mismatched dimensional units raises a clean TypeError."""
    from src.types import Quantity
    q1 = Quantity(10, "meter")
    q2 = Quantity(5, "second")
    with pytest.raises(TypeError, match="Dimensional Mismatch: Cannot add incompatible dimensions"):
        _ = q1 + q2


@pytest.mark.temperature
def test_absolute_temperature_subtraction_produces_relative_delta():
    """Verify subtracting absolute temperature coordinates yields a relative temperature difference delta unit."""
    from src.types import Quantity
    t1 = Quantity(30, "degC")
    t2 = Quantity(10, "degC")
    diff = t1 - t2
    assert diff.unit_name == "delta_degree_Celsius"
    assert diff.expressed_value == 20


@pytest.mark.temperature
def test_temperature_delta_subtraction_absolute_raises_error():
    """Verify subtracting an absolute temperature coordinate from a relative difference raises a TypeError."""
    from src.types import Quantity
    t_delta = Quantity(10, "delta_degC")
    t_abs = Quantity(30, "degC")
    with pytest.raises(TypeError, match="Nonsense: Cannot subtract an absolute temperature from a temperature difference"):
        _ = t_delta - t_abs


@pytest.mark.temperature
def test_temperature_addition_shifts_absolute_coordinate():
    """Verify adding a relative delta offset to an absolute temperature shifts the coordinate properly."""
    from src.types import Quantity
    t_abs = Quantity(30, "degC")
    t_delta = Quantity(10, "delta_degC")
    
    res1 = t_abs + t_delta
    res2 = t_delta + t_abs
    
    assert res1.unit_name == "degree_Celsius"
    assert res1.expressed_value == 40
    assert res2.unit_name == "degree_Celsius"
    assert res2.expressed_value == 40


@pytest.mark.temperature
def test_temperature_absolute_coordinate_addition_raises_error():
    """Verify that adding two absolute temperature coordinates raises a strict physical TypeError."""
    from src.types import Quantity
    t1 = Quantity(30, "degC")
    t2 = Quantity(10, "degC")
    with pytest.raises(TypeError, match="Nonsense: Cannot add two absolute temperatures"):
        _ = t1 + t2


@pytest.mark.temperature
def test_absolute_temperature_multiplication_division_guards():
    """Verify scaling absolute temperature coordinates raises absolute coordinate physical constraints TypeErrors."""
    from src.types import Quantity
    t_abs = Quantity(30, "degC")
    
    with pytest.raises(TypeError, match="Cannot multiply absolute temperatures"):
        _ = t_abs * 2
        
    with pytest.raises(TypeError, match="Cannot multiply absolute temperatures"):
        _ = 2 * t_abs
        
    with pytest.raises(TypeError, match="Cannot divide absolute temperatures"):
        _ = t_abs / 2
        
    with pytest.raises(TypeError, match="Cannot divide absolute temperatures"):
        _ = 2 / t_abs


@pytest.mark.conversion
def test_quantity_multiplication_division():
    """Verify standard physical quantities multiplication and division algebraic combinations."""
    from src.types import Quantity
    q1 = Quantity(10, "meter")
    q2 = Quantity(5, "second")
    
    res_mul = q1 * q2
    assert res_mul.expressed_value == 50
    assert "meter * second" in res_mul.unit_name
    
    res_div = q1 / q2
    assert res_div.expressed_value == 2
    assert "meter / second" in res_div.unit_name
    
    # Raw scalar math
    assert (q1 * 3).expressed_value == 30
    assert (3 * q1).expressed_value == 30
    assert (q1 / 2).expressed_value == 5
    assert (20 / q1).expressed_value == 2


@pytest.mark.conversion
def test_quantity_dimensionality_string():
    """Verify physical quantity dimensionality strings format."""
    from src.types import Quantity
    q_len = Quantity(10, "meter")
    assert q_len.dimensionality == "[length]"
    
    q_acc = Quantity(9.8, "meter / second ** 2")
    assert "[length]" in q_acc.dimensionality
    assert "[time] ** -2" in q_acc.dimensionality
    
    q_dimless = Quantity(5, "dimensionless")
    assert q_dimless.dimensionality == "dimensionless"


# ==========================================
# 3. ENGINE & CONVERSION EDGE CASES
# ==========================================

@pytest.mark.conversion
def test_engine_resolve_unit_unknown_raises_error():
    """Verify resolve_unit raises an ExpressionParsingError for unrecognized names."""
    from src.engine import resolve_unit
    from src.parser import ExpressionParsingError
    with pytest.raises(ExpressionParsingError, match="Unrecognized unit or symbol 'flugelhorn'"):
        resolve_unit("flugelhorn")


@pytest.mark.temperature
def test_engine_absolute_temperature_offset_conversions():
    """Verify offset coordinate conversions on absolute temperatures."""
    import math
    from src.types import Quantity
    t_c = Quantity(0, "degC")
    t_f = t_c.to("degF")
    assert math.isclose(float(t_f.expressed_value), 32, rel_tol=1e-9)
    
    t_k = t_c.to("kelvin")
    assert math.isclose(float(t_k.expressed_value), 273.15, rel_tol=1e-9)


@pytest.mark.conversion
def test_engine_incompatible_conversion_raises_error():
    """Verify converting to incompatible dimension raises a clean TypeError."""
    from src.types import Quantity
    q1 = Quantity(10, "meter")
    with pytest.raises(TypeError, match="Dimensional Mismatch: Cannot convert quantity with unit 'meter'"):
        _ = q1.to("kilogram")


@pytest.mark.conversion
def test_engine_unknown_target_unit_raises_error():
    """Verify converting to an unknown target unit name raises an ExpressionParsingError."""
    from src.types import Quantity
    from src.parser import ExpressionParsingError
    q1 = Quantity(10, "meter")
    with pytest.raises(ExpressionParsingError, match="Unrecognized unit or symbol 'flugelhorn'"):
        _ = q1.to("flugelhorn")


@pytest.mark.inversion
def test_engine_generalized_reciprocal_inversion_mpg_to_metric():
    """Verify generalized reciprocal inversions between MPG and L/100km."""
    from src.types import Quantity
    mpg = Quantity(30, "mile / gallon")
    l_100km = mpg.to("liter / (100 * kilometer)")
    # 30 MPG approx equals 7.84 L/100km
    assert round(float(l_100km.expressed_value), 4) == 7.8405


# ==========================================
# 4. PARSER & AST SANDBOX EDGE CASES
# ==========================================

@pytest.mark.security
def test_parser_security_rce_blocks():
    """Verify AST visitor whitelisting blocks unauthorized node injections."""
    from src.parser import parse_and_evaluate, SecurityError
    with pytest.raises(SecurityError, match="Unauthorized operation 'Call'"):
        parse_and_evaluate("sin(3)")
        
    with pytest.raises(SecurityError, match="Unauthorized operation 'Attribute'"):
        parse_and_evaluate("x.y")


@pytest.mark.conversion
def test_parser_pre_processor_normalizations():
    """Verify that parser normalizes dynamic expressions cleanly."""
    from src.parser import parse_and_evaluate
    from src.types import Quantity
    
    # Space tolerance
    res1 = parse_and_evaluate("10 m / s * 5 s")
    assert res1.expressed_value == 50
    
    # Implicit multiplication
    res2 = parse_and_evaluate("10m/s * 5s")
    assert res2.expressed_value == 50
    
    # Synonyms
    res3 = parse_and_evaluate("10 meters per second * 5 seconds")
    assert res3.expressed_value == 50
    
    # Percentages
    res4 = parse_and_evaluate("50% + 0.5")
    assert res4.expressed_value == 100


@pytest.mark.conversion
def test_parser_pi_and_e_evaluations():
    """Verify parser evaluates Euler's constant E and Pi successfully."""
    from src.parser import parse_and_evaluate
    from sympy import pi, E
    
    res_pi = parse_and_evaluate("pi")
    assert res_pi.expressed_value == pi
    
    res_e = parse_and_evaluate("E")
    assert res_e.expressed_value == E


@pytest.mark.conversion
def test_parser_dimensionless_exponent_guards():
    """Verify raising a physical quantity to a non-dimensionless exponent raises a TypeError."""
    from src.parser import parse_and_evaluate
    with pytest.raises(TypeError, match="Nonsense: Exponents must be dimensionless."):
        parse_and_evaluate("10 m ** (2 s)")


@pytest.mark.conversion
def test_parser_quantity_dimensionless_exponentiation():
    """Verify raising a physical quantity to a dimensionless quantity exponent works correctly."""
    from src.parser import parse_and_evaluate
    res = parse_and_evaluate("(10 m) ** (2 * rad)")
    assert res.expressed_value == 100
    assert "meter ** 2" in res.unit_name


# ==========================================
# 5. HIGH-PRECISION 100% COVERAGE TARGETED TESTS
# ==========================================

@pytest.mark.conversion
def test_types___init_subclass___mro_walk():
    """Verify that __init_subclass__ walks the MRO to inherit CARDINALITY from parent classes."""
    from src.types import Dimension, Length
    class SubLength(Length):
        pass
    assert SubLength.CARDINALITY == {"L": 1, "M": 0, "T": 0, "Theta": 0, "I": 0, "N": 0, "J": 0}

    # Verify None-valued base class and loop-finishing branch coverage
    import src.types
    original_card = src.types.Dimension.CARDINALITY
    try:
        src.types.Dimension.CARDINALITY = None
        class TempSubclass(src.types.Dimension):
            pass
        assert TempSubclass.CARDINALITY == {"L": 0, "M": 0, "T": 0, "Theta": 0, "I": 0, "N": 0, "J": 0}
    finally:
        src.types.Dimension.CARDINALITY = original_card



@pytest.mark.conversion
def test_quantity_init_with_unsupported_value_type_fallback():
    """Verify fallback to direct rational initialization when sympify fails."""
    from src.types import Quantity
    from sympy import Rational
    class DummyStr:
        def __str__(self):
            return "42/5"
    qty = Quantity(DummyStr(), "meter")
    assert qty.value == Rational(42, 5)


@pytest.mark.conversion
def test_quantity_to_unit_object():
    """Verify Quantity.to() accepts a Unit object directly."""
    from src.types import Quantity
    from src.engine import resolve_unit
    qty = Quantity(10, "meter")
    u_inch = resolve_unit("inch")
    qty_inch = qty.to(u_inch)
    assert qty_inch.unit_name == "inch"


@pytest.mark.conversion
def test_quantity_subtraction_with_dimensionless():
    """Verify subtracting a raw dimensionless scalar or quantity commutatively."""
    from src.types import Quantity
    q1 = Quantity(10, "meter")
    q2 = Quantity(5, "meter")
    # Commutative explicit __rsub__ check
    assert q1.__rsub__(q2) == q2 - q1

    qty = Quantity(5, "dimensionless")
    res1 = qty - 2
    res2 = 2 - qty
    assert res1.expressed_value == 3
    assert res2.expressed_value == -3


@pytest.mark.conversion
def test_quantity_subtraction_mismatch_raises_error():
    """Verify subtracting incompatible dimensions raises a TypeError."""
    from src.types import Quantity
    q1 = Quantity(10, "meter")
    q2 = Quantity(5, "second")
    with pytest.raises(TypeError, match="Dimensional Mismatch: Cannot subtract incompatible dimensions"):
        _ = q1 - q2


@pytest.mark.security
def test_parser_unauthorized_binary_operator():
    """Verify whitelisting blocks unauthorized binary operators in parser."""
    from src.parser import parse_and_evaluate, SecurityError
    with pytest.raises(SecurityError, match="Unauthorized binary operator"):
        parse_and_evaluate("10 & 5")


@pytest.mark.security
def test_parser_unauthorized_unary_operator():
    """Verify whitelisting blocks unauthorized unary operators in parser."""
    from src.parser import parse_and_evaluate, SecurityError
    with pytest.raises(SecurityError, match="Unauthorized unary operator"):
        parse_and_evaluate("not 5")


@pytest.mark.security
def test_parser_blocks_underscore_name():
    """Verify whitelisting blocks variable names starting with underscore."""
    from src.parser import parse_and_evaluate, SecurityError
    with pytest.raises(SecurityError, match="Unauthorized name '__builtins__'"):
        parse_and_evaluate("__builtins__")


@pytest.mark.conversion
def test_parser_zero_division_error_directly():
    """Verify division by zero raises ZeroDivisionError."""
    from src.parser import parse_and_evaluate
    with pytest.raises(ZeroDivisionError, match="Nonsense: Division by zero."):
        parse_and_evaluate("10 m / 0")


@pytest.mark.conversion
def test_parser_unsupported_ast_node_evaluation():
    """Verify direct AST evaluator throws on completely unsupported node types."""
    from src.parser import _evaluate_ast_node
    import ast
    with pytest.raises(AttributeError, match="'Pass' object has no attribute 'left'"):
        _evaluate_ast_node(ast.Pass())


@pytest.mark.conversion
def test_parser_syntax_error_parsing():
    """Verify expression parsing raises ExpressionParsingError on syntax failure."""
    from src.parser import parse_and_evaluate, ExpressionParsingError
    with pytest.raises(ExpressionParsingError, match="Syntax error in expression"):
        parse_and_evaluate("10 * + / - 5")


@pytest.mark.conversion
def test_engine_resolve_unit_composed_quantity():
    """Verify resolve_unit handles composed quantity units and delta coordinations."""
    from src.engine import resolve_unit
    u1 = resolve_unit("liter / (100 * kilometer)")
    assert u1.name == "liter / (100 * kilometer)"
    
    u2 = resolve_unit("1 / (mile / gallon)")
    assert u2.name == "gallon / mile"


@pytest.mark.temperature
def test_relative_temp_units_resolution():
    """Verify resolution of relative temp delta units for Celsius, Fahrenheit, Kelvin, Rankine, and custom temps."""
    from src.engine import get_relative_temp_unit_for, resolve_unit
    
    u_c = resolve_unit("degC")
    assert get_relative_temp_unit_for(u_c).name == "delta_degree_Celsius"
    
    u_f = resolve_unit("degF")
    assert get_relative_temp_unit_for(u_f).name == "delta_degree_Fahrenheit"
    
    u_k = resolve_unit("kelvin")
    assert get_relative_temp_unit_for(u_k).name == "delta_kelvin"
    
    u_r = resolve_unit("rankine")
    assert get_relative_temp_unit_for(u_r).name == "delta_degree_Rankine"
    
    u_custom = resolve_unit("degree_Celsius")
    u_custom.name = "custom_temp"
    assert get_relative_temp_unit_for(u_custom).name == "delta_custom_temp"


@pytest.mark.temperature
def test_absolute_temperature_conversion_exception():
    """Verify that absolute temperature conversion raises descriptive TypeError if conversion fails."""
    from src.types import Quantity
    from src.engine import convert_quantity
    t_abs = Quantity(30, "degC")
    with pytest.raises(TypeError, match="Dimensional Mismatch"):
        convert_quantity(t_abs, "meter")


@pytest.mark.conversion
def test_mcp_dimensional_compute_zero_value_reciprocal_mathematical_error():
    """Verify that the primary MCP tool endpoint catches and formats MathematicalError on 0 reciprocal inversion."""
    from src.server import dimensional_compute
    res = dimensional_compute("0 s", "Hz")
    assert "Math Error: Nonsense: Zero-value quantity has no defined reciprocal." in res


@pytest.mark.conversion
def test_engine_case_insensitive_synonyms_resolution():
    """Verify robust case-insensitive resolution of MPG and L/100km."""
    from src.engine import resolve_unit
    from src.parser import parse_and_evaluate
    from src.types import Quantity
    
    # 1. Resolve unit mixed-case synonyms
    u_mpg = resolve_unit("Mpg")
    assert u_mpg.name == "mile / gallon"
    
    u_l100 = resolve_unit("L/100Km")
    assert u_l100.name == "liter / (100 * kilometer)"
    
    # 2. Parse and evaluate case-insensitive synonyms in expressions
    res_mpg = parse_and_evaluate("30 Mpg")
    assert isinstance(res_mpg, Quantity)
    assert res_mpg.unit_name == "mile / gallon"
    
    res_l100 = parse_and_evaluate("7.84 l/100KM")
    assert isinstance(res_l100, Quantity)
    assert "liter / kilometer" in res_l100.unit_name
    
    # Verify that converting it back to "l/100km" yields exactly 7.84
    converted = res_l100.to("l/100km")
    assert float(converted.expressed_value) == 7.84

