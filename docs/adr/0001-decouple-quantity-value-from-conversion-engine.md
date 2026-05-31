# Decouple Quantity Value from Conversion Engine

We have decided to decouple the representation of physical measurements (`Quantity` value object) from the algorithms that translate them (`Converter` module). `Quantity` will act as a pure, immutable value representation that is entirely unaware of the Unit Registry or Pint dependencies, while the `Converter` module handles all conversion, thermodynamic offset, and reciprocal solvers behind a deep, dedicated seam. This ensures that adding new physical solvers does not pollute our core type representation and maintains high test locality.
