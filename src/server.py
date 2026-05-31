import json
from mcp.server.fastmcp import FastMCP
from .types import Quantity, Unit, MathematicalError
from .parser import parse_and_evaluate, SecurityError, ExpressionParsingError
from .engine import convert_quantity, resolve_unit

# Initialize FastMCP Server
mcp = FastMCP("Skookum MCP Server")

@mcp.tool()
def dimensional_compute(expression: str, target_unit: str) -> str:
    """
    Evaluates algebraic expressions involving physical units and converts the result to a target unit.
    
    Args:
        expression: The algebraic physics expression to evaluate (e.g. '10 m/s * 5 s', '(30 degC - 10 degC) + 5 delta_degC').
                    Tolerates space variations, 'per', and implicit multiplications (e.g. '10m').
        target_unit: The target unit abbreviation to convert the final result into (e.g. 'ft', 'delta_degC', 'km/h').
        
    Returns:
        A formatted string with the exact rational result and a floating-point decimal approximation.
        If the calculation is invalid or insecure, returns a detailed educational error message.
    """
    try:
        # 1. Parse and evaluate expression safely via AST sandbox
        evaluated_qty = parse_and_evaluate(expression)
        
        # 2. Handle pure dimensionless numbers
        if not isinstance(evaluated_qty, Quantity):
            qty = Quantity(evaluated_qty, resolve_unit("dimensionless"))
        else:
            qty = evaluated_qty
            
        # 3. Perform conversion (handles linear, temperatures, and reciprocal inversions)
        target_u = resolve_unit(target_unit)
        result = convert_quantity(qty, target_u)
        
        # 4. Format output with exact SymPy fraction and float approximation
        float_approx = float(result.expressed_value)
        return (
            f"Result: {result.expressed_value} {result.unit_name} "
            f"(approx. {float_approx:.6g} {result.unit_name})"
        )
        
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
