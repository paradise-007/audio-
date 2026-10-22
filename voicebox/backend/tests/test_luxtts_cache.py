"""LuxTTS model reuse: cache detection, device choice, and Whisper selection.

zipvoice loads a Whisper ASR model next to the LuxTTS weights. If only the
LuxTTS repo were checked, a cache holding just that repo would flip the loader
into offline mode and the load would fail instead of fetching the missing
Whisper files. We pin Whisper to whisper-base on every device so there is one
cache entry to check and nothing extra to download on the CPU path.
"""

import asyncio

import pytest

from backend.backends import get_model_config
from backend.backends import luxtts_backend
from backend.backends.luxtts_backend import (
    LUXTTS_HF_REPO,
    LUXTTS_SPEED,
    LUXTTS_WHISPER_REPO,
    LuxTTSBackend,
)


def _fake_cached_repo(cache_dir, repo, weight_name):
    snapshot = cache_dir / ("models--" + repo.replace("/", "--")) / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    (snapshot / weight_name).write_bytes(b"weights")


@pytest.fixture
def hf_cache(tmp_path, monkeypatch):
    import huggingface_hub.constants as hf_constants

    monkeypatch.setattr(hf_constants, "HF_HUB_CACHE", str(tmp_path))
    return tmp_path


def test_luxtts_weights_alone_are_not_enough(hf_cache):
    _fake_cached_repo(hf_cache, LUXTTS_HF_REPO, "model.pt")

    assert LuxTTSBackend()._is_model_cached() is False


def test_whisper_alone_is_not_enough(hf_cache):
    _fake_cached_repo(hf_cache, LUXTTS_WHISPER_REPO, "model.safetensors")

    assert LuxTTSBackend()._is_model_cached() is False


def test_cached_once_both_repos_present(hf_cache):
    _fake_cached_repo(hf_cache, LUXTTS_HF_REPO, "model.pt")
    _fake_cached_repo(hf_cache, LUXTTS_WHISPER_REPO, "model.safetensors")

    assert LuxTTSBackend()._is_model_cached() is True


def test_model_config_lists_the_whisper_repo():
    config = get_model_config("luxtts")

    assert config.hf_repo_id == LUXTTS_HF_REPO
    assert config.aux_hf_repo_ids == (LUXTTS_WHISPER_REPO,)


def test_mps_is_never_selected(monkeypatch):
    """zipvoice's torch path crashes on MPS (autocast / complex ops); CPU/ONNX is used instead."""
    import torch

    monkeypatch.delenv("VOICEBOX_FORCE_CPU", raising=False)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)

    assert LuxTTSBackend()._get_device() == "cpu"


def test_cpu_loader_uses_whisper_base_and_restores_pipeline(monkeypatch):
    import zipvoice.modeling_utils as zipvoice_utils

    calls = []

    def fake_pipeline(task, *args, model=None, **kwargs):
        calls.append(model)
        return object()

    monkeypatch.setattr(zipvoice_utils, "pipeline", fake_pipeline)

    with luxtts_backend._use_whisper_base_on_cpu():
        zipvoice_utils.pipeline("automatic-speech-recognition", model="openai/whisper-tiny", device="cpu")
        zipvoice_utils.pipeline("automatic-speech-recognition", model="some/other-model")

    assert calls == [LUXTTS_WHISPER_REPO, "some/other-model"]
    assert zipvoice_utils.pipeline is fake_pipeline


def test_generate_uses_tuned_speed():
    import torch

    seen = {}

    class FakeModel:
        def generate_speech(self, **kwargs):
            seen.update(kwargs)
            return torch.zeros(1, 480)

    backend = LuxTTSBackend()
    backend.model = FakeModel()

    audio, sample_rate = asyncio.run(backend.generate("hello", {"prompt": 1}))  # no per-voice speed set

    assert seen["speed"] == LUXTTS_SPEED
    assert sample_rate == 48000
    assert audio.shape == (480,)


# ── cached voice prompts must follow the active device ──────────────────────

requires_mps = pytest.mark.skipif(
    not __import__("torch").backends.mps.is_available(), reason="needs an MPS device"
)


def test_prompt_to_device_keeps_non_tensors_and_order():
    import torch

    prompt = {"prompt_tokens": [[1, 2, 3]], "prompt_features": torch.ones(2), "prompt_rms": torch.tensor(0.1)}

    moved = luxtts_backend._prompt_to_device(prompt, "cpu")

    assert list(moved) == list(prompt)
    assert moved["prompt_tokens"] == [[1, 2, 3]]
    assert moved["prompt_features"].device.type == "cpu"


def _backend_with_cache(monkeypatch, cached, device="cpu"):
    """A loaded-looking CPU backend whose voice-prompt cache returns ``cached``."""
    backend = LuxTTSBackend()
    backend._device = device
    backend.model = object()
    backend._encode_prompt = lambda path, text, seconds: {"prompt_features": __import__("torch").ones(2, device="mps")}
    stored = {}
    monkeypatch.setattr(luxtts_backend, "get_cache_key", lambda *a: "key")
    monkeypatch.setattr(luxtts_backend, "get_cached_voice_prompt", lambda key: cached)
    monkeypatch.setattr(luxtts_backend, "cache_voice_prompt", lambda key, prompt: stored.update(prompt))
    return backend, stored


@requires_mps
def test_stale_mps_cache_entry_is_moved_to_cpu(monkeypatch):
    """Regression: 'can't convert mps:0 device type tensor to numpy' from an old MPS-era cache entry."""
    import torch

    stale = {"prompt_features": torch.ones(2, device="mps"), "prompt_rms": torch.tensor(0.1)}
    backend, _ = _backend_with_cache(monkeypatch, stale)

    prompt, was_cached = asyncio.run(backend.create_voice_prompt("ignored.wav", "text"))

    assert was_cached is True
    assert prompt["prompt_features"].device.type == "cpu"
    prompt["prompt_features"].numpy()  # the call that used to raise


@requires_mps
def test_new_prompts_are_cached_on_cpu(monkeypatch):
    import torch

    backend, stored = _backend_with_cache(monkeypatch, None)

    asyncio.run(backend.create_voice_prompt("ignored.wav", "text"))

    assert stored["prompt_features"].device.type == "cpu"
