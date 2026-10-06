# ADR 0004: Resolve Ambiguous Unit Symbols by Context and User Defaults

## Context & Problem Statement
Real documents use symbols with more than one valid meaning: `pt` (pint or typographic point), `C` (coulomb or Celsius), `ton` (short, long or metric), `gal` (US or Imperial), `oz` (mass or fluid), `cal`, `hp`, `F`. Until now the engine silently picked whatever Pint picked, which produces confident wrong answers, the failure this project exists to prevent. No single default is universally right, so a fixed table cannot be the answer. An agent usually *can* tell what is meant from the other quantities in the expression, and that should be a one-time decision, not something repeated on every call.

## Decision
Ambiguity is a first-class result, resolved in layers (`src/ambiguity.py`). Each layer is tried in order:

1. **Explicit spellings** are never ambiguous: `°C`/`°F`/`°R` (normalized in the preprocessor, as in ADR 0003), candidate ids such as `us_gallon` or `typographic_point`, and shorthands `R` (Rankine) and `Cal` (kilocalorie).
2. **Hard bindings**: the per-call `assume` argument, then in-memory session defaults set by the `set_unit_default` tool. Never overridden by context or config.
3. **Context**: every candidate assignment for the ambiguous symbols is evaluated through the normal parser and converter, and only dimensionally valid ones survive. The target unit counts as context. The search is capped at 4 distinct ambiguous symbols.
4. **Soft preferences**, used only to break ties among survivors: per-symbol `[defaults]` from the user config file, then a `profile` (`us`, `imperial`, `metric`). A default can never force a dimensionally invalid reading.
5. **Structured response**: if more than one interpretation survives, the tool returns `Ambiguous Unit:` followed by JSON listing the candidates (id, unit, dimension, description), each surviving interpretation with its result, and each rejected interpretation with the reason. When the server resolves something itself, the output carries an `Assumptions:` line saying what and why.

The ambiguous-symbol registry is exposed as the `units://ambiguous` resource. It deliberately covers only ambiguities that occur in real engineering text; exotic collisions (e.g. `Mm` vs `mm`) are out of scope.

**Configuration** is read-only TOML from `SKOOKUM_CONFIG`, else `$XDG_CONFIG_HOME/skookum/config.toml` (default `~/.config`). The server never writes it; agents may only set session-scoped defaults. A project-local file was rejected because a stdio server's working directory is chosen by the client. Reading TOML via `tomllib` raises the Python floor to 3.11.

## Consequences
*   Inference reuses the existing dimension checker, so it adds no new physics logic and the AST sandbox is untouched; candidate text is substituted only from a fixed registry.
*   Evaluation cost grows with the number of ambiguous symbols (bounded at 64 interpretations).
*   With no config, a bare `1 ton` is an error with options, not a guess. This is intentional strictness; a one-line config default removes the friction.
*   Inference is dimension-based only: `12 pt` alone cannot be disambiguated from a document's topic, which is why the response gives the agent the data to reason with.

---

## Status
*   **Status**: Approved
*   **Date**: 2026-10-06
