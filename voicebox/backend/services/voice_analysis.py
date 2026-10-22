"""
Automatic voice analysis for reference recordings.

Measures what can be measured from the audio itself (pitch, pace, pauses,
loudness, tone, breathiness, recording clarity) and turns it into plain-language
traits plus an editable speaker description. No model download is needed: this
is signal analysis with librosa/numpy.

Scope, stated plainly: the numbers are measurements, the words ("confident",
"warm", "male-sounding") are heuristics over those measurements, and accent,
emotion and word-level emphasis are *not* detected here. Those are carried by
the reference audio itself, which is what the voice engine conditions on.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

ANALYSIS_SR = 16000
MAX_ANALYSIS_SECONDS = 60.0
HOP = 160  # 10 ms
FRAME = 400  # 25 ms
SPEECH_WINDOW_DB = 30.0  # frames within this many dB of the loud level count as speech
MIN_PAUSE_S = 0.15
MAX_PAUSE_S = 2.0
SYLLABLES_PER_WORD = 1.4  # rough English average, only for the no-transcript fallback


def _label(value: float, bands: list[tuple[float, str]], top: str) -> str:
    """Return the label of the first band whose upper bound exceeds ``value``."""
    for upper, name in bands:
        if value < upper:
            return name
    return top


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """(start, end) index pairs of consecutive True values."""
    if mask.size == 0:
        return []
    padded = np.concatenate(([False], mask, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return list(zip(edges[::2], edges[1::2]))


def _hnr_db(y: np.ndarray, f0: np.ndarray, voiced: np.ndarray, hop: int, sr: int) -> Optional[float]:
    """Median harmonics-to-noise ratio over voiced frames (autocorrelation method)."""
    values = []
    win = 1024
    for i in np.flatnonzero(voiced)[::3]:  # every 3rd voiced frame is plenty and 3x cheaper
        start = i * hop
        seg = y[start : start + win]
        if len(seg) < win or not np.isfinite(f0[i]):
            continue
        seg = seg - seg.mean()
        ac = np.correlate(seg, seg, mode="full")[win - 1 :]
        if ac[0] <= 1e-9:
            continue
        lag = int(round(sr / f0[i]))
        lo, hi = max(lag - 3, 1), min(lag + 3, win - 1)
        r = float(np.max(ac[lo : hi + 1]) / ac[0])
        r = min(max(r, 0.01), 0.999)
        values.append(10 * np.log10(r / (1 - r)))
    return float(np.median(values)) if values else None


def analyze_voice(audio_path: str, transcript: Optional[str] = None) -> dict:
    """Analyze a reference recording and return measurements, traits and a description."""
    import librosa

    y, sr = librosa.load(audio_path, sr=ANALYSIS_SR, mono=True, duration=MAX_ANALYSIS_SECONDS)
    duration = len(y) / sr
    if duration < 1.0 or not np.any(np.abs(y) > 1e-4):
        raise ValueError("The recording is empty or too short to analyze.")

    # ── Loudness / speech activity ──────────────────────────────────────────
    rms = librosa.feature.rms(y=y, frame_length=FRAME, hop_length=HOP)[0]
    db = 20 * np.log10(rms + 1e-8)
    loud_db = float(np.percentile(db, 95))
    speech = db > loud_db - SPEECH_WINDOW_DB
    speech_runs = _runs(speech)
    if not speech_runs:
        raise ValueError("No speech was detected in the recording.")
    first, last = speech_runs[0][0], speech_runs[-1][1]
    span_s = (last - first) * HOP / sr
    speech_s = float(np.sum(speech)) * HOP / sr

    # Pauses = silent gaps between speech inside the spoken span
    pauses = []
    for (_, end), (start, _) in zip(speech_runs, speech_runs[1:]):
        gap = (start - end) * HOP / sr
        if MIN_PAUSE_S <= gap <= MAX_PAUSE_S:
            pauses.append(gap)
    pause_count = len(pauses)
    pause_ms = 1000 * float(np.mean(pauses)) if pauses else 0.0
    pauses_per_min = pause_count / max(span_s, 1.0) * 60

    active_db = db[speech]
    loudness_var = float(np.std(active_db))
    level_dbfs = float(np.mean(20 * np.log10(rms[speech] + 1e-8)))
    noise_floor = float(np.percentile(db, 5))
    snr = float(np.mean(active_db) - noise_floor)
    clipping_pct = float(np.mean(np.abs(y) > 0.99) * 100)

    # ── Speaking rate ───────────────────────────────────────────────────────
    words = len(transcript.split()) if transcript and transcript.strip() else 0
    if words >= 3 and span_s > 1.0:
        wpm = words / span_s * 60
        rate_source = "transcript"
    else:
        onset = librosa.onset.onset_detect(y=y, sr=sr, hop_length=HOP, units="time")
        syllables_per_s = len(onset) / max(span_s, 1.0)
        wpm = syllables_per_s / SYLLABLES_PER_WORD * 60
        rate_source = "estimated"

    # ── Pitch ───────────────────────────────────────────────────────────────
    pyin_hop = 320  # 20 ms: half the frames of a 10 ms hop, same pitch statistics, ~2x faster
    f0, voiced, _ = librosa.pyin(y, fmin=60, fmax=400, sr=sr, frame_length=1024, hop_length=pyin_hop, n_thresholds=50)
    f0_voiced = f0[voiced & np.isfinite(f0)]
    if f0_voiced.size < 10:
        raise ValueError("Not enough voiced speech to measure pitch. Try a clearer recording.")
    pitch_hz = float(np.median(f0_voiced))
    semitones = 12 * np.log2(f0_voiced / 100.0)
    pitch_var_st = float(np.std(semitones))
    pitch_range_st = float(np.percentile(semitones, 90) - np.percentile(semitones, 10))

    # ── Tone / timbre ───────────────────────────────────────────────────────
    S = np.abs(librosa.stft(y, n_fft=1024, hop_length=HOP)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)
    cols = np.flatnonzero(speech[: S.shape[1]])
    band = S[:, cols].sum(axis=1)
    total = float(band.sum()) + 1e-12
    centroid_hz = float((freqs * band).sum() / total)
    low_ratio = float(band[freqs < 500].sum() / total)
    # Spectral tilt: energy at 2-6 kHz relative to 80 Hz-1 kHz. Lower = darker/warmer.
    low_band = float(band[(freqs >= 80) & (freqs < 1000)].sum()) + 1e-12
    high_band = float(band[(freqs >= 2000) & (freqs < 6000)].sum()) + 1e-12
    tilt_db = float(10 * np.log10(high_band / low_band))
    hnr = _hnr_db(y, f0, voiced & np.isfinite(f0), pyin_hop, sr)

    # ── Labels (heuristics over the measurements above) ─────────────────────
    voice_type = "male-sounding" if pitch_hz < 160 else "female-sounding" if pitch_hz >= 185 else "mid-range"
    pitch_label = _label(
        pitch_hz,
        [(110, "very deep"), (145, "deep"), (185, "medium-low"), (235, "medium"), (285, "medium-high")],
        "high",
    )
    # Bands were set from real recordings (-26 dB dark voice ... -12 dB broadcast voice).
    tone = _label(tilt_db, [(-20, "warm"), (-10, "balanced")], "bright")
    # Noise lowers the harmonics-to-noise ratio, so breathiness is only judged on clean recordings.
    if hnr is None or snr < 28:
        breathiness = None
    else:
        breathiness = "clear" if hnr >= 14 else "slightly breathy" if hnr >= 9 else "breathy"
    rate_label = _label(wpm, [(120, "slow"), (160, "medium"), (195, "brisk")], "fast")
    pause_label = _label(pauses_per_min, [(3, "few pauses"), (14, "natural pauses")], "frequent pauses")
    expressiveness = _label(
        pitch_var_st, [(1.5, "fairly steady pitch"), (3.2, "natural intonation")], "expressive intonation"
    )
    energy = _label(level_dbfs, [(-34, "soft volume"), (-24, "moderate energy")], "strong energy")
    clarity = _label(snr, [(20, "noisy"), (30, "some background noise"), (42, "clean")], "very clean")

    if pauses_per_min > 14 and level_dbfs < -30:
        delivery = "quiet, measured"
    elif pitch_var_st > 3.2 or loudness_var > 9.5:
        delivery = "expressive, engaging"
    elif level_dbfs >= -26 and pauses_per_min <= 14 and pitch_var_st <= 3.2:
        delivery = "confident, authoritative"
    elif level_dbfs < -32 or wpm < 120:
        delivery = "calm, gentle"
    else:
        delivery = "calm, steady"

    voice_phrase = {
        "male-sounding": "male-sounding",
        "female-sounding": "female-sounding",
        "mid-range": "mid-range",
    }[voice_type]
    wpm_text = f"about {round(wpm / 5) * 5:.0f} words per minute"
    clarity_phrase = {
        "very clean": "very clean recording",
        "clean": "clear, clean recording",
        "some background noise": "some background noise",
        "noisy": "noticeable background noise",
    }[clarity]
    description = (
        f"{delivery.capitalize()} {tone} {voice_phrase} voice with a {pitch_label} pitch, "
        f"{clarity_phrase}, {rate_label} speaking speed ({wpm_text}), {pause_label}, "
        f"{expressiveness}, and {energy}."
    )

    warnings = []
    if duration < 8:
        warnings.append("Short recording: 10–30 seconds of clear speech gives the closest voice match.")
    if snr < 20:
        warnings.append("Background noise is high; a quieter recording will sound closer to the voice.")
    if clipping_pct > 0.5:
        warnings.append("The recording is clipping (too loud); lower the input level and re-record.")
    if rate_source == "estimated":
        warnings.append("Speaking speed is estimated; add the transcript for an exact figure.")

    traits = [
        {"key": "voice_type", "label": "Voice type", "value": f"{voice_phrase.capitalize()}, {pitch_label} pitch (~{pitch_hz:.0f} Hz)"},
        {"key": "speaking_speed", "label": "Speaking speed", "value": f"{rate_label.capitalize()} (~{wpm:.0f} words/min)"},
        {"key": "pitch", "label": "Pitch movement", "value": f"{expressiveness.capitalize()} ({pitch_range_st:.1f} semitone range)"},
        {"key": "tone", "label": "Tone", "value": tone.capitalize() + (f", {breathiness}" if breathiness else "")},
        {"key": "energy", "label": "Energy", "value": f"{energy.capitalize()}, {'dynamic' if loudness_var > 8 else 'even'} loudness"},
        {"key": "pauses", "label": "Pauses", "value": f"{pause_label.capitalize()} (avg {pause_ms:.0f} ms)" if pause_count else pause_label.capitalize()},
        {"key": "delivery", "label": "Delivery", "value": delivery.capitalize()},
        {"key": "clarity", "label": "Recording clarity", "value": clarity.capitalize()},
    ]

    return {
        "duration_s": round(duration, 1),
        "speech_s": round(speech_s, 1),
        "voice": {
            "type": voice_type,
            "pitch_hz": round(pitch_hz, 1),
            "pitch_label": pitch_label,
            "pitch_range_st": round(pitch_range_st, 1),
            "tone": tone,
            "brightness_hz": round(centroid_hz),
            "spectral_tilt_db": round(tilt_db, 1),
            "low_frequency_ratio": round(low_ratio, 2),
            "breathiness": breathiness,
            "hnr_db": None if hnr is None else round(hnr, 1),
        },
        "speaking": {
            "words_per_minute": round(wpm),
            "rate_label": rate_label,
            "rate_source": rate_source,
            "pause_count": pause_count,
            "pause_ms_avg": round(pause_ms),
            "pauses_per_minute": round(pauses_per_min, 1),
            "pause_label": pause_label,
            "pitch_variation_st": round(pitch_var_st, 1),
            "expressiveness": expressiveness,
            "loudness_variation_db": round(loudness_var, 1),
            "level_dbfs": round(level_dbfs, 1),
            "energy": energy,
            "delivery": delivery,
        },
        "quality": {
            "snr_db": round(snr, 1),
            "clarity": clarity,
            "clipping_percent": round(clipping_pct, 2),
        },
        "traits": traits,
        "description": description,
        "warnings": warnings,
        "limits": (
            "Accent, pronunciation and emphasis are not measured here: the voice engine "
            "copies them directly from the recording."
        ),
    }
