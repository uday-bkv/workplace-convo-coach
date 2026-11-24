"""Load and validate the practice scenario library."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

CRITERIA_KEYS = ("acknowledge", "respond_to_concern", "next_step")


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    setting: str
    prompt: str
    goal: str
    criteria: dict[str, list[str]]
    example_responses: list[str] = field(default_factory=list)


class ScenarioError(ValueError):
    """Raised when the scenario file is malformed."""


def _parse(raw: dict) -> Scenario:
    missing = [k for k in ("id", "title", "setting", "prompt", "goal", "criteria") if k not in raw]
    if missing:
        raise ScenarioError(f"Scenario {raw.get('id', '?')} is missing: {', '.join(missing)}")
    criteria = raw["criteria"]
    for key in CRITERIA_KEYS:
        cues = criteria.get(key)
        if not cues or not all(isinstance(c, str) and c.strip() for c in cues):
            raise ScenarioError(f"Scenario {raw['id']}: criterion '{key}' needs a list of cue phrases")
    return Scenario(
        id=raw["id"],
        title=raw["title"],
        setting=raw["setting"],
        prompt=raw["prompt"],
        goal=raw["goal"],
        criteria={k: [c.lower() for c in criteria[k]] for k in CRITERIA_KEYS},
        example_responses=list(raw.get("example_responses", [])),
    )


def load_scenarios(path: str | Path | None = None) -> list[Scenario]:
    """Load scenarios from a JSON file, or the bundled library if no path is given."""
    if path is None:
        text = resources.files("practice_coach.data").joinpath("scenarios.json").read_text("utf-8")
    else:
        text = Path(path).read_text("utf-8")
    data = json.loads(text)
    items = data.get("scenarios", [])
    if not items:
        raise ScenarioError("No scenarios found")
    scenarios = [_parse(item) for item in items]
    ids = [s.id for s in scenarios]
    if len(ids) != len(set(ids)):
        raise ScenarioError("Scenario ids must be unique")
    return scenarios


def get_scenario(scenarios: list[Scenario], scenario_id: str) -> Scenario:
    for s in scenarios:
        if s.id == scenario_id:
            return s
    raise KeyError(scenario_id)
