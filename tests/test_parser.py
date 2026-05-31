import pytest
from sympy import Rational
from src.types import Quantity
from src.parser import parse_and_evaluate, SecurityError, ExpressionParsingError

# ==========================================
# 1. PARSER INPUT TOLERANCE TESTS
# ==========================================

@pytest.mark.conversion
@pytest.mark.parametrize(
    "expression, expected_value, expected_unit",
    [
        # Messy spacing and synonyms
        ("10 m/s * 5 s", 50, "meter"),
        ("10 m / s * 5 s", 50, "meter"),
        ("10 meters per second * 5 seconds", 50, "meter"),
        # Implicit multiplication
        ("10m/s * 5s", 50, "meter"),
        ("5kg * 9.8m/s**2", 49, "kilogram * meter / second ** 2"),
        # Brackets and parentheses
        ("(5kg)(9.8m/s**2)", 49, "kilogram * meter / second ** 2"),
        ("10(m/s) * 5(s)", 50, "meter"),
    ]
)
def test_parser_normalizes_messy_natural_phrasing_and_evaluates_correctly(
    expression, expected_value, expected_unit
):
    """Verify that the parser tolerates spacing variations, synonyms, and implicit multiplication."""
    # Arrange & Act
    result = parse_and_evaluate(expression)

    # Assert
    assert isinstance(result, Quantity)
    assert result == Quantity(expected_value, expected_unit)


# ==========================================
# 2. SECURITY AST SANDBOX TESTS
# ==========================================

@pytest.mark.security
@pytest.mark.parametrize(
    "exploit_expression",
    [
        "__import__('os').system('ls')",
        "eval('1+1')",
        "exec('x = 5')",
        "x = 5",
        "sin(3)",
        "10 * m; import os",
        "Quantity(10, 'meter')",
        "__builtins__",
    ]
)
def test_parser_blocks_unauthorized_rce_payloads_with_security_error(exploit_expression):
    """Verify that the AST security sandbox blocks unauthorized nodes, imports, and calls to prevent RCE."""
    # Arrange & Act & Assert
    with pytest.raises((SecurityError, ExpressionParsingError)):
        parse_and_evaluate(exploit_expression)


@pytest.mark.security
def test_parser_blocks_unauthorized_binary_operator():
    """Verify AST visitor blocks unauthorized binary operators."""
    with pytest.raises(SecurityError, match="Unauthorized binary operator"):
        parse_and_evaluate("10 & 5")


@pytest.mark.security
def test_parser_blocks_unauthorized_unary_operator():
    """Verify AST visitor blocks unauthorized unary operators."""
    with pytest.raises(SecurityError, match="Unauthorized unary operator"):
        parse_and_evaluate("not 5")


# ==========================================
# 3. MATHEMATICAL AND PARSER EDGE CASES
# ==========================================

@pytest.mark.conversion
def test_parser_raises_parsing_error_for_unrecognized_symbol():
    """Verify parser raises a detailed error for unrecognized variable or symbol names."""
    with pytest.raises(ExpressionParsingError, match="Unrecognized unit or symbol 'flugelhorn'"):
        parse_and_evaluate("10 * flugelhorn")


@pytest.mark.conversion
def test_parser_evaluates_euler_constant():
    """Verify parser evaluates Euler's constant E."""
    from sympy import E
    res = parse_and_evaluate("E")
    assert res == Quantity(E, "dimensionless")


@pytest.mark.conversion
def test_parser_evaluates_unary_operators():
    """Verify parser evaluates positive and negative unary prefix operators."""
    res1 = parse_and_evaluate("+5 m")
    assert res1 == Quantity(5, "meter")
    
    res2 = parse_and_evaluate("-5 m")
    assert res2 == Quantity(-5, "meter")


@pytest.mark.conversion
def test_parser_evaluates_subtraction_expressions():
    """Verify parser evaluates subtraction expressions."""
    res = parse_and_evaluate("10 m - 4 m")
    assert res == Quantity(6, "meter")


@pytest.mark.conversion
def test_parser_raises_zero_division_error():
    """Verify division by zero raises a strict ZeroDivisionError."""
    with pytest.raises(ZeroDivisionError, match="Nonsense: Division by zero."):
        parse_and_evaluate("10 m / 0")


@pytest.mark.conversion
def test_parser_raises_type_error_for_non_dimensionless_exponent():
    """Verify raising a quantity to a non-dimensionless power raises a TypeError."""
    with pytest.raises(TypeError, match="Exponents must be dimensionless"):
        parse_and_evaluate("10 m ** (2 m)")


@pytest.mark.conversion
def test_parser_evaluates_dimensionless_quantity_exponent():
    """Verify raising a quantity to a dimensionless quantity exponent is evaluated."""
    res = parse_and_evaluate("(10 m) ** (2 * rad)")
    assert res == Quantity(100, "meter ** 2")


@pytest.mark.conversion
def test_parser_evaluates_raw_number_exponentiation():
    """Verify raw scalar exponentiation behaves correctly."""
    res = parse_and_evaluate("2 ** 3")
    assert res == Rational(8)


# ==========================================
# 4. DERIVED & DIMENSIONLESS QUANTITIES VALIDATION TESTS
# ==========================================

@pytest.mark.force
@pytest.mark.parametrize(
    "expr, expected_val, expected_unit",
    [
        ("10 N + 5 N", 15, "newton"),
        ("5 lbf * 2", 10, "pound_force"),
    ]
)
def test_force_derived_quantities_arithmetic_succeeds(expr, expected_val, expected_unit):
    """Verify that derived force quantities evaluate and compose correctly."""
    # Arrange & Act
    res = parse_and_evaluate(expr)
    # Assert
    assert res == Quantity(expected_val, expected_unit)


@pytest.mark.pressure
@pytest.mark.stress
@pytest.mark.parametrize(
    "expr, expected_val, expected_unit",
    [
        ("10 Pa + 10 Pa", 20, "pascal"),
        ("1 bar + 100000 Pa", 2, "bar"),
        ("5 psi * 2", 10, "psi"),
    ]
)
def test_pressure_and_stress_quantities_arithmetic_succeeds(expr, expected_val, expected_unit):
    """Verify that derived pressure and stress quantities evaluate and compose correctly."""
    # Arrange & Act
    res = parse_and_evaluate(expr)
    # Assert
    assert res == Quantity(expected_val, expected_unit)


@pytest.mark.velocity
@pytest.mark.acceleration
@pytest.mark.parametrize(
    "expr, expected_val, expected_unit",
    [
        ("10 m/s + 5 m/s", 15, "meter / second"),
        ("9.8 m/s**2 * 2 s", 19.6, "meter / second"),
    ]
)
def test_kinematics_velocity_and_acceleration_composition_succeeds(expr, expected_val, expected_unit):
    """Verify that derived velocity and acceleration compose and convert correctly."""
    # Arrange & Act
    res = parse_and_evaluate(expr)
    # Assert
    assert res == Quantity(expected_val, expected_unit)


@pytest.mark.dimensionless
@pytest.mark.parametrize(
    "expr, expected_val, expected_unit",
    [
        ("180 degree", 180, "degree"),
        ("pi * rad", 180, "degree"),  # Angle conversion rad to deg
        ("50% + 0.5", 1, "dimensionless"),  # 50% = 0.5, so 0.5 + 0.5 = 1
    ]
)
def test_dimensionless_specializations_succeed(expr, expected_val, expected_unit):
    """Verify that angles, percentages, and dimensionless ratios evaluate and convert correctly."""
    # Arrange & Act
    res = parse_and_evaluate(expr)
    # Assert
    assert res == Quantity(expected_val, expected_unit)


# ==========================================
# 5. COMPLEXITY GUARDS & NATIVE UNIT PARSING
# ==========================================

def test_parser_enforces_maximum_length_limit():
    """Verify that expressions exceeding 500 characters are blocked."""
    huge_expr = "1 m" + " + 0 m" * 100  # 1 + 6*100 = 601 characters
    with pytest.raises(ExpressionParsingError, match="Expression exceeds maximum allowed length of 500 characters."):
        parse_and_evaluate(huge_expr)

def test_parser_enforces_maximum_nesting_depth_limit():
    """Verify that expressions exceeding 20 nested parentheses are blocked."""
    nested_expr = "(" * 21 + "1" + ")" * 21
    with pytest.raises(ExpressionParsingError, match="Expression nesting depth exceeds limit of 20."):
        parse_and_evaluate(nested_expr)

def test_parser_evaluates_raw_unit_directly_to_quantity_one():
    """Verify that parsing a raw unit name directly returns Quantity(1, unit)."""
    res = parse_and_evaluate("m")
    assert res == Quantity(1, "meter")


# ==========================================
# 6. CARET EXPONENTIATION & NORMALIZATION TESTS (USER STORY 2)
# ==========================================

@pytest.mark.conversion
@pytest.mark.parametrize(
    "expression, expected_value, expected_unit",
    [
        ("10^5", 100000, "dimensionless"),
        ("m/s^2", 1, "meter / second ** 2"),
        ("10 kg * (5 m/s^2)", 50, "kilogram * meter / second ** 2"),
        ("10m/s^2 * 5s", 50, "meter/second"),
        ("2^3 * m", 8, "meter"),
        ("10 m ** 2 * 5s^2", 50, "meter ** 2 * second ** 2"),
    ]
)
def test_parser_normalizes_caret_exponentiation_correctly(
    expression, expected_value, expected_unit
):
    """Verify that caret notation (^) is successfully preprocessed to (**) and evaluated."""
    res = parse_and_evaluate(expression)
    if isinstance(res, Quantity):
        assert res == Quantity(expected_value, expected_unit)
    else:
        assert res == Rational(expected_value)


# ==========================================
# 7. UNICODE SYMBOL NORMALIZATION TESTS (ADR 0003)
# ==========================================

@pytest.mark.conversion
@pytest.mark.parametrize(
    "expression, expected_value, expected_unit",
    [
        ("2 * π * 10 cm", 20 * 3.141592653589793, "centimeter"),  # pi -> 3.14159265...
        ("10 Ω", 10, "ohm"),
        ("100 μs", 100, "microsecond"),
    ]
)
def test_parser_preprocesses_unicode_symbols_correctly(
    expression, expected_value, expected_unit
):
    """Verify that Unicode symbols (π, Ω, μ) are successfully preprocessed to ASCII and evaluated."""
    res = parse_and_evaluate(expression)
    assert isinstance(res, Quantity)
    assert res == Quantity(expected_value, expected_unit)
