import json
import pytest

from src import server
from src.config import Config
from src.parser import SecurityError, ExpressionParsingError, parse_and_evaluate, preprocess_expression, prepare_expression
from src.server import dimensional_compute, set_reading_default


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.setattr(server, "_config", Config())
    monkeypatch.setattr(server, "_session_defaults", {})
    monkeypatch.setattr(server, "_session_readings", {})


def fraction_payload(res: str) -> dict:
    assert res.startswith("Ambiguous Fraction:")
    return json.loads(res.split("\n", 1)[1])


# --- Quantity literals bind number and unit ---

@pytest.mark.conversion
@pytest.mark.parametrize("expr, target, expected", [
    ("10 m / 2 s", "m/s", "Result: 5 meter / second"),
    ("100 W / 2 K", "W/K", "Result: 50 watt / kelvin"),
    ("10 m / 2 m/s", "s", "Result: 5 second"),
    ("3 * 4 m / 2 s", "m/s", "Result: 6 meter / second"),
    ("10 / (2 s)", "1/s", "Result: 5 1 / second"),
    ("(10/2) s", "s", "Result: 5 second"),
    ("(1/3) m", "m", "Result: 0.333333 meter"),
    ("10 m/s * 5 s", "m", "Result: 50 meter"),
    ("5 kg * 9.8 m/s**2", "N", "Result: 49 newton"),
    ("2 m ** 2 / 4 s", "m**2/s", "Result: 0.5 meter ** 2 / second"),
    ("10 m / 2 s ** 2", "m/s**2", "Result: 5 meter / second ** 2"),
    ("2 N * 3 m", "J", "Result: 6 joule"),
    ("-5 m / 2 s", "m/s", "Result: -2.5 meter / second"),
])
def test_number_unit_pairs_are_quantity_literals(expr, target, expected):
    assert dimensional_compute(expr, target) == expected


def test_a_unit_run_after_a_divisor_literal_is_absorbed():
    assert dimensional_compute("100 m / 2 m/s", "s") == "Result: 50 second"


def test_explicit_star_stays_left_to_right():
    assert dimensional_compute("10 m / 2 * s", "m*s") == "Result: 5 meter * second"


def test_mixed_magnitudes_and_prefixed_numbers_still_parse():
    assert dimensional_compute("1e3 m / 2 s", "m/s") == "Result: 500 meter / second"
    assert dimensional_compute("1.5 m + 50 cm", "m") == "Result: 2 meter"


# --- The ambiguous case: unit-free run divided by `number unit` ---

@pytest.mark.parametrize("expr, target", [("10 / 2 s", "s"), ("1/3 m", "m"), ("5 / 2 s", "s"), ("1 / 4 kg", "kg")])
def test_unit_free_fraction_before_a_unit_asks(expr, target):
    assert dimensional_compute(expr, target).startswith("Ambiguous Fraction:")


def test_ambiguity_response_lists_both_results():
    payload = fraction_payload(dimensional_compute("10 / 2 s", "s"))
    (label, readings), = payload["occurrences"].items()
    assert label == "10 / 2 s"
    assert readings == {"scalar": "(10/2) s", "divisor": "10/(2 s)"}
    results = {list(i["treat"].values())[0]: i["result"] for i in payload["interpretations"]}
    # the divisor reading is 5 per second, which the reciprocal solver can still express in seconds
    assert results == {"scalar": "5 second", "divisor": "0.2 second"}


def test_target_shapes_the_results_not_the_question():
    payload = fraction_payload(dimensional_compute("1/3 m", "1/m"))
    results = {list(i["treat"].values())[0]: i["result"] for i in payload["interpretations"]}
    assert results == {"scalar": "3 1 / meter", "divisor": "0.333333 1 / meter"}


def test_no_question_when_both_readings_agree():
    res = dimensional_compute("pi / 2 rad", "rad")
    assert res.startswith("Result: 1.5708 radian")
    assert "both readings give the same result" in res


def test_context_can_settle_the_fraction():
    # 1/(3 m) cannot be added to a length, so the scalar reading is the only valid one
    res = dimensional_compute("1/3 m + 2 m", "m")
    assert res.startswith("Result: 2.33333 meter")
    assert "the only reading valid here" in res


def test_assume_picks_the_reading_per_call():
    scalar = dimensional_compute("10 / 2 s", "s", assume={"fraction_unit": "scalar"})
    assert scalar.startswith("Result: 5 second") and "(assumed by caller)" in scalar
    divisor = dimensional_compute("10 / 2 s", "1/s", assume={"fraction_unit": "divisor"})
    assert divisor.startswith("Result: 5 1 / second")


def test_invalid_choice_is_an_assumption_error():
    res = dimensional_compute("10 / 2 s", "s", assume={"fraction_unit": "both"})
    assert res.startswith("Assumption Error:") and "scalar, divisor" in res


# --- Recorded decisions ---

def test_session_decision_is_recorded_and_reused():
    assert set_reading_default("fraction_unit", "scalar") == "Reading default recorded: fraction_unit = scalar."
    first = dimensional_compute("10 / 2 s", "s")
    second = dimensional_compute("1/3 m", "m")
    assert first.startswith("Result: 5 second") and "(session decision)" in first
    assert second.startswith("Result: 0.333333 meter")


def test_assume_beats_session_decision():
    set_reading_default("fraction_unit", "scalar")
    res = dimensional_compute("10 / 2 s", "1/s", assume={"fraction_unit": "divisor"})
    assert res.startswith("Result: 5 1 / second")


def test_config_decision_is_used_and_session_beats_it(monkeypatch):
    monkeypatch.setattr(server, "_config", Config(readings={"fraction_unit": "divisor"}))
    res = dimensional_compute("10 / 2 s", "1/s")
    assert res.startswith("Result: 5 1 / second") and "(configured default)" in res
    set_reading_default("fraction_unit", "scalar")
    assert dimensional_compute("10 / 2 s", "s").startswith("Result: 5 second")


def test_temperature_decisions_can_be_recorded_too():
    assert set_reading_default("degC", "point").startswith("Reading default recorded")
    res = dimensional_compute("1 mol * 8.314 J/(mol*K) * 20 degC", "J")
    assert res.startswith("Result: 2437.25 joule") and "(session decision)" in res


@pytest.mark.parametrize("question, choice", [("fraction_unit", "maybe"), ("m", "point"), ("degC", "scalar")])
def test_set_reading_default_rejects_bad_input(question, choice):
    assert set_reading_default(question, choice).startswith("Assumption Error:")


# --- Marker handling and security ---

def test_user_typed_marker_is_rejected():
    with pytest.raises(SecurityError, match="MatMult"):
        parse_and_evaluate("10 @ 5")
    assert dimensional_compute("10 m @ 5 m", "m").startswith("Security Error:")


def test_preprocess_marks_only_inserted_multiplications_when_asked():
    assert preprocess_expression("10 m / 2 s") == "10 * m / 2 * s"
    assert preprocess_expression("10 m / 2 s", mark=True) == "10 @ m / 2 @ s"
    assert preprocess_expression("(2)m", mark=True) == "(2) @ m"
    assert prepare_expression("5 m * 2 s") == "5 @ m * 2 @ s"


def test_prepared_text_is_not_preprocessed_twice():
    assert parse_and_evaluate(prepare_expression("10 m / 2 s"), _prepared=True).dimensionality == \
        "[length] * [time] ** -1"


def test_length_limit_still_applies_before_marking():
    with pytest.raises(ExpressionParsingError, match="maximum allowed length"):
        prepare_expression("1 m + " * 100 + "1 m")


# --- Interaction with temperatures (ADR 0005) ---

def test_juxtaposed_temperature_literal_binds_through_a_division():
    res = dimensional_compute("101.325 kPa * 2 L / 20 degC", "kPa*L/K")
    assert res.startswith("Result: 0.691284 kilopascal * liter / kelvin")


def test_explicit_star_before_an_offset_unit_is_a_compound_unit():
    res = dimensional_compute("2 m * 5 * degC", "m*delta_degC")
    assert res.startswith("Result: 10 delta_degree_Celsius * meter")


def test_pure_unit_classification():
    import ast
    from src.juxtaposition import _is_pure_unit
    parse = lambda text: ast.parse(text, mode="eval").body
    assert _is_pure_unit(parse("m / s ** 2"))
    assert not _is_pure_unit(parse("m + s"))
    assert not _is_pure_unit(parse("2 * m"))
    assert not _is_pure_unit(parse("pi"))
