import ast
import re
from typing import Any, Optional, Union, cast
from sympy import Rational, pi, E
from .types import Quantity, Unit, Dimensionless
from .affine import prepare_multiplicative, prepare_power_base
from .juxtaposition import rewrite_juxtaposition
from .readings import ReadingContext

class SecurityError(Exception):
    """Exception raised when an expression fails AST security validation."""
    pass

class ExpressionParsingError(Exception):
    """Exception raised when an expression fails syntax parsing or is mathematically ambiguous."""
    pass

class _SafeASTVisitor(ast.NodeVisitor):
    """
    AST visitor that enforces a strict whitelist of safe nodes
    to prevent Remote Code Execution (RCE).
    """
    # Safe AST node types
    SAFE_NODES = {
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Name,
        ast.Load,
        # Allow operator nodes during general visiting
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.UAdd,
        ast.USub,
        ast.MatMult,  # internal juxtaposition marker; user-typed '@' is rejected up front
    }

    # Safe mathematical operators
    SAFE_OPERATORS = {
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.MatMult,
        ast.Pow,
        ast.UAdd,
        ast.USub,
    }

    def __init__(self):
        super().__init__()

    def visit(self, node: ast.AST) -> None:
        node_class = type(node)
        if node_class not in self.SAFE_NODES:
            raise SecurityError(f"Unauthorized operation '{node_class.__name__}' detected in expression.")

        if isinstance(node, ast.BinOp):
            op_class = type(node.op)
            if op_class not in self.SAFE_OPERATORS:
                raise SecurityError(f"Unauthorized binary operator '{op_class.__name__}' detected.")
        elif isinstance(node, ast.UnaryOp):
            op_class = type(node.op)
            if op_class not in self.SAFE_OPERATORS:
                raise SecurityError(f"Unauthorized unary operator '{op_class.__name__}' detected.")

        super().visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        name_id = node.id
        # Prevent accessing private properties or builtins via underscores
        if name_id.startswith('_'):
            raise SecurityError(f"Unauthorized name '{name_id}' starting with underscore.")
            
        if name_id in {"pi", "E"}:
            return
            
        try:
            from .engine import resolve_unit
            resolve_unit(name_id)
            return
        except Exception:
            raise ExpressionParsingError(f"Unrecognized unit or symbol '{name_id}' in expression.")

# Longest first, so degree-scale symbols win over any bare-symbol mapping
UNICODE_MAP = {
    '°C': 'degC',
    '℃': 'degC',
    '°F': 'degF',
    '℉': 'degF',
    '°R': 'degR',
    'π': 'pi',
    'Ω': 'ohm',
    'μ': 'micro',
}

def normalize_unicode_symbols(text: str) -> str:
    """Maps Unicode math/unit symbols to their ASCII canonical names (ADR 0003)."""
    for uni, asc in UNICODE_MAP.items():
        text = text.replace(uni, asc)
    return text

def preprocess_expression(expr: str, mark: bool = False) -> str:
    """
    Normalizes natural phrasing and implicit syntax into standard mathematical format.
    Tolerates 'per', spacing variations, and implicit multiplications (e.g. '10m' -> '10 * m').
    With `mark=True` the implicit multiplications are emitted as '@' so adjacency survives (ADR 0006).
    """
    joiner = ' @ ' if mark else ' * '
    # Normalize spacing
    expr = expr.strip()
    
    # Map caret ^ to ** for exponentiation
    expr = expr.replace('^', '**')
    
    # Map standard Unicode symbols to ASCII equivalents (ADR 0003)
    expr = normalize_unicode_symbols(expr)

    # Map common unit synonyms
    expr = re.sub(r'\bmpg\b', 'mile / gallon', expr, flags=re.IGNORECASE)
    expr = re.sub(r'\bl/100km\b', 'liter / (100 * kilometer)', expr, flags=re.IGNORECASE)
    
    # Strip leading '~' (approximation indicator) before numbers or spaces
    expr = re.sub(r'^\s*~', '', expr)
    # Also strip '~' when used after an operator, e.g. "10 m + ~5 m" -> "10 m + 5 m"
    expr = re.sub(r'([-+*/(])\s*~', r'\1', expr)
    
    # Map percentage sign % to * percent
    expr = re.sub(r'\s*%', ' * percent', expr)
    
    # Replace "per" division synonym with "/"
    expr = re.sub(r'\bper\b', '/', expr)
    
    # Insert explicit multiplication between numbers and words/brackets:
    # e.g., "10m" -> "10 * m", "5.5(s)" -> "5.5 * (s)"
    # Avoids breaking scientific notation (like 1e-5) by matching digits
    # followed by word chars or brackets
    expr = re.sub(r'(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*([a-zA-Z_\[(])', lambda m: m.group(1) + joiner + m.group(2), expr)
    
    # Handle implicit multiplication between closing and opening brackets or words
    # e.g. "(10m)(5s)" -> "(10m) * (5s)"
    expr = re.sub(r'\)\s*([a-zA-Z_\d\[(])', lambda m: ')' + joiner + m.group(1), expr)

    # `in` (inch) is a Python keyword and would fail ast.parse; run last so `2in` has become `2 * in`
    expr = re.sub(r'\bin\b', 'inch', expr)

    return expr

# Resource-exhaustion guards for exponentiation (the AST whitelist cannot stop `9**9**9`)
MAX_EXPONENT = 1000
MAX_RESULT_BITS = 1_000_000

def _check_pow_bounds(base: Any, exponent: Any) -> None:
    """Rejects exponentiations whose exponent or exact-rational result size would exhaust resources."""
    exp_mag = abs(float(exponent))
    if exp_mag > MAX_EXPONENT:
        raise ExpressionParsingError(f"Exponent magnitude exceeds limit of {MAX_EXPONENT}.")
    if isinstance(base, Rational) and base.is_Rational:
        if (base.p.bit_length() + base.q.bit_length()) * exp_mag > MAX_RESULT_BITS:
            raise ExpressionParsingError("Result of exponentiation exceeds the maximum allowed size.")

def _evaluate_ast_node(node: ast.AST, kinds: ReadingContext) -> Union[Rational, Quantity[Any]]:
    """Recursively evaluates an AST node using SymPy and custom Quantity classes securely."""
    if isinstance(node, ast.Expression):
        return _evaluate_ast_node(node.body, kinds)

    elif isinstance(node, ast.Constant):
        return Rational(str(node.value))

    elif isinstance(node, ast.Name):
        name_id = node.id
        from .engine import resolve_unit
        if name_id == "pi":
            u = resolve_unit("dimensionless")
            return Quantity(pi, u)
        elif name_id == "E":
            u = resolve_unit("dimensionless")
            return Quantity(E, u)
        else:
            return resolve_unit(name_id)

    elif isinstance(node, ast.UnaryOp):
        operand = _evaluate_ast_node(node.operand, kinds)
        if isinstance(node.op, ast.UAdd):
            return operand
        return -operand  # _SafeASTVisitor guarantees op is USub if it's not UAdd

    else:
        # Must be ast.BinOp because _SafeASTVisitor strictly whitelists these classes
        node = cast(ast.BinOp, node)
        left = _evaluate_ast_node(node.left, kinds)
        right = _evaluate_ast_node(node.right, kinds)

        op = node.op
        if isinstance(op, (ast.Mult, ast.Div)):
            left, right = prepare_multiplicative(left, right, node.left, node.right, kinds)
        if isinstance(op, ast.Add):
            return left + right
        elif isinstance(op, ast.Sub):
            return left - right
        elif isinstance(op, ast.Mult):
            return left * right
        elif isinstance(op, ast.Div):
            # Safe division check
            if right == 0 or (isinstance(right, Quantity) and right.value == 0):
                raise ZeroDivisionError("Nonsense: Division by zero.")
            return left / right
        else:
            # Must be ast.Pow because _SafeASTVisitor whitelists only Add, Sub, Mult, Div, Pow
            if isinstance(right, Quantity):
                if right.dimensionality != "dimensionless":
                    raise TypeError("Nonsense: Exponents must be dimensionless.")
                exponent = right.value
            else:
                exponent = right
            
            left = prepare_power_base(left, node.left, kinds)
            _check_pow_bounds(left.expressed_value if isinstance(left, Quantity) else left, exponent)
            if isinstance(left, Quantity):
                new_card = {k: v * int(exponent) for k, v in left.unit.cardinality.items()}
                new_scale = left.unit.scale_factor ** exponent
                new_name = f"{left.unit.name} ** {exponent}"
                return Quantity(left.expressed_value ** exponent, Unit(new_name, new_card, new_scale))
            else:
                return left ** exponent

def prepare_expression(expression: str) -> str:
    """
    Validates complexity limits and preprocesses an expression once, marking implicit multiplications with '@'
    (ADR 0006). A user-typed '@' is rejected here, so the marker cannot be forged.
    """
    # Upfront DoS validation complexity guards
    if len(expression) > 500:
        raise ExpressionParsingError("Expression exceeds maximum allowed length of 500 characters.")

    depth = 0
    for char in expression:
        if char == '(':
            depth += 1
            if depth > 20:
                raise ExpressionParsingError("Expression nesting depth exceeds limit of 20.")
        elif char == ')':
            depth -= 1

    if '@' in expression:
        raise SecurityError("Unauthorized binary operator 'MatMult' detected.")
    return preprocess_expression(expression, mark=True)

def parse_and_evaluate(expression: str, kinds: Optional[ReadingContext] = None, _prepared: bool = False) -> Union[Rational, Quantity[Any]]:
    """
    Parses, sandboxes, and evaluates an expression string.
    Raises SecurityError or ExpressionParsingError if unsafe or grammatically invalid.
    `kinds` carries the recorded reading decisions for ambiguous expressions (ADR 0005, ADR 0006).
    `_prepared` is for internal callers that already ran `prepare_expression`.
    """
    preprocessed = expression if _prepared else prepare_expression(expression)
    try:
        tree = ast.parse(preprocessed, mode='eval')
    except SyntaxError as e:
        raise ExpressionParsingError(f"Syntax error in expression: {e}")

    # Enforce AST safety whitelist
    visitor = _SafeASTVisitor()
    visitor.visit(tree)

    # Bind number-unit juxtaposition into quantity literals, then evaluate securely
    kinds = kinds or ReadingContext()
    tree = rewrite_juxtaposition(tree, kinds)
    result = _evaluate_ast_node(tree, kinds)
    if isinstance(result, Unit):
        return Quantity(1, result)
    return result
