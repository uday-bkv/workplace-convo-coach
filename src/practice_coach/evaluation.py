"""Tools for a study team running a multiple-baseline single-case evaluation.

Researchers record *human-delivered* probe results here (not app scores), using
blinded raters. Phases follow the case study: baseline, intervention,
generalization and retention.

CSV columns: participant, session, phase, rater, score
  score = number of probe opportunities with an emotionally responsive reply,
          or a percentage, as defined in your protocol.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

PHASES = ("baseline", "intervention", "generalization", "retention")


@dataclass(frozen=True)
class Probe:
    participant: str
    session: int
    phase: str
    rater: str
    score: float


def load_probes(path: str | Path) -> list[Probe]:
    probes = []
    with open(path, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            phase = row["phase"].strip().lower()
            if phase not in PHASES:
                raise ValueError(f"line {i}: unknown phase '{row['phase']}'")
            probes.append(Probe(row["participant"].strip(), int(row["session"]), phase,
                                row.get("rater", "").strip(), float(row["score"])))
    return probes


def _session_scores(probes: list[Probe]) -> dict[tuple[str, str], list[tuple[int, float]]]:
    """Average across raters per participant/phase/session."""
    grouped: dict[tuple[str, str, int], list[float]] = defaultdict(list)
    for p in probes:
        grouped[(p.participant, p.phase, p.session)].append(p.score)
    out: dict[tuple[str, str], list[tuple[int, float]]] = defaultdict(list)
    for (part, phase, sess), scores in grouped.items():
        out[(part, phase)].append((sess, mean(scores)))
    for v in out.values():
        v.sort()
    return out


def pnd(baseline: list[float], treatment: list[float]) -> float | None:
    """Percentage of non-overlapping data: share of treatment points above the highest baseline point."""
    if not baseline or not treatment:
        return None
    ceiling = max(baseline)
    return 100.0 * sum(t > ceiling for t in treatment) / len(treatment)


def inter_rater_agreement(probes: list[Probe]) -> float | None:
    """Share of double-rated sessions where raters gave identical scores."""
    grouped: dict[tuple[str, str, int], list[float]] = defaultdict(list)
    for p in probes:
        grouped[(p.participant, p.phase, p.session)].append(p.score)
    multi = [s for s in grouped.values() if len(s) > 1]
    if not multi:
        return None
    return 100.0 * sum(len(set(s)) == 1 for s in multi) / len(multi)


def summarise(probes: list[Probe]) -> str:
    scores = _session_scores(probes)
    participants = sorted({p.participant for p in probes})
    lines = [f"Participants: {len(participants)} (single-case design - do not generalise beyond this sample)", ""]
    header = f"{'participant':<12}" + "".join(f"{ph:>16}" for ph in PHASES) + f"{'PND (int.)':>12}"
    lines.append(header)
    lines.append("-" * len(header))
    for part in participants:
        row = f"{part:<12}"
        for ph in PHASES:
            vals = [s for _, s in scores.get((part, ph), [])]
            row += f"{(f'{mean(vals):.1f} (n={len(vals)})' if vals else '-'):>16}"
        base = [s for _, s in scores.get((part, "baseline"), [])]
        treat = [s for _, s in scores.get((part, "intervention"), [])]
        val = pnd(base, treat)
        row += f"{(f'{val:.0f}%' if val is not None else '-'):>12}"
        lines.append(row)
    ira = inter_rater_agreement(probes)
    lines.append("")
    lines.append(f"Inter-rater exact agreement: {f'{ira:.0f}%' if ira is not None else 'n/a (no double-rated sessions)'}")
    lines.append("Report sample size, phase lengths and limitations alongside these figures.")
    return "\n".join(lines)
