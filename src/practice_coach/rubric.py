"""A small, transparent feedback rubric.

Design rules (from the case study's implementation guide):
* Feedback is bounded by a fixed rubric and the scenario's reviewed cue phrases,
  not open-ended advice.
* It only looks at the *words* of the response. It never scores accent, tone of
  voice, speed, fluency, eye contact or speaking style.
* It never diagnoses or claims to know how the person feels.
* Every suggestion is optional and phrased that way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .scenarios import CRITERIA_KEYS, Scenario

CRITERION_LABELS = {
    "acknowledge": "Acknowledged what the other person said",
    "respond_to_concern": "Connected to the specific thing they mentioned",
    "next_step": "Offered help, a next step or a question",
}

SUGGESTIONS = {
    "acknowledge": "If you like, you could start by briefly reflecting what you heard (for example, \"That sounds like a lot\").",
    "respond_to_concern": "One option is to mention the specific thing they talked about, so they know you heard the detail.",
    "next_step": "You might add an offer or a question, which can keep the conversation going.",
}


@dataclass(frozen=True)
class CriterionResult:
    key: str
    label: str
    met: bool
    matched: list[str]


@dataclass(frozen=True)
class Feedback:
    scenario_id: str
    response: str
    results: list[CriterionResult]
    suggestions: list[str]
    examples: list[str]

    @property
    def met_count(self) -> int:
        return sum(r.met for r in self.results)

    def as_text(self) -> str:
        lines = ["Feedback on the words in your response:"]
        for r in self.results:
            mark = "[x]" if r.met else "[ ]"
            lines.append(f"  {mark} {r.label}")
        if self.suggestions:
            lines.append("")
            lines.append("Optional ideas (use only if they feel useful to you):")
            lines.extend(f"  - {s}" for s in self.suggestions)
        else:
            lines.append("")
            lines.append("Your response covered all three parts of this practice goal.")
        if self.examples:
            lines.append("")
            lines.append("Example responses (one of many reasonable ways to reply):")
            lines.extend(f"  * {e}" for e in self.examples)
        lines.append("")
        lines.append("Note: this tool checks wording only. It does not judge your voice, accent or how you speak.")
        return "\n".join(lines)


def _normalise(text: str) -> str:
    text = text.lower().replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()


def _matches(text: str, cue: str) -> bool:
    if cue == "?":
        return "?" in text
    # Word-boundary match at the start so "help" doesn't match "whelp";
    # prefix cues such as "congrat" still match "congratulations".
    return re.search(r"(?<![a-z])" + re.escape(cue), text) is not None


def evaluate(scenario: Scenario, response: str) -> Feedback:
    """Check a typed or transcribed response against the scenario rubric."""
    text = _normalise(response)
    results: list[CriterionResult] = []
    suggestions: list[str] = []
    for key in CRITERIA_KEYS:
        matched = [c for c in scenario.criteria[key] if _matches(text, c)]
        met = bool(matched)
        results.append(CriterionResult(key, CRITERION_LABELS[key], met, matched))
        if not met:
            suggestions.append(SUGGESTIONS[key])
    examples = scenario.example_responses[:2] if suggestions else []
    return Feedback(scenario.id, response, results, suggestions, examples)
