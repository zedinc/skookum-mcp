import json
import pytest

from src import server
from src.affine import canonical_scale_name
from src.readings import ReadingContext, ReadingQuestion, resolve_readings
from src.config import Config
from src.parser import parse_and_evaluate
from src.server import dimensional_compute


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.setattr(server, "_config", Config())
    monkeypatch.setattr(server, "_session_defaults", {})


def kind_payload(res: str) -> dict:
    assert res.startswith("Ambiguous Temperature Kind:")
    return json.loads(res.split("\n", 1)[1])


# --- Forced interval: a rate per the same scale ---

@pytest.mark.temperature
def test_rate_per_degc_forces_an_interval():
    res = dimensional_compute("2 kg * 4.18 kJ/(kg*degC) * 5 degC", "kJ")
    assert res.startswith("Result: 41.8 kilojoule")
    assert "5 degree_Celsius treated as delta_degree_Celsius (the other operand is a rate per degC)" in res


@pytest.mark.temperature
def test_rate_per_degf_forces_an_interval():
    res = dimensional_compute("1 kg * 1 BTU/(lb*degF) * 10 degF", "BTU")
    assert "treated as delta_degree_Fahrenheit" in res


@pytest.mark.temperature
def test_bare_offset_unit_in_a_compound_unit_is_a_scale_step():
    assert dimensional_compute("4.18 kJ/degC * 5 delta_degC", "kJ") == "Result: 20.9 kilojoule"


# --- Unforced points convert to the zero-based scale ---

@pytest.mark.temperature
def test_boyle_style_ratio_converts_celsius_to_kelvin():
    res = dimensional_compute("(101.325 kPa * 2 L) / (20 degC)", "kPa*L/K")
    assert res.startswith("Result: 0.691284 kilopascal * liter / kelvin")
    assert "20 degree_Celsius converted to 293.15 kelvin" in res


@pytest.mark.temperature
def test_unparenthesised_literal_binds_number_to_unit():
    res = dimensional_compute("101.325 kPa * 2 L / 20 degC", "kPa*L/K")
    assert res.startswith("Result: 0.691284")


@pytest.mark.temperature
def test_fahrenheit_converts_to_rankine():
    res = dimensional_compute("2 m * 68 degF", "m*degR")
    assert res.startswith("Result: 1055.34 degree_Rankine * meter")
    assert "converted to 527.67 degree_Rankine" in res


@pytest.mark.temperature
def test_point_scaled_by_a_number_and_raised_to_a_power_are_converted():
    assert dimensional_compute("5 degC * 2", "K").startswith("Result: 556.3 kelvin")
    res = dimensional_compute("(5 degC)**2", "K**2")
    assert "raised to a power" in res and res.startswith("Result: 77367.4")


@pytest.mark.temperature
def test_computed_point_is_converted_too():
    res = dimensional_compute("(20 degC + 5 delta_degC) * 2 m", "K*m")
    assert "25 degree_Celsius converted to 298.15 kelvin" in res


# --- Competing readings: per-kelvin rate next to a point ---

@pytest.mark.temperature
def test_per_kelvin_rate_with_a_point_is_ambiguous_with_both_results():
    payload = kind_payload(dimensional_compute("2 kg * 4.18 kJ/(kg*K) * 5 degC", "kJ"))
    assert set(payload["occurrences"]["5 degree_Celsius"]) == {"point", "interval"}
    results = {list(i["treat"].values())[0]: i["result"] for i in payload["interpretations"]}
    assert results == {"point": "2325.33 kilojoule", "interval": "41.8 kilojoule"}


@pytest.mark.temperature
@pytest.mark.parametrize("kind, expected", [("point", "Result: 2437.25 joule"), ("interval", "Result: 166.28 joule")])
def test_assume_settles_the_reading(kind, expected):
    res = dimensional_compute("1 mol * 8.314 J/(mol*K) * 20 degC", "J", assume={"degC": kind})
    assert res.startswith(expected) and "assumed by caller" in res


@pytest.mark.temperature
def test_writing_the_unit_you_mean_never_asks():
    assert dimensional_compute("1 mol * 8.314 J/(mol*K) * 293.15 K", "J").startswith("Result: 2437.25")
    assert dimensional_compute("1 mol * 8.314 J/(mol*K) * 20 delta_degC", "J").startswith("Result: 166.28")


@pytest.mark.temperature
def test_assume_applies_to_unforced_occurrences_of_unit_conversion_too():
    res = dimensional_compute("3 m * 2 degC", "m*delta_degC", assume={"degC": "interval"})
    assert res.startswith("Result: 6 delta_degree_Celsius * meter")


def test_assume_kind_for_a_non_offset_symbol_is_rejected():
    assert dimensional_compute("1 m", "m", assume={"m": "point"}).startswith("Assumption Error:")
    assert dimensional_compute("1 m", "m", assume={"C": "point"}).startswith("Assumption Error:")


def test_forced_rate_ignores_assume():
    res = dimensional_compute("2 kg * 4.18 kJ/(kg*degC) * 5 degC", "kJ", assume={"degC": "point"})
    assert res.startswith("Result: 41.8 kilojoule")


@pytest.mark.temperature
def test_two_ambiguous_occurrences_are_enumerated():
    payload = kind_payload(dimensional_compute("1 kJ/K * 5 degC + 1 kJ/K * 7 degC", "kJ"))
    assert len(payload["interpretations"]) == 4


# --- Still errors ---

@pytest.mark.temperature
@pytest.mark.parametrize("expr, fragment", [
    ("20 degC + 20 degC", "Cannot add two absolute temperatures"),
    ("-(5 degC)", "Cannot negate 'degree_Celsius'"),
])
def test_nonsense_remains_an_error(expr, fragment):
    res = dimensional_compute(expr, "K")
    assert res.startswith("Type Error:") and fragment in res


@pytest.mark.temperature
def test_zero_based_scales_never_trigger_inference():
    assert dimensional_compute("-5 K", "K") == "Result: -5 kelvin"
    assert dimensional_compute("300 K + -5 K", "K") == "Result: 295 kelvin"
    assert dimensional_compute("2 kg * 4.18 kJ/(kg*K) * 5 K", "kJ") == "Result: 41.8 kilojoule"


def test_quantity_api_stays_strict():
    from src.types import Quantity
    with pytest.raises(TypeError, match="Cannot multiply 'degree_Celsius'"):
        Quantity(3, "m") * Quantity(2, "degC")


@pytest.mark.temperature
def test_negative_literal_binds_to_its_unit():
    res = dimensional_compute("2 m * -5 degC", "m*K")
    assert res.startswith("Result: 536.3 kelvin * meter")
    assert "-5 degree_Celsius converted to 268.15 kelvin" in res


@pytest.mark.temperature
def test_rate_with_a_squared_scale_in_the_denominator_forces_an_interval():
    res = dimensional_compute("4 kJ/(kg*degC**2) * 5 degC", "kJ/(kg*delta_degC)")
    assert "treated as delta_degree_Celsius" in res


def test_scale_exponents_through_unary_and_power():
    import ast
    from src.affine import _scale_exponents
    assert _scale_exponents(ast.parse("-degC", mode="eval").body) == {"degree_Celsius": 1}
    assert _scale_exponents(ast.parse("1 / degC ** 2", mode="eval").body) == {"degree_Celsius": -2}
    assert _scale_exponents(ast.parse("degC + degF", mode="eval").body) == {}


# --- Helpers ---

def test_canonical_scale_name():
    assert canonical_scale_name("degC") == "degree_Celsius"
    assert canonical_scale_name("degF") == "degree_Fahrenheit"
    assert canonical_scale_name("K") is None
    assert canonical_scale_name("not_a_unit") is None


def test_parse_and_evaluate_without_kinds_still_works():
    assert parse_and_evaluate("5 m").expressed_value == 5


def _question(key, label="lit"):
    return ReadingQuestion(key, "temperature_kind", label, "degC", {"point": "p", "interval": "i"}, "summary.", "escape")


def test_resolve_readings_depth_limit():
    def always_ask(ctx: ReadingContext) -> str:
        raise _question(len(ctx.overrides), f"lit{len(ctx.overrides)}")

    with pytest.raises(TypeError, match="Too many ambiguous readings"):
        resolve_readings(always_ask)


def test_resolve_readings_all_options_invalid():
    def run(ctx: ReadingContext) -> str:
        if not ctx.overrides:
            raise _question("k")
        raise TypeError("bad")

    with pytest.raises(TypeError, match="No reading of the ambiguous expression is valid"):
        resolve_readings(run)


def test_resolve_readings_single_valid_option_notes_it():
    def run(ctx: ReadingContext) -> str:
        if not ctx.overrides:
            raise _question("k", "5 degree_Celsius")
        if ctx.overrides["k"] == "interval":
            raise TypeError("interval invalid")
        return "1 kelvin"

    text, notes = resolve_readings(run)
    assert text == "1 kelvin" and "5 degree_Celsius read as 'point'" in notes[0]


def test_resolve_readings_mixed_topics_use_a_generic_title():
    from src.readings import AmbiguousReadingError

    def run(ctx: ReadingContext) -> str:
        if "a" not in ctx.overrides:
            raise _question("a", "first")
        if "b" not in ctx.overrides:
            raise ReadingQuestion("b", "fraction_unit", "second", "fraction_unit",
                                  {"scalar": "s", "divisor": "d"}, "other summary.", "other escape")
        return str(sorted(ctx.overrides.items()))

    with pytest.raises(AmbiguousReadingError) as exc:
        resolve_readings(run)
    assert exc.value.title == "Ambiguous Reading"
