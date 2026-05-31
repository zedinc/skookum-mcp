# Product Requirements Document (PRD): Skookum MCP

**Version**: 1.0.0  
**Status**: Approved  
**Core Mission**: *The secure physical units co-processor for AI agents.*

---

## Problem Statement

When AI agents perform engineering, scientific, or mathematical tasks, they frequently need to parse, compute, and convert physical units and equations from technical documents. In doing so, they face two critical operational failure modes:

1.  **Dimensional & Physical Hallucinations**: Standard LLMs are notoriously poor at physical calculations. They routinely hallucinate conversion factors, make physically illegal mathematical steps (e.g. adding `10 m` to `5 kg`), or violate coordinate limits (e.g. adding two absolute temperatures coordinates together).
2.  **Remote Code Execution (RCE) Vulnerabilities**: To evaluate complex user-provided physics expressions, developers frequently resort to Python's built-in `eval()` or un-sandboxed math interpreters on the host system. When exposed to an agent capable of interpreting untrusted user text, this introduces high-severity code injection and host compromise vulnerabilities.

---

## Solution

**Skookum MCP** is a secure, mathematically precise, and self-contained physical unit conversion server and algebraic dimensional calculator. Running locally as a **Model Context Protocol (MCP)** server, it acts as a headless "physics co-processor" for AI agents.

### Core Architecture Pillars:
1.  **RCE-Safe AST Sandbox**: A strict AST (Abstract Syntax Tree) validator that completely replaces dangerous `eval()` blocks, sandboxing execution to whitelisted mathematical nodes.
2.  **Exact SymPy Rational Engine**: All calculations are computed internally as rational fractions to guarantee perfect mathematical identity and prevent floating-point accumulation drift.
3.  **Physical Safety Guards**: Automatically prevents physically impossible operations (such as adding incompatible units like meters and kilograms) by verifying dynamic algebraic exponent vectors across calculations.
4.  **Interactive Agent Self-Healing**: A specialized error boundary that catches math, syntax, or physical errors and returns rich educational guidance directly inside standard tool text outputs, enabling agents to self-heal and correct their formulas on the fly.
5.  **Developer Companion Playground**: A responsive, visual dashboard interface to manually test formulas, inspect fractional steps, and review derivation logs during integration.

---

## Target Audience & Personas

To align our requirements correctly, we distinguish three primary user groups:

*   **The AI Agent**: The primary automated headless caller that needs RCE-safe tool invocations and clear, self-correcting error messages to navigate mathematical workflows autonomously.
*   **The Agent Platform Engineer**: The developer integrating Skookum MCP into agent frameworks (like LangChain, LangGraph, or Google Antigravity SDK) who needs robust local Stdio transport and clear integration examples.
*   **The Human Scientist / Engineer**: The end-user providing physical equations to the agent or using the developer companion playground to visually validate complex derivations.
*   **The QA Engineer / Tester**: The verification specialist who uses the interactive visual playground to manually test boundary conditions, run mathematical regression checks, and validate that physical safety guards are functioning perfectly before system release.

---

## User Stories & Acceptance Criteria

We map out the core product requirements through exhaustive, testable user stories and their respective definition-of-done criteria:

### Category 1: Core Computational Algebra & Unit Solver

#### 1. Implicit Multiplication & Shorthand Notation
*   **User Story**: As an **AI Agent**, I want the parser to support implicit multiplications (e.g. `10m` $\to$ `10 * m`, `5.5(s)` $\to$ `5.5 * (s)`), so that I can easily parse natural physics formulas copied from technical texts without formatting errors.
*   **Acceptance Criteria**:
    *   Expressions like `10 m/s * 5 s` evaluate successfully to a Quantity of `Length` with a value of `50 m`.
    *   Implicit adjacent parenthetical bounds (e.g. `(10m)(5)`) resolve to `50 m`.
    *   Explicit scientific float notation (e.g. `1e-5 m`) is preserved and never split by the implicit multiplication preprocessor.

#### 2. Exponentiation Notation & Syntax Normalization
*   **User Story**: As an **AI Agent**, I want the preprocessor to support standard caretaker symbols `^` for power calculations (e.g. `m/s^2`), so that I do not have to translate all scientific exponent text into Python-specific double-asterisk (`**`) symbols.
*   **Acceptance Criteria**:
    *   The preprocessor automatically converts `^` characters to `**` operators before AST parsing.
    *   Formulas using caret notation (e.g., `10 kg * (5 m/s^2)`) resolve successfully to `50 N`.
    *   Standard Python `**` exponent notation remains fully functional and whitelisted.

#### 3. Percentage and Ratio Scaling
*   **User Story**: As a **Human Scientist**, I want to include percentages (e.g., `5%` or `10m * 5%`) in my calculations, so that I can scale physical quantities with dimensionless ratios easily.
*   **Acceptance Criteria**:
    *   The percentage sign `%` is safely translated to `* percent` during preprocessing.
    *   A percentage multiplication returns a dimensionally identical, scaled Quantity.
    *   Evaluating `100 m * 5%` yields exactly `5 m`.

#### 4. Generalized Reciprocal Solver
*   **User Story**: As a **Human Scientist**, I want to convert directly between inversely related units (e.g., converting fuel efficiency `30 mpg` to fuel consumption `l/100km`), so that reciprocal physics conversions are solved automatically.
*   **Acceptance Criteria**:
    *   The engine dynamically detects when the target unit's dimensionality vector is the exact reciprocal sum of the starting unit's cardinality.
    *   Converting `30 mpg` to `l/100km` outputs the exact mathematically correct rational value (approx. `7.84 l/100km`).
    *   Attempting to calculate a reciprocal on a zero-value quantity (e.g., `1 / (0 m)`) raises a clear, programmatically caught `MathematicalError` indicating that zero has no defined reciprocal.

---

### Category 2: Physical Coordinate & Temperature Safety Guards

#### 5. Affine Temperature Coordinate Shifts
*   **User Story**: As a **Human Scientist**, I want to add or subtract temperature differences to absolute coordinates (e.g. `20 degC + 5 delta_degC`), so that thermodynamic calculations remain physically and algebraically valid.
*   **Acceptance Criteria**:
    *   Adding a relative temperature difference (`delta_degC`, `delta_degF`, `delta_kelvin`, `delta_rankine`) to an absolute temperature coordinate (`degC`, `degF`, `kelvin`, `rankine`) correctly returns a shifted absolute temperature.
    *   Subtracting a relative delta temperature from an absolute coordinate correctly shifts the coordinate downwards.
    *   Operations preserve rational fraction precision internally without introducing float drift.

#### 6. Coordinate Scale Subtraction
*   **User Story**: As a **Human Scientist**, I want to subtract one absolute coordinate from another (e.g. `100 degC - 20 degC`), so that the physical result represents a relative difference (`80 delta_degC`).
*   **Acceptance Criteria**:
    *   Subtracting two compatible absolute temperatures returns a relative delta temperature.
    *   The resulting delta scale matches the starting unit's base factor (Celsius subtraction yields delta Celsius, Fahrenheit yields delta Fahrenheit).

#### 7. Prevention of Physically Infeasible Math
*   **User Story**: As an **Agent Platform Engineer**, I want the units engine to block physically invalid temperature operations (e.g. adding two absolute coordinates like `20 degC + 20 degC`, or negating/scaling absolute coordinates), so that nonsense physical calculations are caught immediately.
*   **Acceptance Criteria**:
    *   Adding two absolute temperature quantities raises a clear `TypeError` explaining that coordinate addition is invalid.
    *   Negating or multiplying absolute coordinates raises a `TypeError` (unless scaling by a dimensionless value of exactly `1`).

---

### Category 3: RCE-Safe AST Sandbox

#### 8. Safe AST-Based Parsing Whitelist
*   **User Story**: As an **Agent Platform Engineer**, I want the parser to block all non-whitelisted Python AST nodes, so that dynamic physical formulas can be evaluated safely without Remote Code Execution (RCE) risks.
*   **Acceptance Criteria**:
    *   Only safe mathematical nodes (Add, Sub, Mult, Div, Pow, UAdd, USub, Constant, Num, Name, Load) are permitted.
    *   Any attempt to call functions (e.g., `eval()`, `__import__()`), loop, or import packages throws an immediate `SecurityError`.
    *   Standard Python `eval()` is completely avoided at all parsing boundaries.

#### 9. Private Variable and Underscore Protection
*   **User Story**: As an **Agent Platform Engineer**, I want the AST parser to reject any variable names starting with underscores, so that private system variables or internal properties are inaccessible to the caller.
*   **Acceptance Criteria**:
    *   Identifiers starting with an underscore (e.g. `_builtins_`) immediately trigger a `SecurityError` during name validation.
    *   Only whitelisted mathematical constants (`pi`, `E`) and verified physical unit abbreviations are allowed as variable names.

---

### Category 4: Interactive Agent Self-Healing

#### 10. Plaintext Educational Error Responses
*   **User Story**: As an **AI Agent**, I want the computational tool to catch syntax, safety, and math errors and return them as readable plaintext, so that I can self-correct my physical formulas dynamically within the conversation.
*   **Acceptance Criteria**:
    *   Making a dimensional mismatch error (e.g. `10 kg + 5 m`) returns a successful tool output containing the plaintext: `Type Error: Dimensional Mismatch: Cannot add incompatible dimensions`.
    *   Division by zero returns: `Math Error: Nonsense: Division by zero`.
    *   Taking the reciprocal of a zero-value quantity returns: `Math Error: Nonsense: Zero-value quantity has no defined reciprocal`.

---

### Category 5: Dynamic Discovery & Local Integration

#### 11. Dynamic Supported Units Registry
*   **User Story**: As an **AI Agent**, I want to query a resource listing supported physical dimensions, so that I can format my unit abbreviations correctly and avoid hallucinations.
*   **Acceptance Criteria**:
    *   Querying the `units://supported` resource URI returns a structured JSON mapping categories (length, mass, force, energy, power, pressure, etc.) to valid abbreviations.
    *   Absolute and relative temperature scales are grouped under a unified, intuitive `temperature` category.

#### 12. Programmatic Local Stdio Connection
*   **User Story**: As an **Agent Platform Engineer**, I want to connect the server programmatically to local Python agents, so that I can use it as an external local tool.
*   **Acceptance Criteria**:
    *   The server's standard input/output streams cleanly handle standard JSON-RPC 2.0.
    *   Programmatic integration using Google Antigravity SDK's `McpStdioServer` processes works successfully.

#### 13. Non-MCP Programmatic & CLI Integration
*   **User Story**: As an **Agent Platform Engineer**, I want to use the core units-solving engine directly as a standard Python package or run evaluations via a local Command Line Interface (CLI), so that I can perform physical calculations in environments where the Model Context Protocol is not available.
*   **Acceptance Criteria**:
    *   The core algebra types and AST parsing functions are structured to be fully importable directly in any standard Python script (e.g. `from src.parser import parse_and_evaluate`) without requiring FastMCP to be running.
    *   Expose a standard, portable CLI utility executable (`skookum-cli`) that accepts a physics equation and a target unit (e.g. `skookum-cli -e "10m * 5" -t "m"`) and prints the exact conversion result directly to stdout, exiting with 0 on success.

### Category 6: Natural Language & Traceability Seam (Roadmap - Phase 3)

#### 14. Conversational Expression Extraction
*   **User Story**: As an **AI Agent**, I want to submit raw conversational prose containing embedded physical measurements, so that Skookum can extract the mathematical quantities and operations without requiring me to pre-parse the text.
*   **Acceptance Criteria**:
    *   Submitting natural paragraphs (e.g., *"What happens when 70% of the 10g of coffee is introduced?"*) successfully isolates and parses the calculation spans.
    *   Implicit syntactic modifications (e.g. *"half a mile"*, *"double the speed"*) collapse into correct mathematical representations (`0.5 * mile`, `2 * speed`).
    *   Alphanumeric word numbers (`"zero"`, `"half"`) are normalized to standard scalars.
    *   Synonym variations (`"inches"`, `"feet"`, `"'"` , `"""`) map cleanly to canonical unit symbols.

#### 15. Machine-Readable Operations AST & Traceability Logs
*   **User Story**: As an **Agent Platform Engineer**, I want the normalization output to include a structured, inspectable mathematical operations log, so that I can audit exactly how Skookum translated conversational input into mathematical calculations.
*   **Acceptance Criteria**:
    *   The API payload returned from the normalizer includes a language-independent JSON **Operations AST** displaying operation nodes (`Multiply`, `Divide`, `Convert`) and their operands.
    *   The receipt maps original raw text spans to their normalized canonical elements to guarantee absolute traceability.

### Category 7: Visual Verification & QA Playgrounds (Phase 1)

#### 16. Visual Regression & Boundary Verification
*   **User Story**: As a **QA Tester**, I want to manually execute high-risk calculations (e.g. division-by-zero, RCE exploits, dimensional mismatches) via the web dashboard and receive dynamic, color-coded diagnostic errors and tips, so that I can easily verify that physical safety guards and AST Sandbox security boundaries are perfectly functional.
*   **Acceptance Criteria**:
    *   Submitting an invalid calculation (e.g., `10m / 0` or `10 kg + 5 m`) instantly renders a dynamic neon red card displaying the error type (Math Error, Type Error) with helpful diagnostic tips.
    *   Submitting an RCE injection or invalid variables (e.g. containing `_` or private methods) is successfully caught and displayed as a "Security Error" with instructions on sandboxed safety rules.

#### 17. Interactive SI Base Reference Inspector
*   **User Story**: As a **QA Tester**, I want to visually inspect the inferred dynamic dimensionality and SI base conversion scales of my calculations on the dashboard, so that I can cross-examine the core engine's internal mathematical scaling calculations against physical constants.
*   **Acceptance Criteria**:
    *   Exposing computed results displays the exact SymPy fraction, the decimal approximation, the inferred algebraic dimensionality vector (e.g. `[mass] * [length] * [time] ** -2`), and the base SI scale factor (e.g., scale factor in meters or seconds).
    *   The interactive units accordion palette displays clean abbreviations and categories, allowing unit injection on click.

#### 18. Local Session Replay History
*   **User Story**: As a **QA Tester**, I want to store my manual calculation runs locally and re-execute them with a single click, so that I can perform rapid regression cycles during QA validation passes without re-typing.
*   **Acceptance Criteria**:
    *   The dashboard automatically caches up to 15 successful calculations in browser `localStorage`.
    *   Clicking a history card instantly populates the solver input fields and re-triggers the calculation on the backend.

---

## System Boundaries

To maintain high cohesion and prevent dependency pollution, the co-processor enforces the following functional boundaries:
*   **Decoupled Value Objects**: The immutable physical measurement representation (`Quantity` value object) is strictly decoupled from the conversion algorithms (`Converter` module) behind a dedicated seam.
*   **Double-Form Dimension Enforcement**: Pairs semantic compile-time generic parameters (`Unit[T_Dim]` / `Quantity[T_Dim]`) for IDE-level safety with runtime algebraic exponent dictionaries (`Cardinality`) for dynamic calculations.
*   **AST Sandbox Specifications**: The AST validator enforces a strict whitelist of safe AST mathematical nodes (Add, Sub, Mult, Div, Pow, UAdd, USub, Constant, Num, Name, Load). All names are restricted to verified unit symbols or mathematical constants. Any name containing leading underscores (`_`) or private attributes is immediately blocked.

---

## Validation & Quality Metrics

We establish the following quality standards for the Skookum MCP project:
*   **Black-Box Behavioral Assertions**: All tests must verify external interfaces, mathematical rational identities, and security boundaries rather than checking low-level internal state transitions.
*   **Statement and Branch Coverage**: We strive to maintain a strict 100% statement and branch coverage across all modules (types, engine, parser, server, and dashboard app).
*   **RCE Mitigation Verifications**: Maintain explicit property and injection tests designed to attempt sandboxing bypasses, verifying that no unauthorized code or attributes are exposed.

---

## Out of Scope & Roadmap

### Out of Scope for Phase 1
1.  **Vector Dimensional Algebra**: High-dimensional vector physical mathematics (e.g., cross products, dot products) are out of scope for the initial release.
2.  **Dynamic Custom Unit Creation**: Allowing agents to register arbitrary, dynamic custom conversion scales at runtime.

### Technical Roadmap
*   **Vector Math Support**: Introduce coordinate vector units and direction algebra (dot/cross products) while retaining strict dimensional compatibility checks.
*   **Dynamic Registries**: Expose an MCP tool allowing authorized agents to define and inject custom unit coefficients dynamically during active sessions.
*   **Native Dependency Purge (Pint Decoupling)**: Transition the `Converter` engine away from the heavy third-party `Pint` library, replacing it with a native, compiled JSON dictionary registry of SI base factors to achieve 100% dependency self-containment.
*   **Natural Language Normalization Pipeline (Phase 3)**: Establish an upstream normalization pipeline to extract physical quantities and semantic relations from messy, natural prose. It will resolve adjoined numbers/units (`10g`), word-numbers (`"half"`, `"zero"`), synonym mapping (`"inches"`/`"\""` $\to$ `"inch"`), and syntactically distributed intent (e.g., `"half a mile"` $\to$ `0.5 * mile`), while providing a machine-readable intermediate Operations AST for agent verification.

---

## Open Questions & Technical Decisions

### 1. Unicode Symbol Support (e.g., `π`, `Ω`, `μ`)
*   *Requirement*: LLM agents naturally write standard Unicode mathematical and unit symbols when parsing technical texts.
*   *Technical Decision*: **Preprocessor Symbol Normalization**.
    *   *Reference*: See **[ADR 0003](file:///home/mzk/Documents/codespaces/units-mcp/docs/adr/0003-use-preprocessor-normalization-for-unicode-symbol-support.md)**.
    *   *Outcome*: We normalize Unicode symbols at the preprocessor boundary into standard ASCII canonical equivalents before parsing. This provides seamless symbol support while preserving a small, simple, and perfectly secure AST Sandbox whitelist.
