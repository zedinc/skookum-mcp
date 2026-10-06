import json
from typing import Dict, Optional
from mcp.server.fastmcp import FastMCP
from .types import Quantity, Unit, MathematicalError
from .parser import parse_and_evaluate, SecurityError, ExpressionParsingError
from .engine import convert_quantity, resolve_unit
from .ambiguity import AmbiguousUnitError, AssumptionError, find_candidate, registry_listing, resolve_ambiguities
from .config import Config, ConfigError, load_config

# Initialize FastMCP Server
mcp = FastMCP("Skookum MCP Server")

# Per-process state: the config is read once (never written); session defaults live only in memory
_config: Optional[Config] = None
_session_defaults: Dict[str, str] = {}


def _get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def _evaluate(expression: str, target_unit: str) -> str:
    """Parses, evaluates and converts one fully-specified expression, returning 'value unit'."""
    # 1. Parse and evaluate expression safely via AST sandbox
    evaluated_qty = parse_and_evaluate(expression)

    # 2. Handle pure dimensionless numbers
    if not isinstance(evaluated_qty, Quantity):
        qty = Quantity(evaluated_qty, resolve_unit("dimensionless"))
    else:
        qty = evaluated_qty

    # 3. Perform conversion (handles linear, temperatures, and reciprocal inversions)
    result = convert_quantity(qty, resolve_unit(target_unit))

    # 4. Format output as a decimal to 6 significant figures
    return f"{float(result.expressed_value):.6g} {result.unit_name}"

@mcp.tool()
def dimensional_compute(expression: str, target_unit: str, assume: Optional[Dict[str, str]] = None) -> str:
    """
    Evaluates algebraic expressions involving physical units and converts the result to a target unit.
    
    Args:
        expression: The algebraic physics expression to evaluate (e.g. '10 m/s * 5 s', '(30 degC - 10 degC) + 5 delta_degC').
                    Tolerates space variations, 'per', and implicit multiplications (e.g. '10m').
        target_unit: The target unit abbreviation to convert the final result into (e.g. 'ft', 'delta_degC', 'km/h').
        assume: Optional explicit meanings for ambiguous unit symbols, e.g. {"pt": "typographic_point"}.
                Symbols like pt, C, F, ton, gal, oz are resolved from context when only one meaning is
                dimensionally valid; otherwise an 'Ambiguous Unit' response lists the options (see the
                units://ambiguous resource) and this argument settles it.
        
    Returns:
        'Result: <value> <unit>' with the value to 6 significant figures, plus an 'Assumptions:' line if
        any ambiguous symbol was resolved for you. If the calculation is invalid or insecure, returns a
        detailed educational error message.
    """
    try:
        config = _get_config()
        resolution = resolve_ambiguities(
            expression, target_unit, _evaluate,
            assume=assume, session=_session_defaults,
            defaults=config.defaults, profile=config.profile,
        )
        out = f"Result: {resolution.value}"
        if resolution.notes:
            out += "\nAssumptions: " + "; ".join(resolution.notes)
        return out

    except AmbiguousUnitError as e:
        return f"Ambiguous Unit: {e.message}\n{json.dumps(e.payload, indent=2)}"
    except AssumptionError as e:
        return f"Assumption Error: {e}"
    except ConfigError as e:
        return f"Config Error: {e}"
    except SecurityError as e:
        return f"Security Error: {e}"
    except ExpressionParsingError as e:
        return f"Parsing Error: {e}"
    except TypeError as e:
        return f"Type Error: {e}"
    except MathematicalError as e:
        return f"Math Error: {e}"
    except ZeroDivisionError as e:
        return f"Math Error: {e}"
    except Exception as e:
        return f"Error: Unexpected error during evaluation: {e}"

@mcp.tool()
def set_unit_default(symbol: str, candidate: str) -> str:
    """
    Fixes the meaning of an ambiguous unit symbol for the rest of this session (in memory only; the
    config file is never modified). Use it once you have worked out what the document means, e.g.
    set_unit_default("pt", "typographic_point"). See the units://ambiguous resource for options.
    """
    try:
        cand = find_candidate(symbol, candidate)
    except AssumptionError as e:
        return f"Assumption Error: {e}"
    _session_defaults[symbol] = cand.id
    return f"Session default set: {symbol} = {cand.id} ({cand.description})."

@mcp.resource("units://ambiguous")
def list_ambiguous_units() -> str:
    """
    Unit symbols with more than one common meaning, with each candidate's id, unit, physical dimension
    and description. Use the ids with the `assume` argument or set_unit_default.
    """
    return json.dumps(registry_listing(), indent=2)

@mcp.resource("units://supported")
def list_supported_units() -> str:
    """
    Returns a structured list of commonly supported physical units and dimensions.
    Helps the LLM format its unit inputs correctly without hallucinations.
    """
    supported = {
        "length": ["meter (m)", "centimeter (cm)", "millimeter (mm)", "kilometer (km)", "inch (in)", "foot (ft)", "yard (yd)", "mile (mi)"],
        "mass": ["gram (g)", "kilogram (kg)", "milligram (mg)", "pound (lb)", "ounce (oz)"],
        "time": ["second (s)", "minute (min)", "hour (hr)", "day (day)", "year (year)"],
        "temperature": ["kelvin (K)", "rankine (R)", "degree_Celsius (degC)", "degree_Fahrenheit (degF)", "delta_kelvin (delta_kelvin)", "delta_rankine (delta_rankine)", "delta_degree_Celsius (delta_degC)", "delta_degree_Fahrenheit (delta_degF)"],
        "velocity": ["meter/second (m/s)", "kilometer/hour (km/h)", "mile/hour (mph)"],
        "force": ["newton (N)", "dyne (dyn)", "pound_force (lbf)"],
        "energy": ["joule (J)", "calorie (cal)", "BTU (btu)", "watt_hour (Wh)"],
        "power": ["watt (W)", "kilowatt (kW)", "horsepower (hp)"],
        "pressure": ["pascal (Pa)", "bar (bar)", "atmosphere (atm)", "psi (psi)"],
        "dimensionless": ["dimensionless"]
    }
    return json.dumps(supported, indent=2)

@mcp.prompt()
def verify_dimensional_consistency(text: str) -> str:
    """
    Workflow template instructing the LLM to scan a technical text, extract physical formulas,
    and use the dimensional_compute tool to verify their mathematical correctness.
    """
    return f"""
You are an expert physics and engineering validator. Your task is to analyze the following technical document, extract all implicit and explicit physical formulas or mathematical claims, and verify their dimensional and algebraic correctness.

For every physical equation or conversion claim in the text:
1. Extract the algebraic expression and its claimed result unit.
2. Sequentially call the `dimensional_compute` tool to evaluate the expression and convert it to the claimed result unit.
3. Verify if the computed value and unit match the document's claim.
4. Compile a formal validation report. For any discrepancies, explain the physical error (e.g. incorrect scaling factor, adding absolute coordinates, or mismatched dimensions).

Here is the document to analyze:
---
{text}
---
"""

def main():
    mcp.run()

if __name__ == "__main__":
    main()
