# Skookum MCP Context

This context is responsible for representing physical measurements, validating their algebraic dimensions, and securely converting them across compatible measurement scales.

## Language

**Dimension**:
The semantic, compile-time classification of physical nature (e.g., Length, Mass, Force). Used as a generic type tag for static analysis.
_Avoid_: Dimension string, physical property

**Cardinality**:
The runtime algebraic representation of a **Dimension**, modeled as an integer exponent vector of the 7 fundamental physical quantities: Length (L), Mass (M), Time (T), Temperature (Theta), Electric Current (I), Amount of Substance (N), and Luminous Intensity (J).
_Avoid_: Exponent dictionary, dimension vector

**Unit**:
A standardized physical scale of measurement whose **Dimension** and associated **Cardinality** are inherently embedded within its definition.
_Avoid_: Symbol, abbreviation

**Quantity**:
A physical measurement. A Quantity gets its dimensionality directly from its associated **Unit**. Quantities can be scalar or vector:
- **Scalar Quantity**: A Quantity defined strictly by a numerical magnitude and an associated **Unit**.
- **Vector Quantity**: A Quantity defined by a **Scalar Quantity** associated with a direction (unit vector).
_Avoid_: Measurement, coordinate

**Ambiguous Symbol**:
A unit symbol with more than one common meaning (e.g. `pt`, `C`, `ton`). Each meaning is a **Candidate** with a stable id (e.g. `typographic_point`). Resolved by explicit binding, then context, then user defaults (ADR 0004).
_Avoid_: Alias, synonym

**Profile**:
A named preference (`us`, `imperial`, `metric`) in the user config that breaks ties between Candidates the context cannot separate.
_Avoid_: Locale, region

**Point / Interval**:
A temperature is either a point on a scale (a reading: 20 degC) or an interval (a difference: 5 delta_degC). The unit alone does not say which; the expression does (ADR 0005). Only offset-scale units (degC, degF) cannot be scaled as points, so they are converted to their zero-based scale (K, degR) before multiplying.
_Avoid_: Absolute/relative temperature

**Converter**:
The domain module responsible for translating a physical Quantity into a target Unit of mathematically compatible dimensions.
_Avoid_: Calculator, engine, translator

**Co-processor**:
The headless, deterministic MCP server role that executes secure physical calculations to shield AI agents from dimensional reasoning hallucinations.
_Avoid_: Host interpreter, un-sandboxed math tool

**AST Sandbox**:
The security boundary that parses, validates, and safely executes dynamic mathematical expressions against a strict whitelist of AST node types to mitigate RCE and injection vectors.
_Avoid_: Dangerous `eval()` paths

## Acronyms

**RCE (Remote Code Execution)**:
A high-severity vulnerability class where an attacker executes arbitrary code on a host machine. In agent workflows, this frequently occurs when untrusted user strings are evaluated directly in un-sandboxed runtime interpreters.
_Avoid_: Local crash, client bypass

**MCP (Model Context Protocol)**:
An open-standard integration protocol designed to securely connect AI models to local data sources, APIs, and computational tools.
_Avoid_: Local plugin framework, tool wrapper

**AST (Abstract Syntax Tree)**:
A tree representation of the syntactic structure of source code. In Skookum MCP, the AST represents the structure of algebraic physics equations, allowing safe node validation before math evaluation.
_Avoid_: String parser, code block

**SI (Système International)**:
The modern standard metric system of physical units, built upon 7 fundamental base dimensions (Length, Mass, Time, Temperature, Electric Current, Substance Amount, Luminous Intensity) that serve as Skookum MCP's algebraic dimensionality coordinates.
_Avoid_: Base unit, raw scale

