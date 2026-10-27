"""
Reading questions (ADR 0005, ADR 0006).

Some expressions have more than one legitimate reading that Skookum must not choose between: is `5 degC` a
temperature reading or a difference, is `10 / 2 s` `(10/2) s` or `10/(2 s)`? The evaluator raises a
`ReadingQuestion` at the unsettled occurrence; `resolve_readings` re-runs the evaluation under each option and
either settles on the single valid result or reports every surviving interpretation to the caller.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .types import MathematicalError

MAX_QUESTIONS_PER_EXPRESSION = 3

TOPIC_TITLES = {
    "temperature_kind": "Ambiguous Temperature Kind",
    "fraction_unit": "Ambiguous Fraction",
}
FRACTION_KEY = "fraction_unit"
FRACTION_CHOICES = ("scalar", "divisor")


class ReadingQuestion(Exception):
    """Raised at an occurrence whose reading is not settled by the expression or by a recorded decision."""
    def __init__(self, key: Any, topic: str, label: str, hint_key: str, options: Dict[str, str],
                 summary: str, escape: str):
        super().__init__(label)
        self.key, self.topic, self.label = key, topic, label
        self.hint_key, self.options, self.summary, self.escape = hint_key, options, summary, escape


class AmbiguousReadingError(Exception):
    """More than one reading is valid, and no decision settles it."""
    def __init__(self, title: str, message: str, payload: Dict[str, Any]):
        super().__init__(message)
        self.title, self.message, self.payload = title, message, payload


@dataclass
class ReadingContext:
    """Decisions in force (`assume`, by topic key), where they came from, branch overrides, and notes."""
    assume: Dict[str, str] = field(default_factory=dict)
    sources: Dict[str, str] = field(default_factory=dict)
    overrides: Dict[Any, str] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def decision(self, topic_key: str, occurrence: Any) -> Optional[Tuple[str, str]]:
        """(choice, why) for an occurrence, or None if undecided. Branch overrides win over recorded decisions."""
        if occurrence in self.overrides:
            return self.overrides[occurrence], "one possible reading"
        if topic_key in self.assume:
            return self.assume[topic_key], self.sources.get(topic_key, "assumed by caller")
        return None


def resolve_readings(run: Callable[[ReadingContext], str], assume: Optional[Dict[str, str]] = None,
                     sources: Optional[Dict[str, str]] = None) -> Tuple[str, List[str]]:
    """
    Calls `run(ctx)` (parse, evaluate, convert, format). If an occurrence is unsettled, re-runs under each
    option and either settles on the single valid one or raises AmbiguousReadingError.
    """
    assume, sources = dict(assume or {}), dict(sources or {})
    leaves: List[Tuple[Dict[Any, str], str, List[str]]] = []
    rejected: List[Tuple[Dict[Any, str], str]] = []
    questions: Dict[Any, ReadingQuestion] = {}

    def branch(overrides: Dict[Any, str]) -> None:
        ctx = ReadingContext(assume=assume, sources=sources, overrides=dict(overrides))
        try:
            text = run(ctx)
        except ReadingQuestion as q:
            if len(overrides) >= MAX_QUESTIONS_PER_EXPRESSION:
                raise TypeError("Too many ambiguous readings in one expression; add parentheses or write "
                                "the unit you mean explicitly.")
            questions[q.key] = q
            for option in q.options:
                branch({**overrides, q.key: option})
            return
        except (TypeError, MathematicalError, ZeroDivisionError) as err:
            if not overrides:
                raise
            rejected.append((overrides, str(err)))
            return
        leaves.append((overrides, text, ctx.notes))

    branch({})

    def label(overrides: Dict[Any, str]) -> Dict[str, str]:
        return {questions[k].label: choice for k, choice in overrides.items()}

    if not leaves:
        detail = "; ".join(f"{label(o)}: {m}" for o, m in rejected[:4])
        raise TypeError(f"No reading of the ambiguous expression is valid. {detail}")
    if len(leaves) == 1:
        overrides, text, notes = leaves[0]
        notes = [n.replace("one possible reading", "the only reading valid here") for n in notes]
        for lit, choice in label(overrides).items():
            if not any(lit in n for n in notes):
                notes.append(f"{lit} read as '{choice}' (the only reading valid here)")
        return text, notes

    if len({text for _, text, _ in leaves}) == 1:
        # Every reading gives the same answer, so there is nothing for the caller to decide
        _, text, notes = leaves[0]
        return text, notes + [f"{lit}: both readings give the same result" for lit in (q.label for q in questions.values())]

    topics = {q.topic for q in questions.values()}
    title = TOPIC_TITLES[next(iter(topics))] if len(topics) == 1 else "Ambiguous Reading"
    hints = {}
    for q in questions.values():
        hints.setdefault(q.hint_key, " | ".join(repr(o) for o in q.options))
    hint = ", ".join(f"'{k}': {v}" for k, v in hints.items())
    escapes = "; ".join(dict.fromkeys(q.escape for q in questions.values()))
    summaries = " ".join(dict.fromkeys(q.summary for q in questions.values()))
    raise AmbiguousReadingError(
        title,
        f"{summaries} Re-call with assume={{{hint}}}, or {escapes}. A decision can be recorded for the rest "
        f"of the session with set_reading_default, or permanently under [readings] in the config file.",
        {
            "occurrences": {q.label: q.options for q in questions.values()},
            "interpretations": [{"treat": label(o), "result": t, "assumptions": n} for o, t, n in leaves],
            "rejected": [{"treat": label(o), "reason": m} for o, m in rejected[:4]],
        },
    )
