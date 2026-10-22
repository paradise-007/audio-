"""Voice analysis: measurements on synthetic speech-like signals with known properties."""

import numpy as np
import pytest
import soundfile as sf

from backend.services.voice_analysis import analyze_voice

SR = 16000


def _speech_like(f0, seconds=8.0, gaps=((2.5, 3.0), (5.0, 5.6)), noise=0.0, level=0.3, seed=0):
    """Harmonic 'voice' with syllable-like gating, silent gaps, and optional noise."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * SR)) / SR
    voice = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 8))
    gate = (np.sin(2 * np.pi * 4 * t) > -0.4).astype(float)
    y = level * voice / np.max(np.abs(voice)) * gate
    for start, end in gaps:
        y[int(start * SR) : int(end * SR)] = 0
    return (y + noise * rng.standard_normal(len(t))).astype(np.float32)


def _write(tmp_path, y, name="ref.wav"):
    path = tmp_path / name
    sf.write(path, y, SR)
    return str(path)


def test_low_pitch_is_male_sounding_and_pitch_is_accurate(tmp_path):
    result = analyze_voice(_write(tmp_path, _speech_like(120)))

    assert result["voice"]["type"] == "male-sounding"
    assert result["voice"]["pitch_hz"] == pytest.approx(120, rel=0.05)


def test_high_pitch_is_female_sounding(tmp_path):
    result = analyze_voice(_write(tmp_path, _speech_like(220)))

    assert result["voice"]["type"] == "female-sounding"
    assert result["voice"]["pitch_hz"] == pytest.approx(220, rel=0.05)


def test_pauses_are_counted_and_timed(tmp_path):
    result = analyze_voice(_write(tmp_path, _speech_like(150)))["speaking"]

    assert result["pause_count"] >= 2
    # gaps of 0.5 s and 0.6 s, plus ~0.1 s of gate silence either side
    assert 400 <= result["pause_ms_avg"] <= 900


def test_transcript_gives_exact_words_per_minute(tmp_path):
    path = _write(tmp_path, _speech_like(150))
    words = " ".join(["word"] * 20)

    with_text = analyze_voice(path, words)["speaking"]
    without_text = analyze_voice(path)["speaking"]

    assert with_text["rate_source"] == "transcript"
    assert without_text["rate_source"] == "estimated"
    # 20 words over the ~7 s spoken span
    assert with_text["words_per_minute"] == pytest.approx(20 / 7.3 * 60, rel=0.15)


def test_noise_lowers_the_clarity_rating(tmp_path):
    clean = analyze_voice(_write(tmp_path, _speech_like(150), "clean.wav"))["quality"]
    noisy = analyze_voice(_write(tmp_path, _speech_like(150, noise=0.08), "noisy.wav"))["quality"]

    assert noisy["snr_db"] < clean["snr_db"] - 10
    assert any("noise" in w.lower() for w in analyze_voice(_write(tmp_path, _speech_like(150, noise=0.08), "n2.wav"))["warnings"])


def test_description_and_traits_are_ready_for_the_ui(tmp_path):
    result = analyze_voice(_write(tmp_path, _speech_like(120)), "hello there my friend how are you today")

    assert result["description"].endswith(".")
    assert "male-sounding" in result["description"]
    assert [t["key"] for t in result["traits"]] == [
        "voice_type",
        "speaking_speed",
        "pitch",
        "tone",
        "energy",
        "pauses",
        "delivery",
        "clarity",
    ]
    assert all(t["label"] and t["value"] for t in result["traits"])


def test_short_clip_warns(tmp_path):
    result = analyze_voice(_write(tmp_path, _speech_like(150, seconds=4, gaps=())))

    assert any("Short recording" in w for w in result["warnings"])


def test_silence_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        analyze_voice(_write(tmp_path, np.zeros(SR * 3, dtype=np.float32)))


def test_analyze_endpoint_returns_the_analysis(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.routes import profiles as profiles_routes

    app = FastAPI()
    app.include_router(profiles_routes.router)
    client = TestClient(app)
    path = _write(tmp_path, _speech_like(120))

    with open(path, "rb") as f:
        response = client.post(
            "/profiles/analyze", files={"file": ("ref.wav", f, "audio/wav")}, data={"transcript": "one two three four five six"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["voice"]["type"] == "male-sounding"
    assert body["description"]
    assert body["limits"]


def test_analyze_endpoint_rejects_silence(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.routes import profiles as profiles_routes

    app = FastAPI()
    app.include_router(profiles_routes.router)
    path = _write(tmp_path, np.zeros(SR * 3, dtype=np.float32))

    with open(path, "rb") as f:
        response = TestClient(app).post("/profiles/analyze", files={"file": ("ref.wav", f, "audio/wav")})

    assert response.status_code == 400
