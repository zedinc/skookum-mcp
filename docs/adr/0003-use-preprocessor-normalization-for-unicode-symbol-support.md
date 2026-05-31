# ADR 0003: Use Preprocessor Normalization for Unicode Symbol Support

## Context & Problem Statement
AI agents and human engineers naturally write standard Unicode symbols (e.g., `π` for pi, `Ω` for ohms, or `μ` for micro) when typing physical formulas and scientific equations. To support these user-friendly symbols safely inside **Skookum MCP**, we must intercept and evaluate them without weakening our **AST Sandbox** security boundary. Exposing the parser to raw non-ASCII identifiers could introduce validation bypass exploits or RCE vectors.

## Decision Drivers
1.  **Security First**: The AST Sandbox must remain perfectly secure against injection vectors and obfuscated characters.
2.  **Grammar Simplicity**: The whitelisted `_SafeASTVisitor` should remain tiny, cohesive, and easily auditable.
3.  **User Experience**: Agents and humans should be able to type standard Unicode mathematical characters and receive accurate calculations.

## Options Considered

### Option A: Preprocessor Symbol Normalization (Approved)
Scan the raw input string inside `preprocess_expression` (in `src/parser.py`) and translate Unicode symbols into their standard ASCII canonical equivalents (e.g., `π` $\to$ `pi`, `Ω` $\to$ `ohm`, `μ` $\to$ `micro`) *before* the string is compiled into an AST.
*   **Pros**:
    *   *Absolute Security*: Keeps the whitelisted AST Name validator extremely small, simple, and secure (only whitelisting ASCII constants `pi` and `E`).
    *   *Zero Parser Overhead*: Leverages standard regex replacements before parsing, meaning no modification to the AST safety visitor itself is required.
    *   *High Extensibility*: Adding new Unicode symbols is as simple as adding a key-value mapping to a preprocessor dictionary.
*   **Cons**:
    *   Adds a lightweight string scanning and translation phase on every incoming expression string (negligible performance impact).

### Option B: AST Whitelist Expansion (Rejected)
Expand the `_SafeASTVisitor` name validator to support non-ASCII Unicode identifiers directly during AST compiled Name node validation.
*   **Pros**:
    *   Expressions are parsed directly as written without string manipulation.
*   **Cons**:
    *   *Security Risk*: Exposing the AST name identifier whitelists to broad Unicode character sets opens the system to homoglyph attacks or unexpected encoding bypasses in Python's parsing engine.
    *   *High Complexity*: Requires maintaining an expanding list of Unicode character codepoints inside the security visitor, making the security boundary complex and difficult to audit.

## Pros and Cons of the Decision
We chose **Option A** because it enforces a strict security boundary by translating user-friendly characters at the preprocessor level, ensuring that the AST compiler only ever receives safe, standard ASCII whitelisted symbols.

---

## Status
*   **Status**: Approved
*   **Date**: 2026-05-31
*   **Decided by**: Skookum MCP Engineering & Product Alignment Group
