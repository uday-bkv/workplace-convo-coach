"""Command-line interface.

    practice-coach practice            # interactive practice session
    practice-coach scenarios           # list scenarios
    practice-coach history             # show your saved practice (decrypted locally)
    practice-coach delete --all        # delete every record, audio clip and the key
    practice-coach delete --audio      # delete only saved audio
    practice-coach probes FILE.csv     # researchers: summarise human probe ratings
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path
from typing import Callable

from . import __version__, speech
from .evaluation import load_probes, summarise
from .rubric import evaluate
from .scenarios import load_scenarios
from .storage import DEFAULT_RETENTION_DAYS, PracticeStore, new_record

DISCLAIMER = (
    "This is a learning prototype, not a clinical or diagnostic tool.\n"
    "It gives optional suggestions about the words in a practice reply.\n"
    "It does not judge your voice, accent, speaking style or how you feel."
)


def default_data_dir() -> Path:
    return Path(os.environ.get("PRACTICE_COACH_HOME", Path.home() / ".practice_coach"))


def ask_yes_no(question: str, ask: Callable[[str], str]) -> bool:
    while True:
        ans = ask(f"{question} [y/n]: ").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("Please type y or n.")


def choose(options: list[str], ask: Callable[[str], str], allow_quit: bool = True) -> int | None:
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    if allow_quit:
        print("  q. Quit")
    while True:
        ans = ask("Choose: ").strip().lower()
        if allow_quit and ans in ("q", "quit"):
            return None
        if ans.isdigit() and 1 <= int(ans) <= len(options):
            return int(ans) - 1
        print("Please type one of the numbers shown.")


def run_practice(args, ask: Callable[[str], str] = input) -> int:
    scenarios = load_scenarios(args.scenarios)
    print(DISCLAIMER + "\n")

    save = ask_yes_no(
        f"Save your typed or transcribed replies on this computer (encrypted, auto-deleted after "
        f"{args.retention_days} days)?", ask)
    ok, reason = speech.speech_available()
    use_speech = False
    save_audio = False
    if ok:
        use_speech = ask_yes_no("Turn on the option to answer by speaking? (You can always type instead.)", ask)
        if use_speech and save:
            save_audio = ask_yes_no("Also keep the audio recordings? (Default is to discard audio after transcription.)", ask)
    else:
        print(f"Speaking option is off: {reason}. You can type your replies.\n")

    store = PracticeStore(args.data_dir, args.retention_days) if save else None

    while True:
        print("\nPractice scenarios:")
        idx = choose([s.title for s in scenarios], ask)
        if idx is None:
            break
        sc = scenarios[idx]
        print(f"\n--- {sc.title} ---")
        print(f"Setting: {sc.setting}")
        print(sc.prompt)
        print(f"Practice goal: {sc.goal}\n")

        mode = "text"
        audio = None
        if use_speech:
            pick = choose(["Type my reply", "Speak my reply"], ask, allow_quit=False)
            mode = "speech" if pick == 1 else "text"

        if mode == "speech":
            try:
                audio = speech.record(args.record_seconds)
                transcript = speech.transcribe(audio, args.whisper_model)
            except speech.SpeechUnavailable as exc:
                print(f"Speech did not work ({exc}). Please type your reply instead.")
                mode, audio, transcript = "text", None, ""
            if mode == "speech":
                print(f"\nTranscript: \"{transcript}\"")
                fix = ask("Press Enter if this is right, or type a corrected version: ").strip()
                response = fix or transcript
        if mode == "text":
            response = ask("Your reply: ").strip()

        if not response:
            print("No reply entered - that's fine. Pick another scenario or try again.")
            continue

        fb = evaluate(sc, response)
        print("\n" + fb.as_text())

        if store:
            rec = new_record(sc.id, response, mode, {r.key: r.met for r in fb.results})
            store.save(rec, audio if save_audio else None)
            print("\n(Saved, encrypted. Run 'practice-coach delete --all' to remove everything.)")

    print("\nThanks for practising.")
    return 0


def run_history(args) -> int:
    if not Path(args.data_dir).exists():
        print("No saved practice.")
        return 0
    store = PracticeStore(args.data_dir, args.retention_days)
    records = store.list_records()
    if not records:
        print("No saved practice.")
        return 0
    for r in records:
        when = dt.datetime.fromtimestamp(r.created_at).strftime("%Y-%m-%d %H:%M")
        met = sum(r.criteria_met.values())
        audio = " +audio" if r.has_audio else ""
        print(f"{when}  {r.scenario_id:<24} {met}/3 parts  ({r.input_mode}{audio})  id={r.id[:8]}")
        print(f"    \"{r.response_text}\"")
    return 0


def run_delete(args) -> int:
    path = Path(args.data_dir)
    if not path.exists():
        print("Nothing to delete.")
        return 0
    if args.all:
        PracticeStore(path, args.retention_days).delete_all()
        print(f"Deleted all practice records, audio and the encryption key in {path}.")
    elif args.audio:
        n = PracticeStore(path, args.retention_days).delete_audio_only()
        print(f"Deleted {n} audio recording(s).")
    elif args.id:
        store = PracticeStore(path, args.retention_days)
        matches = [r.id for r in store.list_records() if r.id.startswith(args.id)]
        if len(matches) != 1:
            print("No unique record matches that id.")
            return 1
        store.delete(matches[0])
        print("Deleted.")
    return 0


def run_scenarios(args) -> int:
    for s in load_scenarios(args.scenarios):
        print(f"{s.id:<24} {s.title}")
    return 0


def run_probes(args) -> int:
    print(summarise(load_probes(args.csv)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="practice-coach", description="Workplace conversation practice prototype")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--data-dir", default=default_data_dir(), type=Path)
    p.add_argument("--retention-days", default=DEFAULT_RETENTION_DAYS, type=int)
    p.add_argument("--scenarios", default=None, help="path to a custom scenarios.json")
    sub = p.add_subparsers(dest="command", required=True)

    pr = sub.add_parser("practice", help="start a practice session")
    pr.add_argument("--record-seconds", type=float, default=15.0)
    pr.add_argument("--whisper-model", default="base.en")
    pr.set_defaults(func=run_practice)

    sub.add_parser("scenarios", help="list scenarios").set_defaults(func=run_scenarios)
    sub.add_parser("history", help="show saved practice").set_defaults(func=run_history)

    d = sub.add_parser("delete", help="delete saved data")
    g = d.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--audio", action="store_true")
    g.add_argument("--id")
    d.set_defaults(func=run_delete)

    pb = sub.add_parser("probes", help="summarise human-rated probe CSV (researchers)")
    pb.add_argument("csv")
    pb.set_defaults(func=run_probes)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
