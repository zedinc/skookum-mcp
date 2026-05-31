# Represent Dimensions Statically and Cardinalities Algebraically

To achieve sophisticated static type enforcement in IDEs while allowing dynamic algebraic operations at runtime, we have decided to represent physical dimensions in two distinct forms:
1. **Dimension (Type Tag):** A semantic compile-time generic parameter (e.g., `Length`, `Mass`, `Force`) used on `Unit[T_Dim]` and `Quantity[T_Dim]` to let static checkers (like mypy/Pyright) verify dimension compatibility during development.
2. **Cardinality (Runtime Vector):** An algebraic dictionary (TypedDict of exponents across the 7 fundamental quantities) used at runtime to calculate dimensions and execute explicit key-by-key exponent addition or subtraction during arithmetic operations, completely decoupled from Pint.
