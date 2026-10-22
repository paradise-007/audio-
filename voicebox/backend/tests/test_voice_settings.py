"""Per-voice settings (speaking speed, reference length): storage and delivery to the engine."""

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from backend.backends import luxtts_backend
from backend.backends.luxtts_backend import (
    LUXTTS_MAX_CHUNK_CHARS,
    LUXTTS_PROMPT_SECONDS,
    LUXTTS_SPEED,
    SPEED_KEY,
    LuxTTSBackend,
)
from backend.database import Base, ProfileSample, VoiceProfile
from backend.database.migrations import _migrate_profiles
from backend.models import VoiceProfileCreate, VoiceSettings
from backend.services import profiles as profiles_service
from backend.services.profiles import create_profile, create_voice_prompt_for_profile, update_profile
from backend.utils.chunked_tts import generate_chunked


@pytest.fixture
def db(monkeypatch, tmp_path):
    from backend import config

    monkeypatch.setattr(config, "get_profiles_dir", lambda: tmp_path)
    temp_dir = tempfile.mkdtemp()
    engine = create_engine(f"sqlite:///{Path(temp_dir) / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()
    shutil.rmtree(temp_dir)


def _run(coro):
    return asyncio.run(coro)


# ── storage ─────────────────────────────────────────────────────────────────

def test_migration_adds_the_column_to_an_existing_profiles_table():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE profiles (id VARCHAR PRIMARY KEY, name VARCHAR)"))

    _migrate_profiles(engine, inspect(engine), {"profiles"})

    assert "voice_settings" in {c["name"] for c in inspect(engine).get_columns("profiles")}


def test_settings_round_trip_and_update_semantics(db):
    created = _run(
        create_profile(
            VoiceProfileCreate(name="John Voice", voice_settings=VoiceSettings(speed=1.1, reference_seconds=20)), db
        )
    )
    assert created.voice_settings == VoiceSettings(speed=1.1, reference_seconds=20)

    # An update that omits the field (older clients) keeps what is stored
    kept = _run(update_profile(created.id, VoiceProfileCreate(name="John Voice"), db))
    assert kept.voice_settings == VoiceSettings(speed=1.1, reference_seconds=20)

    changed = _run(
        update_profile(created.id, VoiceProfileCreate(name="John Voice", voice_settings=VoiceSettings(speed=0.9)), db)
    )
    assert changed.voice_settings.speed == 0.9


def test_profile_without_settings_has_none(db):
    assert _run(create_profile(VoiceProfileCreate(name="Plain"), db)).voice_settings is None


@pytest.mark.parametrize("bad", [{"speed": 2.0}, {"speed": 0.3}, {"reference_seconds": 1}, {"reference_seconds": 40}])
def test_out_of_range_settings_are_rejected(bad):
    with pytest.raises(Exception):
        VoiceSettings(**bad)


# ── delivery to the engine ──────────────────────────────────────────────────

class _FakeBackend:
    def __init__(self):
        self.calls = []

    async def create_voice_prompt(self, audio_path, reference_text, use_cache=True, **kwargs):
        self.calls.append(kwargs)
        return {"prompt_tokens": [[1]]}, False


def _profile_with_sample(db, monkeypatch, settings):
    from backend import config

    profile = _run(create_profile(VoiceProfileCreate(name="V", voice_settings=settings), db))
    db.add(ProfileSample(id="s1", profile_id=profile.id, audio_path="x.wav", reference_text="hello"))
    db.commit()
    monkeypatch.setattr(config, "resolve_storage_path", lambda p: Path(p))
    return profile


@pytest.mark.parametrize("engine,expect", [("luxtts", True), ("chatterbox", False)])
def test_settings_reach_only_the_engine_that_implements_them(db, monkeypatch, engine, expect):
    profile = _profile_with_sample(db, monkeypatch, VoiceSettings(speed=1.2, reference_seconds=10))
    fake = _FakeBackend()
    import backend.backends as backends

    monkeypatch.setattr(backends, "get_tts_backend_for_engine", lambda e: fake)

    prompt = _run(create_voice_prompt_for_profile(profile.id, db, engine=engine))

    if expect:
        assert fake.calls == [{"prompt_seconds": 10}]
        assert prompt[SPEED_KEY] == 1.2
    else:
        assert fake.calls == [{}]
        assert SPEED_KEY not in prompt


def test_cached_prompts_are_not_mutated_by_the_speed_key(db, monkeypatch):
    profile = _profile_with_sample(db, monkeypatch, VoiceSettings(speed=1.2))
    shared = {"prompt_tokens": [[1]]}

    class Backend(_FakeBackend):
        async def create_voice_prompt(self, *a, **k):
            return shared, True

    import backend.backends as backends

    monkeypatch.setattr(backends, "get_tts_backend_for_engine", lambda e: Backend())

    _run(create_voice_prompt_for_profile(profile.id, db, engine="luxtts"))

    assert SPEED_KEY not in shared


# ── LuxTTS backend ──────────────────────────────────────────────────────────

def _generating_backend(prompt_tokens=50, text_tokens=25):
    import torch

    seen = {}

    class Tokenizer:
        def texts_to_token_ids(self, texts):
            return [[0] * text_tokens]

    class Model:
        tokenizer = Tokenizer()

        def generate_speech(self, **kwargs):
            seen.update(kwargs)
            return torch.zeros(1, 480)

    backend = LuxTTSBackend()
    backend.model = Model()
    prompt = {"prompt_tokens": [[0] * prompt_tokens], "prompt_features_lens": torch.tensor([100])}
    return backend, seen, prompt


def test_neutral_speed_is_the_reference_matched_pace():
    backend, seen, prompt = _generating_backend()

    _run(backend.generate("hello", prompt))
    assert seen["speed"] == pytest.approx(LUXTTS_SPEED)

    _run(backend.generate("hello", {**prompt, SPEED_KEY: 1.0}))
    assert seen["speed"] == pytest.approx(LUXTTS_SPEED)
    assert SPEED_KEY not in seen["encode_dict"]  # zipvoice never sees the key


@pytest.mark.parametrize("multiplier", [0.7, 0.85, 1.15, 1.3])
def test_speed_multiplier_makes_the_output_exactly_that_much_faster(multiplier):
    """zipvoice shortens (prompt + speech) by `speed`, so output = (P + T0)/speed - P.

    The backend must invert that so a 1.15 setting really gives speech 1.15x faster.
    """
    backend, seen, prompt = _generating_backend(prompt_tokens=50, text_tokens=25)
    prompt_frames, neutral = 100.0, 100.0 * 25 / 50  # P = 100 frames, T0 = 50 frames

    _run(backend.generate("hello", {**prompt, SPEED_KEY: multiplier}))

    zipvoice_speed = seen["speed"] / LUXTTS_SPEED  # relative to the neutral setting
    output_frames = (prompt_frames + neutral) / zipvoice_speed - prompt_frames
    assert output_frames == pytest.approx(neutral / multiplier)


def test_the_speed_multiplier_is_clamped():
    backend, seen, prompt = _generating_backend()

    _run(backend.generate("hello", {**prompt, SPEED_KEY: 9}))
    clamped = seen["speed"]
    _run(backend.generate("hello", {**prompt, SPEED_KEY: 1.5}))

    assert clamped == pytest.approx(seen["speed"])


def test_speed_falls_back_to_a_plain_multiplier_without_prompt_lengths():
    backend, seen, _ = _generating_backend()

    _run(backend.generate("hello", {"prompt_tokens": [[]], "prompt_features_lens": __import__("torch").tensor([0]), SPEED_KEY: 1.2}))

    assert seen["speed"] == pytest.approx(LUXTTS_SPEED * 1.2)


def test_reference_seconds_set_the_encode_window_and_the_cache_key(monkeypatch):
    backend = LuxTTSBackend()
    backend._device = "cpu"
    backend.model = object()
    encoded, stored_keys = [], []
    backend._encode_prompt = lambda path, text, seconds: encoded.append(seconds) or {"prompt_tokens": [[1]]}
    monkeypatch.setattr(luxtts_backend, "get_cache_key", lambda *a: "k")
    monkeypatch.setattr(luxtts_backend, "get_cached_voice_prompt", lambda key: None)
    monkeypatch.setattr(luxtts_backend, "cache_voice_prompt", lambda key, prompt: stored_keys.append(key))

    _run(backend.create_voice_prompt("a.wav", "t"))
    _run(backend.create_voice_prompt("a.wav", "t", prompt_seconds=8))

    assert encoded == [LUXTTS_PROMPT_SECONDS, 8]
    assert stored_keys == [f"luxtts_v2_p{LUXTTS_PROMPT_SECONDS}_k", "luxtts_v2_p8_k"]  # windows never share a cache entry


# ── chunk cap ───────────────────────────────────────────────────────────────

def test_engine_chunk_limit_overrides_a_larger_request():
    sizes = []

    class Backend:
        max_chunk_chars = 120

        async def generate(self, text, voice_prompt, language, seed, instruct):
            import numpy as np

            sizes.append(len(text))
            return np.zeros(2400, dtype=np.float32), 24000

    text = " ".join(["This is a sentence of moderate length."] * 30)
    _run(generate_chunked(Backend(), text, {}, max_chunk_chars=800))

    assert max(sizes) <= 120 and len(sizes) > 5


def test_luxtts_declares_its_chunk_limit():
    assert LuxTTSBackend.max_chunk_chars == LUXTTS_MAX_CHUNK_CHARS == 500
