# Skookum MCP: System Design Reference

This document serves as the official system design and architectural blueprint for **Skookum MCP** (`skookum-mcp`). It maps out the exact sequence of data flow, details the preprocessor translation grammar, specifies the AST sandbox whitelist, and explains the mathematical calculations governing physical scale conversions.

---

## 1. System Architecture & Call Flow Pipeline

When an AI Agent makes a tool call via the Model Context Protocol (Stdio transport) or a human developer submits a query through the Companion Dashboard (HTTP REST boundary), data flows sequentially through the decoupled modules:

```
[Agent Client]             [Dashboard Client]
      │                            │
      ▼ (JSON-RPC tool/call)       ▼ (HTTP POST /api/compute)
┌────────────────────────────────────────────────────────┐
│             src/server.py: MCP Server Boundary         │
└───────────────────────────┬────────────────────────────┘
                            │ (dimensional_compute)
                            ▼
┌────────────────────────────────────────────────────────┐
│             src/parser.py: AST Sandbox Parser          │
│                                                        │
│  1. Preprocessor (Syntax & Unicode normalization)      │
│  2. AST parsing (ast.parse)                            │
│  3. AST Visitor Whitelist (RCE-safe Node check)        │
│  4. AST Recursive Evaluation                           │
└───────────────────────────┬────────────────────────────┘
                            │ (Quantity instantiation)
                            ▼
┌────────────────────────────────────────────────────────┐
│             src/types.py: Quantity Value Object        │
│                                                        │
│  - Query SI scale factor and coordinate offset         │
│  - Compute internal base value:                        │
│    base_val = expressed_val * factor + offset          │
└───────────────────────────┬────────────────────────────┘
                            │ (target unit conversion)
                            ▼
┌────────────────────────────────────────────────────────┐
│             src/engine.py: Converter Seam              │
│                                                        │
│  - Match exponent cardinality vectors                  │
│  - Perform standard scale conversion:                  │
│    target_val = (base_val - target_offset) / target_sf │
│  - Detect and solve reciprocal inversions             │
└───────────────────────────┬────────────────────────────┘
                            │ (formatted tool output)
                            ▼
                  [ Plaintext Result ]
```

---

## 2. Preprocessor Normalization Grammar

Before a dynamic physical expression string is compiled into a Python Abstract Syntax Tree (AST), `preprocess_expression` in `src/parser.py` normalizes messy, natural engineering shorthand into standard mathematical grammar.

The preprocessor executes five sequential normalizations:

1.  **Approximation Indicator Stripping**: Removes approximation tilde signs (`~`) from numbers or operations (e.g. `~10 m` $\to$ `10 m`, `5 m + ~2 m` $\to$ `5 m + 2 m`).
2.  **Percentage Conversion**: Safely translates percentage signs `%` to `* percent` to route them as dimensionless scalar divisions.
3.  **Division Synonym Mapping**: Maps the engineering term `per` to standard division slashes `/` (e.g. `meter per second` $\to$ `meter / second`).
4.  **Implicit Multiplication Injection**: Automatically inserts explicit multiplication operators `*` between adjacent numbers and word boundaries or brackets (e.g. `10m` $\to$ `10 * m`, `5.5(s)` $\to$ `5.5 * (s)`), while preserving scientific notation (`1e-5`).
5.  **Unicode Symbol Translation**: Automatically normalizes user-friendly Unicode math and unit characters to ASCII canonical names (e.g. `π` $\to$ `pi`, `Ω` $\to$ `ohm`, `μ` $\to$ `micro`).

---

## 3. AST Sandbox Specifications & Whitelist

To eliminate Remote Code Execution (RCE) and attributes leakage, the `_SafeASTVisitor` in `src/parser.py` completely replaces dangerous `eval()` blocks by validating every node in the compiled AST against a strict, whitelisted grammar:

### Allowed AST Nodes:
*   **Structure**: `ast.Expression` (ensures only single expressions are evaluated, blocking statement blocks, loops, or variable assignments).
*   **Arithmetic Binary Operations**: `ast.BinOp` (restricted strictly to operators: `ast.Add`, `ast.Sub`, `ast.Mult`, `ast.Div`, `ast.Pow`).
*   **Unary Signs**: `ast.UnaryOp` (restricted to signs: `ast.UAdd`, `ast.USub`).
*   **Constants**: `ast.Constant` / `ast.Num` (allows raw numerical values).
*   **Variables & Lookups**: `ast.Name`, `ast.Load` (restricted strictly to verified, registered unit abbreviations or mathematical constants `pi` and `E`).

### Explicit Security Guards:
*   **Attribute Blocker**: Any Name or attribute containing leading underscores (`_`) immediately triggers a `SecurityError` to prevent private namespace access.
*   **Bitwise Caret Handler**: In standard Python grammar, `^` represents the bitwise XOR operator (`ast.BitXor`). To prevent bitwise injection vectors, bitwise operators are completely excluded from the whitelist. All caret characters `^` are converted to standard power symbols `**` during preprocessing before AST compilation occurs.

---

## 4. Quantity SI-Base Scaling Math

Every physical measurement is represented in `src/types.py` by an immutable `Quantity` value object. Upon instantiation, the object parses its magnitude using SymPy `Rational` exact math and immediately translates it into standard SI-Base units (meters, kilograms, seconds, etc.) internally. 

This internal base value is computed by querying the Converter's `resolve_unit` registry:

$$\text{value}_{internal} = (\text{value}_{expressed} \times \text{scale\_factor}) + \text{offset}$$

*   **Linear Units (e.g., Length, Mass, Force)**: Have an offset of `0`. The internal base value is a simple linear scale factor multiplication.
*   **Offset Scale Coordinates (e.g., Absolute Temperatures)**: Have non-zero coordinate offsets (e.g., Celsius has an offset of `273.15` relative to Kelvin). Paired with the unit's base scale factor, this maps the coordinate precisely into absolute base units (Kelvin).

When returning the value to the caller in its expressed form, the offset is reversed:

$$\text{value}_{expressed} = \frac{\text{value}_{internal} - \text{offset}}{\text{scale\_factor}}$$

---

## 5. Converter Resolution & Reciprocal Logic

The **Converter** seam (`src/engine.py`) performs two primary physical validations during a conversion call:

### Exponent Cardinality Comparison
The converter validates that the starting unit and the target unit share identical dimensional exponent vectors:

$$\mathbf{v}_{start} \equiv \mathbf{v}_{target}$$

If the exponent vectors mismatch, the conversion is rejected with a `TypeError`.

### Reciprocal Inversion Solver
If the exponent vectors are not equal but sum key-by-key to exactly zero:

$$\mathbf{v}_{start} + \mathbf{v}_{target} = \mathbf{0}$$

The converter identifies this as a reciprocal physical relationship (e.g. `Miles Per Gallon` ($L^{-1}$) vs `Liters per Kilometer` ($L^1$)). The solver automatically performs an algebraic reciprocal inversion:

1.  Calculates the exact rational reciprocal of the starting Quantity's value:
    $$\text{value}_{inv} = \frac{1}{\text{value}_{internal}}$$
2.  Resolves an intermediate, inverted unit mapping.
3.  Performs standard linear scale matching to output the correct target unit quantity, preserving mathematical identity and avoiding decimal rounding drift.
