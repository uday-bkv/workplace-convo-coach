"""Bounded conversation-practice workflow demo; not a clinical or employment tool."""

import argparse
from pathlib import Path


def get_text(args: argparse.Namespace) -> str:
    if args.audio:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise SystemExit("For --audio, install faster-whisper: pip install faster-whisper") from exc
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(args.audio))
        return " ".join(segment.text.strip() for segment in segments).strip()
    return args.text or input("Your spoken-reply transcript (or type a reply): ").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Practice a workplace conversation (demo only).")
    parser.add_argument("--text", help="Transcript of a practice response")
    parser.add_argument("--audio", type=Path, help="Local audio file to transcribe with Whisper")
    parser.add_argument("--speak", action="store_true", help="Read the prompt and response using local TTS")
    args = parser.parse_args()
    if args.audio and not args.audio.is_file():
        parser.error(f"Audio file not found: {args.audio}")

    prompt = "A coworker says: 'I am overwhelmed by the changes to today's schedule.'"
    print(prompt)
    if args.speak:
        try:
            import pyttsx3
        except ImportError as exc:
            raise SystemExit("For --speak, install pyttsx3: pip install pyttsx3") from exc
        engine = pyttsx3.init()
        engine.say(prompt)
        engine.runAndWait()

    reply = get_text(args)
    print(f"\nTranscript: {reply}")
    print("\nOptional reflection: Did you acknowledge what your coworker said, and would you like to ask what support they need?")
    print("This demo does not grade, diagnose, or judge a person's communication.")


if __name__ == "__main__":
    main()
