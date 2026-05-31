import ast
import re
from typing import Any, Union, cast
from sympy import Rational, pi, E
from .types import Quantity, Unit, Dimensionless

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
        ast.Constant,  # Python 3.8+
        ast.Num,       # Deprecated but kept for older Python versions
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
    }

    # Safe mathematical operators
    SAFE_OPERATORS = {
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
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

def preprocess_expression(expr: str) -> str:
    """
    Normalizes natural phrasing and implicit syntax into standard mathematical format.
    Tolerates 'per', spacing variations, and implicit multiplications (e.g. '10m' -> '10 * m').
    """
    # Normalize spacing
    expr = expr.strip()
    
    # Map caret ^ to ** for exponentiation
    expr = expr.replace('^', '**')
    
    # Map standard Unicode symbols to ASCII equivalents (ADR 0003)
    unicode_map = {
        'π': 'pi',
        'Ω': 'ohm',
        'μ': 'micro'
    }
    for uni, asc in unicode_map.items():
        expr = expr.replace(uni, asc)
        
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
    expr = re.sub(r'(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*([a-zA-Z_\[(])', r'\1 * \2', expr)
    
    # Handle implicit multiplication between closing and opening brackets or words
    # e.g. "(10m)(5s)" -> "(10m) * (5s)"
    expr = re.sub(r'\)\s*([a-zA-Z_\d\[(])', r') * \1', expr)
    
    return expr

def _evaluate_ast_node(node: ast.AST) -> Union[Rational, Quantity[Any]]:
    """Recursively evaluates an AST node using SymPy and custom Quantity classes securely."""
    if isinstance(node, ast.Expression):
        return _evaluate_ast_node(node.body)

    elif isinstance(node, (ast.Constant, ast.Num)):
        val = node.value if isinstance(node, ast.Constant) else node.n
        return Rational(str(val))

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
        operand = _evaluate_ast_node(node.operand)
        if isinstance(node.op, ast.UAdd):
            return operand
        return -operand  # _SafeASTVisitor guarantees op is USub if it's not UAdd

    else:
        # Must be ast.BinOp because _SafeASTVisitor strictly whitelists these classes
        node = cast(ast.BinOp, node)
        left = _evaluate_ast_node(node.left)
        right = _evaluate_ast_node(node.right)

        op = node.op
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
            
            if isinstance(left, Quantity):
                new_card = {k: v * int(exponent) for k, v in left.unit.cardinality.items()}
                new_scale = left.unit.scale_factor ** exponent
                new_name = f"{left.unit.name} ** {exponent}"
                return Quantity(left.expressed_value ** exponent, Unit(new_name, new_card, new_scale))
            else:
                return left ** exponent

def parse_and_evaluate(expression: str) -> Union[Rational, Quantity[Any]]:
    """
    Parses, sandboxes, and evaluates an expression string.
    Raises SecurityError or ExpressionParsingError if unsafe or grammatically invalid.
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

    preprocessed = preprocess_expression(expression)
    try:
        tree = ast.parse(preprocessed, mode='eval')
    except SyntaxError as e:
        raise ExpressionParsingError(f"Syntax error in expression: {e}")

    # Enforce AST safety whitelist
    visitor = _SafeASTVisitor()
    visitor.visit(tree)

    # Secure evaluation
    result = _evaluate_ast_node(tree)
    if isinstance(result, Unit):
        return Quantity(1, result)
    return result
