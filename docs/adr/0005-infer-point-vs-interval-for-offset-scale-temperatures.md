# ADR 0005: Infer Point vs. Interval for Offset-Scale Temperatures

## Context & Problem Statement
A temperature written as `5 degC` is either a **point** on a scale (a thermometer reading: 5 °C = 278.15 K) or an **interval** (a change: 5 K of difference). The unit does not say which; the surrounding expression does. Today the engine decides by unit name alone (`'delta' in unit.name`) and rejects every multiplicative use of an offset-scale unit (commit `9f2c868`). That is strict, but it fails real expressions that are physically fine:

*   `2 kg * 4.18 kJ/(kg*degC) * 5 degC`: calorimetry. The `5 degC` is a ΔT. Today: error.
*   `(101.325 kPa * 2 L) / (20 degC)`: Boyle's/combined gas law. The `20 degC` is a point and physical convention is to convert to kelvin before any multiplication or division. Today: error, though the intended result is unambiguous.

It also hides an inconsistency: `kJ/(kg*degC)` only works today because `Unit.__mul__`/`__truediv__` silently drop the offset, so the engine already treats `degC` inside a rate as an interval, by accident.

Dimensional analysis cannot settle every case. `1 mol * 8.314 J/(mol*K) * 20 degC` (gas constant times a point) and `2 kg * 4.18 kJ/(kg*K) * 5 degC` (specific heat times a ΔT written in degC) have the same unit structure but opposite meanings, and both are dimensionally valid. Guessing silently would produce a confident wrong answer, the failure this project exists to prevent.

## Scope
Offset-scale temperatures (`degC`, `degF`) and the zero-based scales they relate to (`K`, `degR`). Gauge vs. absolute pressure has the same structure and should reuse this design, but is a separate decision. Log units (dB, pH) are out of scope.

## Decision
Inference is performed at the **expression layer** (the AST evaluator), not inside `Quantity`. `Quantity` stays a strict value object (ADR 0001): used directly, it keeps raising on multiplying an offset scale. The evaluator, which sees both operands and the expression structure, decides what each affine literal *means* before arithmetic happens.

**Vocabulary becomes data.** The registry declares each affine family explicitly (points, their interval counterparts, zero-based scales) instead of sniffing `'delta'` out of names. Zero-based units (`K`, `degR`) are *unspecified*: scaling them is always legal and arithmetic is identical for points and intervals, so their kind never causes an error and only labels results.

**Rules, applied per occurrence of an offset-scale literal, in order:**

1. **Explicit.** `delta_degC`, `delta_degF` are intervals. `K`, `degR` and the explicit forms below never trigger inference.
2. **Forced interval** (the only automatic inference to *interval*; this is "Option A: conservative"):
    *   a negative value on a zero-based scale, e.g. `-5 K`, which cannot be a point; or
    *   an offset-scale literal multiplied or divided with a rate whose expression contains the *same* scale in a denominator position, e.g. `kJ/(kg*degC) * 5 degC`. This is detected from the expression structure (Name nodes), not from numeric scale, because "per degC" and "per K" are numerically identical.
3. **Unforced point in a multiplicative operation** (`*`, `/`, `**`): by physical convention, convert to the zero-based scale of the same step (`degC` → `K`, `degF` → `degR`) before the operation, and report it. `3 m * 2 degC` evaluates as `3 m * 275.15 K`; `(101.325 kPa * 2 L) / (20 degC)` as `... / 293.15 K`.
4. **Hazard: unforced point next to a "per kelvin" rate.** If the other operand carries a temperature exponent below zero (`J/(mol*K)`, `kJ/(kg*K)`) and rule 2 did not force interval, both readings are plausible (gas constant × T versus specific heat × ΔT) and dimensions cannot choose. The tool returns a structured `Ambiguous Temperature Kind` response, in the style of ADR 0004, listing the result under each reading. The agent resolves it from the meaning of the other operand, or writes `K` / `delta_degC` explicitly.
5. **Addition and subtraction** keep their current semantics, expressed with explicit kinds: point − point = interval; point ± interval = point; interval ± interval = interval; point + point is an error.

**Still errors:** point + point; negating a point on an offset scale (`-(5 degC)`: a negative absolute temperature is meaningless); any direct multiplicative use through the `Quantity` API.

**Transparency.** Whenever the evaluator converts or infers, the result carries an `Assumptions:` line, e.g. `2 degC converted to 275.15 K (offset-scale temperature in a multiplicative operation)`. Explicit overrides: write the unit you mean (`K`, `delta_degC`), or pass `assume={"degC": "point" | "interval"}`, which applies to every *unforced* occurrence of that symbol in the call. No config-file default exists for this: it is physics, not preference.

## Options Considered

### Option A: Conservative inference (Approved)
Infer *interval* only when the expression forces it (rule 2); apply the kelvin-conversion convention to unforced points (rule 3); ask when the two readings genuinely compete (rule 4).
*   **Pros**: Keeps strictness where it matters; fixes calorimetry and gas-law forms; agents can see and override every assumption.
*   **Cons**: Rule 4 costs a round trip for some `per K` expressions; per-occurrence kind needs an AST-level pass rather than the per-symbol substitution of ADR 0004.

### Option B: Permissive (Rejected)
Flip to interval whenever the point reading is invalid, noting it.
*   **Cons**: Turns `3 m * 2 degC` and `R * 20 degC` into confident answers on a guess about intent. The error-versus-guess boundary should be drawn by evidence in the expression, not by convenience.

### Option C: Keep blocking all multiplicative offset use (Rejected)
*   **Cons**: Rejects standard physics (gas laws, calorimetry) that agents write constantly, while the engine already accepts `per degC` rates through a bug.

## Consequences
*   `Unit.__mul__`/`__truediv__` dropping the offset is *deliberate*, not a bug: an offset unit inside a compound unit (`kg*degC`, `kJ/degC`) denotes a scale step. It is documented and tested instead of changed. A bare offset unit multiplied or divided onto a `Quantity` (`4.18 kJ/degC`) is likewise replaced by its interval unit.
*   A number written directly before an offset-scale unit binds to it as one literal even through implicit multiplication: `A * 5 degC` is `A * (5 degC)` and `A / 20 degC` is `A / (20 degC)`. This regrouping is deliberately limited to offset-scale units. General number-unit juxtaposition (`10 m / 2 s`) is a separate known issue.
*   Evaluator gains a small kind-propagation pass; `Quantity` and the converter are unchanged (ADR 0001 holds).
*   Pressure (`psig`/`psia`, differential `psi`) can adopt the same registry-declared families later.
*   The README and PRD statements about blocking absolute-temperature multiplication change from "error" to "converted to kelvin, with an assumption note".

## Verification (acceptance examples)

| Expression → target | Expected |
|---|---|
| `2 kg * 4.18 kJ/(kg*degC) * 5 degC` → kJ | `41.8 kilojoule`, `5 degC` treated as an interval (rate is per degC) |
| `(101.325 kPa * 2 L) / (20 degC)` → `kPa*L/K` | ≈ `0.6913`, `20 degC` converted to `293.15 K` |
| `3 m * 2 degC` → `m*K` | `825.45 meter * kelvin`, with assumption note |
| `2 kg * 4.18 kJ/(kg*K) * 5 degC` → kJ | `Ambiguous Temperature Kind`: ≈ `2325` (point) vs `41.8` (interval) |
| `1 mol * 8.314 J/(mol*K) * 20 degC` → J | `Ambiguous Temperature Kind`; `assume={"degC": "point"}` resolves it |
| `-5 K` | interval; `300 K + -5 K` → `295 kelvin` |
| `20 degC + 20 degC` | still an error |
| `-(5 degC)` | still an error |

---

## Status
*   **Status**: Approved and implemented
*   **Date**: 2026-10-26
*   **Relates to**: ADR 0001 (Quantity stays pure), ADR 0004 (structured ambiguity responses)
