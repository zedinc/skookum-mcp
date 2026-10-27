# ADR 0006: Bind Number-Unit Juxtaposition as Quantity Literals

## Context & Problem Statement
The preprocessor turns `10 m / 2 s` into `10 * m / 2 * s`, and Python's grammar reads `*` and `/` left to right, so the expression becomes `((10 m) / 2) * s`: 5 m·s instead of 5 m/s. Likewise `100 W / 2 K` yields W·K and `10 m / 2 m/s` yields m²/s. Pint behaves the same way, so this is a shared convention among unit libraries, but it contradicts how an engineer reads the text: `10 m` and `2 s` are two quantities and the `/` divides one by the other. Nothing in the domain forces the left-to-right reading; it is an artifact of discarding the adjacency of number and unit when the implicit `*` is inserted.

## Decision
Adjacency is preserved and used.

1. **Marking.** The preprocessor emits `@` (same precedence as `*`, so tree shapes are unchanged) for the multiplications it *inserts*. A user-typed `@` is rejected up front (`SecurityError`, as before), so the marker cannot be forged. Preprocessing happens exactly once, before ambiguity resolution (ADR 0004), and the resolver passes the prepared text to the evaluator.
2. **Quantity literals.** A tree pass (`src/juxtaposition.py`, replacing the temperature-only regrouping of ADR 0005) rewrites each chain of `*` `/` `@` operands. `number @ unit` forms one literal that binds tighter than `*` and `/`, and following `/ unit-only` operands (`/s` in `2 m/s`) are absorbed into it. A following explicit `*` is not absorbed. So `10 m / 2 s` is `(10 m) / (2 s)`, `100 W / 2 K` is 50 W/K, and `x / 2 m/s` is `x / (2 m/s)`.
3. **Leading unit-free factors are one number.** `3 * 4 m` is `(3*4) m`; a parenthesised `(10/2) s` is unambiguously a number times a unit; `10/(2 s)` is unambiguously a rate.
4. **The remaining case is ambiguous, and Skookum does not choose.** When a unit-free run is divided by a number directly followed by a unit (`10 / 2 s`, `1/3 m`, `5 / 2 s`), both readings are legitimate: `(10/2) s` ("scalar") or `10/(2 s)` ("divisor"). The tool returns `Ambiguous Fraction` with the result under each reading, in the style of ADR 0004/0005. Which one is meant is the caller's call.
5. **Decisions are recorded and then adopted.** Once the caller decides, the choice can be given per call (`assume={"fraction_unit": "scalar" | "divisor"}`), recorded for the rest of the session (`set_reading_default("fraction_unit", "scalar")`, in memory only), or set by the user under `[readings]` in the config file. Precedence: `assume`, then session, then config; with none, Skookum asks. Applied decisions are reported in the `Assumptions:` line. The same mechanism now also records point-vs-interval decisions from ADR 0005 (`degC`, `degF`). Agents never write the config file.

The branching machinery of ADR 0005 is generalised into `src/readings.py`: a *reading question* is raised at an unsettled occurrence, each option is evaluated, and the caller either gets the single valid result or the full set of readings.

## Options Considered
*   **Keep left-to-right (Rejected).** Matches Pint, but silently produces wrong units for ordinary engineering text.
*   **Always bind the unit to the nearest number (Rejected).** Turns `1/3 m` into `1/(3 m)`, a worse silent surprise than today.
*   **Pick a rule for `10 / 2 s` and document it (Rejected).** Either choice is wrong for some author. Deciding is outside the engine's remit; a one-time recorded decision costs the caller a single round trip.

## Consequences
*   Expressions that relied on the old reading change. These were almost certainly wrong (`10 m / 2 s` as m·s), and the unit-checked target conversion rejected most of them anyway.
*   Prior art differs: Pint evaluates `10 m / 2 s` as m·s. Skookum deliberately does not.
*   `1/3 m` now asks the first time. A single `set_reading_default("fraction_unit", "scalar")` or a config line removes that for good.
*   The temperature-literal regrouping is subsumed; the offset-scale rules of ADR 0005 are otherwise unchanged. An explicit `m * 5 * degC` is no longer regrouped and is read as a compound unit.
*   Readings that give identical results (`pi / 2 rad`) are not put to the caller.
*   `mpg` expands to `mile / gallon`, so it inherits the US-vs-Imperial question from ADR 0004 and needs a profile or default.

## Acceptance examples

| Expression | Result |
|---|---|
| `10 m / 2 s` → m/s | `5 meter / second` |
| `100 W / 2 K` → W/K | `50` |
| `10 m / 2 m/s` → s | `5 second` |
| `3 * 4 m / 2 s` → m/s | `6` |
| `10 / (2 s)` → 1/s, `(10/2) s` → s | `5`, unambiguous |
| `10 / 2 s`, `1/3 m` | `Ambiguous Fraction` listing both results |
| same with `assume={"fraction_unit": "scalar"}` | `5 second`, with a note |

---

## Status
*   **Status**: Approved and implemented
*   **Date**: 2026-10-27
*   **Relates to**: ADR 0004, ADR 0005 (generalises its branching), ADR 0003 (preprocessor)
