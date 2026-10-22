"""LuxTTS reference prompts: use the vetted transcript, cut at a pause, never feed Whisper garbage."""

import sys
import types

import numpy as np
import pytest

from backend.backends import luxtts_backend as lb
from backend.backends.luxtts_backend import LuxTTSBackend, is_plausible_transcript, plan_prompt

FPS = 100


def _mask(total_s, speech_ranges):
    mask = np.zeros(int(total_s * FPS), dtype=bool)
    for a, b in speech_ranges:
        mask[int(a * FPS) : int(b * FPS)] = True
    return mask


def _words(n):
    return " ".join(f"word{i}" for i in range(n))


# ── plausibility ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "text,speech_s,ok",
    [
        (_words(40), 15, True),  # 160 wpm
        (_words(5), 15, False),  # a placeholder against 15 s of speech
        (_words(2), 15, False),  # too few words to judge
        (_words(200), 15, False),  # 800 wpm: a looping transcript
        ("", 15, False),
        (_words(40), 0.5, False),  # no speech to compare against
    ],
)
def test_transcript_plausibility(text, speech_s, ok):
    assert is_plausible_transcript(text, speech_s) is ok


# ── planning ────────────────────────────────────────────────────────────────

def test_whole_recording_uses_the_whole_transcript():
    speech = _mask(20, [(0.5, 19.5)])

    plan = plan_prompt(speech, 20.0, _words(55), seconds=25)

    assert plan.seconds == 20.0
    assert plan.text == _words(55)


def test_longer_recording_is_cut_at_a_pause_near_the_target():
    # speech 0-14 s, pause 14.0-14.6 s, speech 14.6-30 s
    speech = _mask(30, [(0.0, 14.0), (14.6, 30.0)])

    plan = plan_prompt(speech, 30.0, _words(90), seconds=15)

    assert 14.0 <= plan.seconds <= 14.6  # inside the pause, so no word is split
    # transcript cut in proportion to the speech before the pause (14 of 29.4 s)
    assert len(plan.text.split()) == pytest.approx(90 * 14 / 29.4, abs=1)
    assert plan.text == " ".join(_words(90).split()[: len(plan.text.split())])


def test_without_a_pause_the_cut_is_exactly_the_requested_seconds():
    speech = _mask(30, [(0.0, 30.0)])

    assert plan_prompt(speech, 30.0, _words(90), seconds=15).seconds == 15.0


def test_implausible_transcript_defers_to_whisper():
    speech = _mask(20, [(0.5, 19.5)])

    plan = plan_prompt(speech, 20.0, "Reference audio for voice cloning", seconds=25)

    assert plan.text is None
    assert plan.seconds == 20.0


def test_missing_transcript_defers_to_whisper():
    assert plan_prompt(_mask(10, [(0, 10)]), 10.0, None, seconds=15).text is None


# ── encoding ────────────────────────────────────────────────────────────────

class _Model:
    device = "cpu"
    tokenizer = feature_extractor = object()

    def __init__(self, whisper_text):
        self.whisper_text = whisper_text
        self.whisper_calls = []

    def transcriber(self, wav, **kwargs):
        self.whisper_calls.append((len(wav), kwargs))
        return {"text": self.whisper_text}


@pytest.fixture
def fake_zipvoice(monkeypatch):
    """Stand in for zipvoice's process_audio (records the transcript and window) and for audio loading."""
    seen = {}

    def process_audio(path, transcriber, tokenizer, extractor, device, target_rms, duration):
        seen["duration"] = duration
        seen["text"] = transcriber(np.zeros(16000))["text"]
        return [[1, 2]], 5, "features", 0.01

    module = types.ModuleType("zipvoice.modeling_utils")
    module.process_audio = process_audio
    monkeypatch.setitem(sys.modules, "zipvoice.modeling_utils", module)
    monkeypatch.setattr(lb, "_speech_activity", lambda path: (_mask(20, [(0.5, 19.5)]), 20.0))
    monkeypatch.setattr("librosa.load", lambda *a, **k: (np.zeros(16000 * 20, dtype=np.float32), 16000))
    return seen


def _backend(model):
    backend = LuxTTSBackend()
    backend.model = model
    return backend


def test_a_good_transcript_is_used_and_whisper_is_not_consulted(fake_zipvoice):
    model = _Model("never used")

    prompt = _backend(model)._encode_prompt("a.wav", _words(55), seconds=25)  # 20 s recording: used whole

    assert fake_zipvoice["text"] == _words(55)
    assert fake_zipvoice["duration"] == 20.0
    assert model.whisper_calls == []
    assert list(prompt) == ["prompt_tokens", "prompt_features_lens", "prompt_features", "prompt_rms"]  # zipvoice's order


def test_placeholder_text_falls_back_to_whisper_on_the_whole_recording(fake_zipvoice):
    model = _Model(_words(50))

    _backend(model)._encode_prompt("a.wav", "Reference audio for voice cloning", seconds=15)

    assert len(model.whisper_calls) == 1
    samples, kwargs = model.whisper_calls[0]
    assert samples == 16000 * 20  # the whole 20 s recording, never a window
    assert kwargs["generate_kwargs"]["language"] == "en"
    # the transcript is cut together with the audio (15 s of a 19 s span of speech)
    assert fake_zipvoice["duration"] == 15.0
    assert fake_zipvoice["text"] == " ".join(_words(50).split()[: len(fake_zipvoice["text"].split())])
    assert 35 <= len(fake_zipvoice["text"].split()) <= 40


def test_a_looping_whisper_transcript_is_refused_with_a_useful_message(fake_zipvoice):
    model = _Model(_words(2600))  # hallucination loop

    with pytest.raises(ValueError, match="Reference Text"):
        _backend(model)._encode_prompt("a.wav", "x", seconds=15)
