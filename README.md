# Workplace Conversation Practice Coach (learning prototype)

A small Python prototype based on **Case 01**: a conversational training tool where
autistic interns practise replies to workplace scenarios and get immediate feedback.
It is modelled on the published Noora study, but it is **not** Noora and does not
copy how Noora works.

> **Prototype for learning only.** This is not a medical device and has not been
> validated. Anything used with participants needs co-design, ethics approval and,
> where relevant, clinical or regulatory review.

## What it does

| Case-study element | How the prototype handles it |
|---|---|
| Person practises a workplace prompt | 4 starter scenarios in `src/practice_coach/data/scenarios.json` |
| Verbal response | Optional, opt-in microphone capture with local Whisper (`faster-whisper`). Typing is always available |
| Real-time AI feedback | A **bounded rubric** (acknowledge → connect to their concern → offer a next step) that uses cue phrases from each scenario. Suggestions are optional, and example replies are shown |
| Expert check outside the app | `practice-coach probes` summarises **human-rated** probe scores across baseline, intervention, generalization and retention, with PND and inter-rater agreement |
| Privacy | Encrypted storage (Fernet), a 14-day retention window, `delete --all` / `--audio` / `--id`, and audio is discarded unless the user separately chooses to keep it |

**What the tool never does:** it doesn't score accent, voice, fluency or speaking
style. It doesn't diagnose anything or claim to know how a person feels.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # text mode
pip install -e ".[dev,speech]"     # adds microphone + local Whisper
```

## Use

```bash
practice-coach practice                 # interactive session (asks for consent first)
practice-coach scenarios                # list scenarios
practice-coach history                  # view your saved practice
practice-coach delete --all             # remove all records, audio and the key
practice-coach probes examples/probes_example.csv   # researcher summary
```

Options: `--data-dir`, `--retention-days`, `--scenarios my_scenarios.json`,
`practice --record-seconds 20 --whisper-model small.en`.

Run the tests with `pytest`.

## Project layout

```
src/practice_coach/
  scenarios.py    load + validate the scenario library
  rubric.py       transparent, bounded feedback (wording only)
  speech.py       opt-in recording + local transcription, with transcript correction
  storage.py      encrypted short-retention store, user-controlled deletion
  evaluation.py   single-case probe analysis (phase means, PND, agreement)
  cli.py          command-line app
  data/scenarios.json
examples/probes_example.csv   SYNTHETIC demo data, not study results
tests/test_core.py
```

## Next steps (from the implementation guide)

1. **Co-design the scenarios.** The bundled scenarios and cue phrases are
   developer-written drafts (`_review_status` in the JSON). Replace them with
   scenarios co-designed with autistic adults and employment specialists.
2. **Keep the coach bounded.** Add scenarios to the JSON rather than adding
   open-ended advice. If you add an LLM later, limit it to rephrasing the rubric
   output.
3. **Speech access.** Recording only starts on request and shows when the microphone is on and when
   audio is being processed. A transcript correction step and typed input are always available.
4. **Evaluate with people.** With ethics approval, compare the app's feedback against blinded human
   ratings in realistic probes. Report sample size and limitations, as the case
   study does (3 participants, no long-term employment outcomes).
