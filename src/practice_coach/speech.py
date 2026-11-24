"""Optional, opt-in speech input.

Recording uses `sounddevice` and transcription uses `faster-whisper` (a local,
on-device Whisper implementation, so audio never leaves the machine). Both are
optional extras: `pip install -e .[speech]`. Without them the app runs in
text-only mode, which is always available as an alternative to speaking.

The transcript is shown to the person and can be corrected before feedback is
given. Only the words are used; nothing about accent or speaking style is scored.
"""

from __future__ import annotations

import io
import wave

SAMPLE_RATE = 16000


class SpeechUnavailable(RuntimeError):
    pass


def speech_available() -> tuple[bool, str]:
    try:
        import sounddevice  # noqa: F401
    except Exception as exc:  # pragma: no cover - depends on host
        return False, f"microphone library not available ({exc.__class__.__name__})"
    try:
        import faster_whisper  # noqa: F401
    except Exception as exc:  # pragma: no cover
        return False, f"speech recognizer not installed ({exc.__class__.__name__})"
    return True, "ok"


def record(seconds: float = 15.0) -> bytes:
    """Record from the default microphone and return WAV bytes."""
    try:
        import numpy as np
        import sounddevice as sd
    except Exception as exc:  # pragma: no cover
        raise SpeechUnavailable(str(exc)) from exc
    print(f"[RECORDING - microphone is ON for up to {seconds:.0f}s. Press Ctrl+C to stop early.]")
    frames = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    try:
        sd.wait()
    except KeyboardInterrupt:
        sd.stop()
    print("[Microphone is OFF.]")
    audio = np.asarray(frames).flatten()
    # Trim trailing silence left by an early stop.
    nonzero = np.nonzero(audio)[0]
    audio = audio[: nonzero[-1] + 1] if nonzero.size else audio[:0]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(audio.tobytes())
    return buf.getvalue()


_model = None


def transcribe(wav_bytes: bytes, model_size: str = "base.en") -> str:
    """Transcribe WAV bytes locally with faster-whisper."""
    global _model
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:  # pragma: no cover
        raise SpeechUnavailable(str(exc)) from exc
    print("[Processing audio on this computer...]")
    if _model is None:
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = _model.transcribe(io.BytesIO(wav_bytes), language="en")
    return " ".join(seg.text.strip() for seg in segments).strip()
