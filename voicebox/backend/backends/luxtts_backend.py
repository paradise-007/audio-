"""
LuxTTS backend implementation.

Wraps the LuxTTS (ZipVoice) model for zero-shot voice cloning.
~1GB VRAM, 48kHz output, 150x realtime on CPU.
"""

import asyncio
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from . import TTSBackend
from .base import (
    is_model_cached,
    get_torch_device,
    empty_device_cache,
    manual_seed,
    combine_voice_prompts as _combine_voice_prompts,
    model_load_progress,
)
from ..utils.cache import get_cache_key, get_cached_voice_prompt, cache_voice_prompt

logger = logging.getLogger(__name__)

# HuggingFace repo for model weight detection
LUXTTS_HF_REPO = "YatharthS/LuxTTS"

# zipvoice also loads a Whisper ASR model next to the LuxTTS weights, to
# transcribe the reference audio. It must count toward "cached": a LuxTTS-only
# cache would flip the loader into offline mode and the load would fail instead
# of fetching the missing Whisper files.
#
# zipvoice's own CPU path hard-codes whisper-tiny while its GPU path uses
# whisper-base. We use whisper-base on every device: it transcribes noticeably
# better (the transcript is part of the voice prompt, so errors hurt cloning
# accuracy) and one shared cache entry means one download, reused everywhere.
LUXTTS_WHISPER_REPO = "openai/whisper-base"
_ZIPVOICE_CPU_WHISPER_REPO = "openai/whisper-tiny"

# Output pace = the reference's own pace x `speed`, and zipvoice multiplies the
# `speed` it is given by 1.3 internally. Passing 1.0 therefore speaks 30% faster
# than the reference (measured: ~315 words/min on a 175 wpm news-anchor reference,
# with dropped and slurred words). 1/1.3 cancels that so the output keeps the
# reference's pace: 179-190 wpm vs 175 wpm reference, same intelligibility.
LUXTTS_SPEED = 1 / 1.3

# Seconds of the reference the model conditions on (zipvoice's default is 5).
# The prompt carries the voice, pitch and delivery, so more of it matches the
# reference better. Measured against a 23 s reference (timbre error, lower is
# better): 5s 0.32, 10s 0.22, 15s 0.19, 24s 0.13; a 5s prompt also put the pitch
# a semitone sharp, 15s+ did not. Cost grows with prompt length (~+30% at 15s),
# so 15s is the compromise. It is part of the voice-prompt cache key.
LUXTTS_PROMPT_SECONDS = 15

# Per-voice speaking-speed multiplier (1.0 = the reference's own pace). It is carried
# inside the voice prompt dict under this key (see services/profiles.py) and removed
# before the prompt reaches zipvoice.
SPEED_KEY = "_speed"
MIN_SPEED, MAX_SPEED = 0.5, 1.5  # hard clamp; the UI offers 0.7-1.3

# Longest text chunk worth generating in one pass. Cost grows faster than linearly
# with chunk length once a long reference prompt is in play: measured on a 15 s
# prompt, 500 chars ran at 1.5x real time and 800 chars at 3.5x (300 chars: 1.8x,
# less accurate). The app's default is 800, so cap it for this engine.
LUXTTS_MAX_CHUNK_CHARS = 500


@contextmanager
def _use_whisper_base_on_cpu():
    """Make zipvoice's CPU loader build its ASR pipeline from whisper-base."""
    import zipvoice.modeling_utils as zipvoice_utils

    original = zipvoice_utils.pipeline

    def pipeline(task, *args, model=None, **kwargs):
        if model == _ZIPVOICE_CPU_WHISPER_REPO:
            model = LUXTTS_WHISPER_REPO
        return original(task, *args, model=model, **kwargs)

    zipvoice_utils.pipeline = pipeline
    try:
        yield
    finally:
        zipvoice_utils.pipeline = original


def _prompt_to_device(prompt: dict, device: str) -> dict:
    """Copy a voice prompt's tensors to ``device`` (non-tensors and key order are kept).

    Cached prompts outlive the process that wrote them, so their tensors may sit
    on a device this run doesn't use (e.g. an entry saved under the old MPS
    setting), which makes the CPU/ONNX path fail with "can't convert mps:0
    device type tensor to numpy".
    """
    import torch

    return {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in prompt.items()}


# ── Reference prompt planning ────────────────────────────────────────────────
#
# zipvoice normally transcribes the reference window itself with Whisper-base. On
# some recordings that fails badly: the same 20 s clip gave 2655 prompt tokens
# (a hallucination loop, 0.4 s of output) at a 10 s window and 119 tokens (under-
# transcribed, speech at ~87 wpm) at 15 s. The transcript is part of the prompt, so
# its errors become pace and voice errors. Voicebox already holds a transcript for
# every sample (auto-filled and editable in the UI), so use that, cut at a pause,
# and only fall back to Whisper (on the whole recording) when it is missing or implausible.

PLAUSIBLE_WPM = (60.0, 320.0)  # words per second of *speech* (pauses excluded)
_FRAMES_PER_SECOND = 100  # 10 ms analysis frames


@dataclass
class PromptPlan:
    """How much of the reference to use and which transcript describes it (None = ask Whisper)."""

    seconds: float
    text: Optional[str]


def _speech_activity(audio_path: str):
    """Per-10ms speech/silence mask and total duration of a recording."""
    import librosa

    y, sr = librosa.load(audio_path, sr=16000, mono=True)
    rms = librosa.feature.rms(y=y, frame_length=400, hop_length=160)[0]
    db = 20 * np.log10(rms + 1e-8)
    return db > np.percentile(db, 95) - 30, len(y) / sr


def _speech_seconds(speech: np.ndarray, end_s: float) -> float:
    return float(np.sum(speech[: int(end_s * _FRAMES_PER_SECOND)])) / _FRAMES_PER_SECOND


def is_plausible_transcript(text: str, speech_seconds: float) -> bool:
    """True when ``text`` could be what was said in ``speech_seconds`` of speech."""
    words = len(text.split()) if text else 0
    if words < 3 or speech_seconds < 1.0:
        return False
    wpm = words / speech_seconds * 60
    return PLAUSIBLE_WPM[0] <= wpm <= PLAUSIBLE_WPM[1]


def plan_prompt(speech: np.ndarray, duration: float, text: Optional[str], seconds: float) -> PromptPlan:
    """Choose the reference cut-off and the transcript for it.

    The whole recording is used when it is not much longer than ``seconds``. Otherwise
    the cut moves to the longest pause within 2 s of ``seconds`` so no word is split, and
    the transcript is cut in proportion to the speech before that point.
    """
    if duration <= seconds + 1.5:
        cut = duration
    else:
        cut = float(seconds)
        lo, hi = int((seconds - 2) * _FRAMES_PER_SECOND), int((seconds + 2) * _FRAMES_PER_SECOND)
        silent = ~speech[lo:hi]
        padded = np.concatenate(([False], silent, [False]))
        edges = np.flatnonzero(padded[1:] != padded[:-1])
        gaps = [(b - a, a + lo, b + lo) for a, b in zip(edges[::2], edges[1::2]) if b - a >= 12]
        if gaps:
            _, a, b = max(gaps)
            cut = (a + b) / 2 / _FRAMES_PER_SECOND

    total_speech = _speech_seconds(speech, duration)
    if text and is_plausible_transcript(text, total_speech):
        words = text.split()
        if cut >= duration:
            count = len(words)
        else:
            count = max(3, round(len(words) * _speech_seconds(speech, cut) / total_speech))
        return PromptPlan(cut, " ".join(words[:count]))
    return PromptPlan(cut, None)


class LuxTTSBackend:
    """LuxTTS backend for zero-shot voice cloning."""

    # Read by utils.chunked_tts.generate_chunked
    max_chunk_chars = LUXTTS_MAX_CHUNK_CHARS

    def __init__(self):
        self.model = None
        self.model_size = "default"  # LuxTTS has only one model size
        self._device = None
        # Serialize loads: a preload racing a generate request must not load
        # the model twice (double the RAM and startup time).
        self._load_lock = asyncio.Lock()

    def _get_device(self) -> str:
        # MPS is deliberately off: zipvoice's torch path needs autocast and
        # complex-number ops that MPS lacks on torch<=2.2 (generation crashes),
        # whereas its CPU path (ONNX int8) is the fast one and runs everywhere.
        return get_torch_device(allow_mps=False, allow_xpu=True)

    def is_loaded(self) -> bool:
        return self.model is not None

    @property
    def device(self) -> str:
        if self._device is None:
            self._device = self._get_device()
        return self._device

    def _get_model_path(self, model_size: str) -> str:
        return LUXTTS_HF_REPO

    def _is_model_cached(self, model_size: str = "default") -> bool:
        return is_model_cached(
            LUXTTS_HF_REPO,
            weight_extensions=(".pt", ".safetensors", ".onnx", ".bin"),
        ) and is_model_cached(LUXTTS_WHISPER_REPO)

    async def load_model(self, model_size: str = "default") -> None:
        """Load the LuxTTS model."""
        if self.model is not None:
            return

        async with self._load_lock:
            if self.model is not None:
                return
            await asyncio.to_thread(self._load_model_sync)

    def _load_model_sync(self):
        model_name = "luxtts"
        is_cached = self._is_model_cached()

        with model_load_progress(model_name, is_cached):
            from zipvoice.luxvoice import LuxTTS

            device = self.device
            logger.info(f"Loading LuxTTS on {device}...")

            if device == "cpu":
                import os

                threads = os.cpu_count() or 4
                with _use_whisper_base_on_cpu():
                    self.model = LuxTTS(
                        model_path=LUXTTS_HF_REPO,
                        device="cpu",
                        threads=min(threads, 8),
                    )
            else:
                self.model = LuxTTS(model_path=LUXTTS_HF_REPO, device=device)

        logger.info("LuxTTS loaded successfully")

    def unload_model(self) -> None:
        """Unload model to free memory."""
        if self.model is not None:
            device = self.device
            del self.model
            self.model = None
            self._device = None

            empty_device_cache(device)

            logger.info("LuxTTS unloaded")

    async def create_voice_prompt(
        self,
        audio_path: str,
        reference_text: str,
        use_cache: bool = True,
        prompt_seconds: Optional[int] = None,
    ) -> Tuple[dict, bool]:
        """
        Create voice prompt from reference audio.

        ``prompt_seconds`` is how much of the recording the model listens to
        (default ``LUXTTS_PROMPT_SECONDS``); it is part of the cache key.

        The transcript for the prompt is ``reference_text`` when it plausibly matches
        the audio, otherwise zipvoice's own Whisper pass (see ``plan_prompt``).
        """
        await self.load_model()

        seconds = int(prompt_seconds or LUXTTS_PROMPT_SECONDS)

        # Compute cache key once for both lookup and storage
        cache_key = (
            f"luxtts_v2_p{seconds}_" + get_cache_key(audio_path, reference_text)
        ) if use_cache else None

        if cache_key:
            cached = get_cached_voice_prompt(cache_key)
            if cached is not None and isinstance(cached, dict):
                return _prompt_to_device(cached, self.device), True

        def _encode_sync():
            return self._encode_prompt(str(audio_path), reference_text, seconds)

        encoded = await asyncio.to_thread(_encode_sync)

        if cache_key:
            # Stored on CPU so the entry is valid whichever device later runs use
            cache_voice_prompt(cache_key, _prompt_to_device(encoded, "cpu"))

        return encoded, False

    def _zipvoice_speed(self, voice_prompt: dict, text: str, multiplier: float) -> float:
        """zipvoice ``speed`` that makes the output ``multiplier`` times faster than the neutral pace.

        zipvoice divides the *whole* sequence (reference prompt + new speech) by ``speed``:
        output = (P + T0) / speed - P, with P the prompt length and T0 the neutral length of
        the text. So the knob is far from proportional (measured: 1.3 -> 3x shorter, 0.8 ->
        1.7x longer) and depends on the prompt. Inverting gives output = T0 / multiplier:
        speed = (P + T0) / (P + T0 / multiplier). All lengths are in prompt frames.
        """
        if abs(multiplier - 1.0) < 1e-6:
            return LUXTTS_SPEED
        prompt_frames = float(voice_prompt["prompt_features_lens"][0])
        prompt_tokens = len(voice_prompt["prompt_tokens"][0])
        text_tokens = len(self.model.tokenizer.texts_to_token_ids([text])[0])
        if prompt_frames <= 0 or prompt_tokens <= 0 or text_tokens <= 0:
            return LUXTTS_SPEED * multiplier
        neutral = prompt_frames * text_tokens / prompt_tokens  # T0: text at the reference's pace
        return LUXTTS_SPEED * (prompt_frames + neutral) / (prompt_frames + neutral / multiplier)

    def _transcribe_whole(self, audio_path: str) -> str:
        """Whisper transcript of the *entire* recording (blocking).

        Windows cut mid-sentence make Whisper-base skip, drop or loop on noisy or quiet
        speech (measured: 8 s -> 23 words, 10 s -> 334 words, 15 s -> 20 words, whole
        20 s clip -> 49 words for 44 spoken), so it is only ever asked about whole recordings.
        """
        import librosa

        wav, _ = librosa.load(audio_path, sr=16000, mono=True)
        return self.model.transcriber(
            wav, return_timestamps=True, chunk_length_s=30, generate_kwargs={"language": "en", "task": "transcribe"}
        )["text"]

    def _encode_prompt(self, audio_path: str, reference_text: str, seconds: int) -> dict:
        """zipvoice's ``encode_prompt`` with a vetted transcript (blocking; run in a thread)."""
        from zipvoice.modeling_utils import process_audio

        model = self.model
        speech, duration = _speech_activity(audio_path)
        plan = plan_prompt(speech, duration, reference_text, seconds)
        if plan.text is None:
            # No usable transcript on file (missing or placeholder): transcribe the whole
            # recording, then cut the text together with the audio.
            plan = plan_prompt(speech, duration, self._transcribe_whole(audio_path), seconds)
        if plan.text is None:
            raise ValueError(
                "Could not transcribe the reference recording reliably. "
                "Check the Reference Text for this voice (it must match the audio) and try again."
            )

        tokens, lens, features, rms = process_audio(
            audio_path,
            lambda wav_16k: {"text": plan.text},
            model.tokenizer,
            model.feature_extractor,
            model.device,
            target_rms=0.01,
            duration=plan.seconds,
        )
        return {
            "prompt_tokens": tokens,
            "prompt_features_lens": lens,
            "prompt_features": features,
            "prompt_rms": rms,
        }

    async def combine_voice_prompts(self, audio_paths, reference_texts):
        return await _combine_voice_prompts(audio_paths, reference_texts, sample_rate=24000)

    async def generate(
        self,
        text: str,
        voice_prompt: dict,
        language: str = "en",
        seed: Optional[int] = None,
        instruct: Optional[str] = None,
    ) -> Tuple[np.ndarray, int]:
        """
        Generate audio from text using LuxTTS.

        Args:
            text: Text to synthesize
            voice_prompt: Encoded prompt dict from encode_prompt()
            language: Language code (LuxTTS is English-focused)
            seed: Random seed for reproducibility
            instruct: Not supported by LuxTTS (ignored)

        Returns:
            Tuple of (audio_array, sample_rate)
        """
        await self.load_model()

        # Per-voice speed multiplier rides in the prompt; zipvoice must not see the key.
        voice_prompt = dict(voice_prompt)
        multiplier = min(max(float(voice_prompt.pop(SPEED_KEY, 1.0)), MIN_SPEED), MAX_SPEED)

        def _generate_sync():
            if seed is not None:
                manual_seed(seed, self.device)

            import torch

            with torch.inference_mode():
                wav = self.model.generate_speech(
                    text=text,
                    encode_dict=voice_prompt,
                    num_steps=4,
                    guidance_scale=3.0,
                    t_shift=0.5,
                    speed=self._zipvoice_speed(voice_prompt, text, multiplier),
                    return_smooth=False,  # 48kHz output
                )

                # LuxTTS returns a tensor (may be on GPU/MPS), move to CPU first
                audio = wav.detach().cpu().numpy().squeeze()
            return audio, 48000

        return await asyncio.to_thread(_generate_sync)
