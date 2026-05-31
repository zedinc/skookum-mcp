# Skookum MCP: Active Issues & Technical Roadmap

This document serves as the active issue log and technical transition roadmap for **Skookum MCP** (`skookum-mcp`). It distinguishes between **Product Backlog** (requirements, alignment, documentation) and **Technical Backlog** (code, syntax, refactoring, and package decoupling) while tracking their resolution status.

---

## Triage Vocabulary: `ready-for-agent`

In this repository, the label **`[ready-for-agent]`** indicates a triage status. It means that:
1. The issue has been fully aligned and agreed upon by the human developer.
2. The requirements, scope, and **Acceptance Criteria** are exhaustively defined.
3. The issue is **100% prepared for an autonomous coding agent to pick up and implement** immediately without requiring further design input or requirements gathering.

---

## 1. Product / Project Backlog (Requirements, Alignment & Documentation)

### Issue: PRD Fleshing Out & Core Alignment
*   **Backlog Type**: Product / Project Backlog
*   **Status**: `[STATUS: RESOLVED]`
*   **Label**: `[ready-for-agent]`
*   **Specification**: [prd.md](file:///home/mzk/.gemini/antigravity/brain/3831196d-6eff-4c2f-bd42-e1217d23b78a/prd.md)
*   **Context**:
    To address early positioning ambiguity and align on Skookum MCP's core identity as a secure physical units co-processor for AI agents, we drafted a comprehensive Product Requirements Document (PRD) detailing extensive computational and coordinate user stories and precise acceptance criteria.
*   **Resolution**:
    The PRD was fully compiled, reviewed, and approved. Branding and headline positioning are fully aligned across `README.md`, `CONTEXT.md`, and all system modules.

---

### Issue: Natural Language Normalization & Extraction Pipeline (NLP/Normalizer Seam)
*   **Backlog Type**: Product Backlog (Phase 3 Roadmap Proposal)
*   **Status**: `[STATUS: OPEN]`
*   **Label**: `[ready-for-agent]`
*   **Specification**: Defined as a Phase 3 Roadmap goal in `prd.md`.
*   **Context**:
    AI agents and human scientists naturally write messy, conversational prose to describe physical queries (e.g., *"What happens when 70% of the 10g of coffee is introduced?"* or *"A 140 pound man walks for half a mile"*).
    To handle this without bloating our RCE-safe AST Sandbox or pure algebraic conversion engine with high-entropy parsing rules:
    1.  **Upstream Normalizer Seam**: Keep computational logic perfectly separated from natural language inference.
    2.  **Semantic Modifier Parser**: Handle complex, syntactically distributed scales (e.g., *"half a mile"*, *"double the speed"*), adjoined values (`10g`), and alphanumeric quantities (`"zero"`, `"half"`) by collapsing them into canonical mathematical expressions.
    3.  **Traceability Operations AST**: Expose a structured intermediate Operations AST (JSON format) and preprocessing receipt showing exactly how messy inputs were parsed and transformed before calculation, ensuring agents can debug normalization errors.
*   **Acceptance Criteria**:
    *   Expose a new `skookum_normalize` MCP tool accepting natural language string input and returning a structured normalization receipt.
    *   The tool dynamically extracts physical spans from natural prose, maps unit synonyms (`"inches"` $\to$ `"inch"`), and normalizes alphanumeric scalars/modifiers (`"half a mile"` $\to$ `0.5 * mile`).
    *   The output JSON contains the canonical AST math expression and a traceability trace log mapping original spans to normalized components.
    *   The normalization pipeline is strictly positioned upstream, ensuring `Converter` and AST Sandbox rules are unchanged.

---

## 2. Technical / Code Backlog (Syntax, Parser & Architecture)

### Issue: Bitwise Caret Exponent Compatibility (`^` vs `**`)
*   **Backlog Type**: Technical / Code Backlog
*   **Status**: `[STATUS: RESOLVED]`
*   **Label**: `[ready-for-agent]`
*   **Context**:
    In natural engineering and scientific texts, powers and exponents are frequently written using the caret symbol `^` (e.g., `kg.m/s^2` or `10^5`). Currently, the caret character `^` is flagged as **illegal** by the security whitelist (`_SafeASTVisitor`) because standard Python interprets `^` as the bitwise XOR operator (`ast.BitXor`), which is blocked to prevent obfuscated injection exploits.
*   **Planned Resolution Strategy**:
    Implement a safe preprocessor translation step inside `preprocess_expression` in `src/parser.py` that translates Unicode caret signs `^` to power signs `**` before AST parsing, resolving the compatibility gap without weakening the whitelisted security sandbox.

### Issue: Long-Term Pint Decoupling Plan
*   **Backlog Type**: Technical / Code Backlog
*   **Status**: `[STATUS: OPEN]`
*   **Context**:
    The **Converter** module (`src/engine.py`) currently relies on the third-party `Pint` library's `UnitRegistry` to dynamically resolve unit strings, retrieve physical constants, and fetch SI base offsets.
*   **Planned Resolution Strategy**:
    To achieve complete dependency self-containment, we aim to transition the codebase to a native registry:
    1.  **Static Registry**: Compile a JSON dictionary registry containing all physical constants and conversion coefficients natively.
    2.  **SI Solver**: Build a native, light-weight cardinality resolver that handles prefixed strings (e.g., `cm`, `ms`, `kHz`) dynamically.
    3.  **Pint Purge**: Safely remove `Pint` from `pyproject.toml` and verify all conversions against exact rational test benchmarks.

---

### Issue: Expose a Standard CLI Entrypoint (`skookum-cli`)
*   **Backlog Type**: Technical / Code Backlog
*   **Status**: `[STATUS: OPEN]`
*   **Label**: `[ready-for-agent]`
*   **Context**:
    While FastMCP makes the units solver incredibly easy to integrate into LLM agents via MCP Stdio, developers and other systems frequently need to perform physical math conversions directly from their terminal shells or in environments where the Model Context Protocol is not running.
*   **Planned Resolution Strategy**:
    1.  Create a lightweight CLI entrypoint function in `src/cli.py` that utilizes standard Python `argparse` to accept an expression string `-e` / `--expression` and a target unit `-t` / `--target`.
    2.  Delegate the calculations to the decoupled AST parser and converter engine (catching all Security, Parsing, and Type errors to output clean plaintext to stderr).
    3.  Register `skookum-cli` under `[project.scripts]` in `pyproject.toml` pointing to `src.cli:main`.
    4.  Add CLI-based programmatic integration tests to ensure 100% statement and branch coverage.
