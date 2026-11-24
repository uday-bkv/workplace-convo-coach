import time
from pathlib import Path

import pytest

from practice_coach import cli
from practice_coach.evaluation import Probe, inter_rater_agreement, load_probes, pnd, summarise
from practice_coach.rubric import evaluate
from practice_coach.scenarios import ScenarioError, get_scenario, load_scenarios
from practice_coach.storage import PracticeStore, new_record

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def scenarios():
    return load_scenarios()


# --- scenarios -------------------------------------------------------------
def test_bundled_scenarios_load(scenarios):
    assert len(scenarios) >= 4
    assert get_scenario(scenarios, "deadline_stress").title


def test_bad_scenario_rejected(tmp_path):
    bad = tmp_path / "s.json"
    bad.write_text('{"scenarios": [{"id": "x", "title": "t", "setting": "s", "prompt": "p", "goal": "g", "criteria": {"acknowledge": ["a"]}}]}')
    with pytest.raises(ScenarioError):
        load_scenarios(bad)


# --- rubric ----------------------------------------------------------------
def test_full_response_meets_all(scenarios):
    sc = get_scenario(scenarios, "deadline_stress")
    fb = evaluate(sc, "That sounds really stressful. Can I help with part of the report?")
    assert fb.met_count == 3
    assert fb.suggestions == []


def test_partial_response_gets_optional_suggestions(scenarios):
    sc = get_scenario(scenarios, "deadline_stress")
    fb = evaluate(sc, "Okay.")
    assert fb.met_count == 0
    assert len(fb.suggestions) == 3
    assert all(s.startswith(("If you like", "One option", "You might")) for s in fb.suggestions)
    assert fb.examples


def test_curly_apostrophe_and_prefix_cue(scenarios):
    sc = get_scenario(scenarios, "good_news")
    fb = evaluate(sc, "Congratulations — that’s exciting about the client!")
    met = {r.key: r.met for r in fb.results}
    assert met["acknowledge"] and met["respond_to_concern"]


def test_no_partial_word_false_match(scenarios):
    sc = get_scenario(scenarios, "deadline_stress")
    fb = evaluate(sc, "whelp")  # must not match "help"
    assert not fb.results[2].met


def test_feedback_text_never_mentions_emotion_diagnosis(scenarios):
    sc = get_scenario(scenarios, "feedback_from_manager")
    text = evaluate(sc, "ok").as_text().lower()
    for banned in ("you feel", "you seem", "autis", "diagnos", "accent score"):
        assert banned not in text


# --- storage ---------------------------------------------------------------
def test_storage_encrypts_and_roundtrips(tmp_path):
    store = PracticeStore(tmp_path / "d")
    rec = new_record("deadline_stress", "secret reply text", "speech", {"acknowledge": True})
    store.save(rec, audio_bytes=b"RIFFfakeaudio")
    raw = b"".join(p.read_bytes() for p in (tmp_path / "d").rglob("*.bin"))
    assert b"secret reply text" not in raw and b"RIFFfakeaudio" not in raw
    [loaded] = store.list_records()
    assert loaded.response_text == "secret reply text" and loaded.has_audio
    assert store.load_audio(rec.id) == b"RIFFfakeaudio"
    assert oct((tmp_path / "d" / "key").stat().st_mode)[-3:] == "600"


def test_retention_purges_old(tmp_path):
    store = PracticeStore(tmp_path / "d", retention_days=1)
    old = new_record("x", "old", "text", {})
    old.created_at = time.time() - 3 * 86400
    store.save(old)
    store.save(new_record("x", "new", "text", {}))
    assert store.purge_expired() == 1
    assert [r.response_text for r in store.list_records()] == ["new"]


def test_delete_all_and_audio_only(tmp_path):
    store = PracticeStore(tmp_path / "d")
    store.save(new_record("x", "a", "speech", {}), audio_bytes=b"abc")
    assert store.delete_audio_only() == 1
    assert len(store.list_records()) == 1
    store.delete_all()
    assert not (tmp_path / "d").exists()


# --- evaluation ------------------------------------------------------------
def test_pnd_and_agreement():
    assert pnd([1, 2, 1], [4, 5, 2]) == pytest.approx(66.666, rel=1e-3)
    assert pnd([], [1]) is None
    probes = [Probe("P1", 1, "baseline", "R1", 2), Probe("P1", 1, "baseline", "R2", 2),
              Probe("P1", 2, "baseline", "R1", 1), Probe("P1", 2, "baseline", "R2", 3)]
    assert inter_rater_agreement(probes) == 50.0


def test_example_csv_summary():
    out = summarise(load_probes(ROOT / "examples" / "probes_example.csv"))
    assert "Participants: 3" in out and "P3" in out


# --- CLI -------------------------------------------------------------------
def test_cli_text_session_saves_and_deletes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.speech, "speech_available", lambda: (False, "test"))
    answers = iter(["y", "1", "That sounds hard. Can I help with the report?", "q"])
    args = cli.build_parser().parse_args(["--data-dir", str(tmp_path / "d"), "practice"])
    assert cli.run_practice(args, ask=lambda _: next(answers)) == 0
    out = capsys.readouterr().out
    assert "[x] Acknowledged" in out
    assert cli.main(["--data-dir", str(tmp_path / "d"), "history"]) == 0
    assert "deadline_stress" in capsys.readouterr().out
    assert cli.main(["--data-dir", str(tmp_path / "d"), "delete", "--all"]) == 0
    assert not (tmp_path / "d").exists()


def test_cli_no_consent_saves_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.speech, "speech_available", lambda: (False, "test"))
    answers = iter(["n", "2", "Congratulations!", "q"])
    args = cli.build_parser().parse_args(["--data-dir", str(tmp_path / "d"), "practice"])
    cli.run_practice(args, ask=lambda _: next(answers))
    assert not (tmp_path / "d").exists()
