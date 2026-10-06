import json
import pytest

from src import server
from src.ambiguity import AMBIGUOUS, AssumptionError, find_candidate, registry_listing
from src.config import Config
from src.server import dimensional_compute, set_unit_default, list_ambiguous_units


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """Isolate every test from the user's real config and from session defaults."""
    monkeypatch.setattr(server, "_config", Config())
    monkeypatch.setattr(server, "_session_defaults", {})


def use_config(monkeypatch, **kwargs):
    monkeypatch.setattr(server, "_config", Config(**kwargs))


def ambiguity_payload(res: str) -> dict:
    assert res.startswith("Ambiguous Unit:")
    return json.loads(res.split("\n", 1)[1])


# --- Context inference ---

@pytest.mark.conversion
def test_context_resolves_point_vs_pint_from_a_length_neighbour():
    res = dimensional_compute("12 pt + 2 inch", "mm")
    assert res.startswith("Result: 55.0333 millimeter")
    assert "pt = typographic_point" in res


def test_context_resolves_celsius_vs_coulomb_from_a_temperature_delta():
    res = dimensional_compute("20 C + 5 delta_degF", "degC")
    assert res.startswith("Result: 22.7778 degree_Celsius")
    assert "C = celsius" in res


def test_context_resolves_coulomb_from_electrical_neighbour():
    res = dimensional_compute("5 C * 2 V", "J")
    assert res.startswith("Result: 10 joule")
    assert "C = coulomb" in res


def test_target_unit_is_context_too():
    res = dimensional_compute("1 oz", "g")
    assert res.startswith("Result: 28.3495 gram")
    assert "oz = ounce" in res


def test_ambiguous_target_is_resolved_from_the_expression():
    res = dimensional_compute("68 degF", "C")
    assert res.startswith("Result: 20 degree_Celsius")


# --- Structured ambiguity response ---

def test_unresolved_ambiguity_returns_structured_options_with_outcomes():
    payload = ambiguity_payload(dimensional_compute("1 ton", "kg"))
    assert [c["id"] for c in payload["tokens"]["ton"]] == ["short_ton", "long_ton", "metric_ton"]
    assert payload["tokens"]["ton"][0]["dimension"] == "[mass]"
    results = {i["assume"]["ton"]: i["result"] for i in payload["interpretations"]}
    assert results["metric_ton"] == "1000 kilogram"
    assert payload["rejected"] == []


def test_rejected_interpretations_explain_why():
    payload = ambiguity_payload(dimensional_compute("1 pt + 2 L", "ml"))
    assert {c["id"] for c in payload["tokens"]["pt"]} == {"us_pint", "imperial_pint"}
    assert payload["rejected"][0]["assume"] == {"pt": "typographic_point"}
    assert "Dimensional Mismatch" in payload["rejected"][0]["reason"]


def test_no_valid_interpretation_is_a_type_error():
    res = dimensional_compute("5 C + 3 kg", "kg")
    assert res.startswith("Type Error: No interpretation of ambiguous unit(s) 'C'")


def test_too_many_ambiguous_tokens_is_rejected():
    res = dimensional_compute("1 ton + 1 gal + 1 qt + 1 pint + 1 hp", "kg")
    assert res.startswith("Parsing Error: Too many distinct ambiguous units")


def test_overlong_expression_still_hits_the_length_guard():
    res = dimensional_compute("1 m + " * 100 + "1 m", "m")
    assert res.startswith("Parsing Error: Expression exceeds maximum")


# --- Hard bindings: assume and session defaults ---

def test_assume_settles_ambiguity_without_a_note():
    res = dimensional_compute("1 ton", "kg", assume={"ton": "long_ton"})
    assert res == "Result: 1016.05 kilogram"


def test_assume_is_never_overridden_by_context():
    res = dimensional_compute("12 pt + 2 inch", "mm", assume={"pt": "us_pint"})
    assert res.startswith("Type Error: Dimensional Mismatch")


@pytest.mark.parametrize("assume, fragment", [
    ({"tun": "long_ton"}, "'tun' is not an ambiguous unit symbol"),
    ({"ton": "heavy_ton"}, "'heavy_ton' is not a candidate for 'ton'"),
])
def test_invalid_assume_is_an_assumption_error(assume, fragment):
    res = dimensional_compute("1 ton", "kg", assume=assume)
    assert res.startswith("Assumption Error:") and fragment in res


def test_session_default_applies_to_later_calls_and_is_reported():
    assert "Session default set: ton = metric_ton" in set_unit_default("ton", "metric_ton")
    res = dimensional_compute("1 ton", "kg")
    assert res.startswith("Result: 1000 kilogram")
    assert "ton = metric_ton (session binding)" in res


def test_assume_beats_session_default():
    set_unit_default("ton", "metric_ton")
    assert dimensional_compute("1 ton", "kg", assume={"ton": "short_ton"}) == "Result: 907.185 kilogram"


def test_set_unit_default_rejects_unknown_candidates():
    assert set_unit_default("ton", "nope").startswith("Assumption Error:")


# --- Soft preferences: config defaults and profile ---

def test_config_default_breaks_ties(monkeypatch):
    use_config(monkeypatch, defaults={"ton": "short_ton"})
    res = dimensional_compute("1 ton", "kg")
    assert res.startswith("Result: 907.185 kilogram") and "configured default" in res


def test_profile_breaks_ties(monkeypatch):
    use_config(monkeypatch, profile="metric")
    res = dimensional_compute("1 ton", "kg")
    assert res.startswith("Result: 1000 kilogram") and "'metric' profile" in res


def test_config_default_beats_profile(monkeypatch):
    use_config(monkeypatch, profile="metric", defaults={"ton": "long_ton"})
    assert dimensional_compute("1 ton", "kg").startswith("Result: 1016.05 kilogram")


def test_default_never_overrides_what_context_forces(monkeypatch):
    use_config(monkeypatch, defaults={"pt": "us_pint"})
    res = dimensional_compute("12 pt + 2 inch", "mm")
    assert res.startswith("Result: 55.0333 millimeter")
    assert "only interpretation consistent" in res


def test_profile_does_not_pick_fluid_ounce_for_a_bare_oz(monkeypatch):
    use_config(monkeypatch, profile="us")
    payload = ambiguity_payload(dimensional_compute("1 oz", "oz"))
    assert {c["id"] for c in payload["tokens"]["oz"]} == {"ounce", "us_fluid_ounce"}


def test_profile_with_no_matching_candidate_leaves_ambiguity(monkeypatch):
    use_config(monkeypatch, profile="us")
    payload = ambiguity_payload(dimensional_compute("1 hp", "W"))
    assert {c["id"] for c in payload["tokens"]["hp"]} == {"mechanical_horsepower", "metric_horsepower"}


def test_default_for_a_candidate_context_rejected_is_ignored(monkeypatch):
    use_config(monkeypatch, defaults={"oz": "ounce"})
    res = dimensional_compute("1 oz", "ml")
    assert ambiguity_payload(res)["tokens"]["oz"]


# --- Unambiguous spellings ---

@pytest.mark.parametrize("expr, target, expected", [
    ("20 °C", "degF", "Result: 68 degree_Fahrenheit"),
    ("68 °F", "°C", "Result: 20 degree_Celsius"),
    ("491.67 R", "K", "Result: 273.15 kelvin"),
    ("491.67 °R", "K", "Result: 273.15 kelvin"),
    ("1 Cal", "kcal", "Result: 1 kilocalorie"),
    ("1 us_gallon", "L", "Result: 3.78541 liter"),
    ("1 imperial_gallon", "L", "Result: 4.54609 liter"),
])
def test_explicit_spellings_never_ambiguous(expr, target, expected):
    assert dimensional_compute(expr, target) == expected


def test_unaffected_expressions_take_the_plain_path():
    assert dimensional_compute("10 m/s * 5 s", "m") == "Result: 50 meter"
    assert dimensional_compute("1e5 m", "km") == "Result: 100 kilometer"


# --- Registry and resource ---

def test_registry_resource_lists_candidates_with_dimensions():
    listing = json.loads(list_ambiguous_units())
    assert set(listing) == set(AMBIGUOUS)
    pt = {c["id"]: c for c in listing["pt"]}
    assert pt["typographic_point"]["dimension"] == "[length]"
    assert pt["us_pint"]["dimension"] == "[length] ** 3"
    assert registry_listing() == listing


def test_find_candidate_errors():
    assert find_candidate("pt", "us_pint").unit == "pint"
    with pytest.raises(AssumptionError):
        find_candidate("zzz", "x")


def write_config(tmp_path, monkeypatch, text):
    path = tmp_path / "config.toml"
    path.write_text(text)
    monkeypatch.setenv("SKOOKUM_CONFIG", str(path))
    return path


def test_bad_config_surfaces_as_a_tool_error(tmp_path, monkeypatch):
    write_config(tmp_path, monkeypatch, 'profile = "martian"')
    monkeypatch.setattr(server, "_config", None)
    assert dimensional_compute("1 ton", "kg").startswith("Config Error:")


def test_config_is_loaded_once_and_cached(tmp_path, monkeypatch):
    write_config(tmp_path, monkeypatch, 'profile = "metric"')
    monkeypatch.setattr(server, "_config", None)
    assert server._get_config().profile == "metric"
    (tmp_path / "config.toml").write_text('profile = "us"')
    assert server._get_config().profile == "metric"



# --- Mixed hard-bound and inferred symbols ---

def test_assume_one_symbol_and_infer_another():
    res = dimensional_compute("1 ton + 1 oz", "kg", assume={"ton": "long_ton"})
    assert res.startswith("Result: 1016.08 kilogram")
    assert "oz = ounce" in res and "ton" not in res.split("Assumptions:")[1]


def test_session_default_for_one_symbol_and_infer_another():
    set_unit_default("ton", "metric_ton")
    res = dimensional_compute("1 ton + 1 oz", "kg")
    assert "ton = metric_ton (session binding)" in res and "oz = ounce" in res
