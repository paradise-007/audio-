"""
XTTS v2 backend implementation.

Wraps the Coqui XTTS v2 (coqui/XTTS-v2) model for zero-shot multilingual
voice cloning, with explicit Hindi support.

Supported languages: hi, en, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar,
                     zh, hu, ko, ja  (17 total)

For Sanskrit, text is transliterated to Devanagari and processed as Hindi
(shared phoneme space).

HuggingFace repo: coqui/XTTS-v2
Model size: ~1.9 GB
Output: 24 kHz mono WAV

Dependencies (install separately):
    pip install coqui-tts
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import soundfile as sf

from . import TTSBackend
from .base import (
    is_model_cached,
    get_torch_device,
    empty_device_cache,
    manual_seed,
    model_load_progress,
    combine_voice_prompts as _combine_voice_prompts,
)
from ..utils.cache import get_cache_key, get_cached_voice_prompt, cache_voice_prompt

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

XTTS_HF_REPO = "coqui/XTTS-v2"
XTTS_SAMPLE_RATE = 24000

# XTTS v2 supported language codes
XTTS_LANGUAGES = {
    "hi", "en", "es", "fr", "de", "it", "pt", "pl",
    "tr", "ru", "nl", "cs", "ar", "zh", "hu", "ko", "ja",
}

# Sanskrit maps to Hindi (closest supported language in the model)
LANG_REMAP = {
    "sa": "hi",
    "bn": "hi",   # Bengali → Hindi (best available approximation)
    "gu": "hi",
    "mr": "hi",
    "pa": "hi",
    "ta": "hi",
    "te": "hi",
    "kn": "hi",
    "ml": "hi",
}


def _preprocess_for_xtts(text: str, language: str) -> str:
    """
    Preprocess text for XTTS v2.

    - Normalise Unicode
    - Handle IAST → Devanagari if needed
    - Remove danda/double-danda (replace with period)
    - Strip unsupported markup
    """
    import unicodedata
    import re

    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("।", ".").replace("॥", ".")

    # Detect IAST and transliterate to Devanagari for Hindi/Sanskrit
    iast_chars = set("āīūṛṝḷṅñṭḍṇśṣḥṁ")
    if any(c in iast_chars for c in text) and not any(
        "\u0900" <= c <= "\u097F" for c in text
    ):
        try:
            from indic_transliteration import sanscript
            from indic_transliteration.sanscript import transliterate
            text = transliterate(text, sanscript.IAST, sanscript.DEVANAGARI)
        except ImportError:
            logger.warning("indic-transliteration not installed; keeping IAST")

    return text


# ── Main Backend ─────────────────────────────────────────────────────────────

class XTTSBackend:
    """
    XTTS v2 (Coqui) backend for multilingual zero-shot voice cloning.

    Supports Hindi natively. Sanskrit is mapped to Hindi (shared script + phonemes).
    """

    max_chunk_chars = 300  # XTTS works best with shorter segments

    def __init__(self):
        self.model = None
        self._device = None
        self._load_lock = asyncio.Lock()

    def _get_device(self) -> str:
        """CUDA preferred for XTTS (RTX 4050). CPU fallback."""
        return get_torch_device(allow_mps=False, allow_xpu=True)

    @property
    def device(self) -> str:
        if self._device is None:
            self._device = self._get_device()
        return self._device

    def is_loaded(self) -> bool:
        return self.model is not None

    def _get_model_path(self, model_size: str = "default") -> str:
        return XTTS_HF_REPO

    def _is_model_cached(self, model_size: str = "default") -> bool:
        return is_model_cached(XTTS_HF_REPO, weight_extensions=(".pth", ".pt", ".safetensors", ".bin"))

    async def load_model(self, model_size: str = "default") -> None:
        if self.model is not None:
            return
        async with self._load_lock:
            if self.model is not None:
                return
            await asyncio.to_thread(self._load_model_sync)

    def _load_model_sync(self):
        is_cached = self._is_model_cached()
        with model_load_progress("xtts-v2", is_cached):
            try:
                from TTS.api import TTS
            except ImportError:
                raise RuntimeError(
                    "coqui-tts is not installed. Run:\n"
                    "  pip install coqui-tts\n"
                    "inside the voicebox venv."
                )

            import torch

            logger.info(f"Loading XTTS v2 on {self.device}...")
            use_gpu = (self.device == "cuda")

            self.model = TTS(
                model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                gpu=use_gpu,
            )

        logger.info("XTTS v2 loaded successfully")

    def unload_model(self) -> None:
        if self.model is not None:
            device = self.device
            del self.model
            self.model = None
            self._device = None
            empty_device_cache(device)
            logger.info("XTTS v2 unloaded")

    # ── Voice Prompt ─────────────────────────────────────────────────────────

    async def create_voice_prompt(
        self,
        audio_path: str,
        reference_text: str,
        use_cache: bool = True,
        prompt_seconds: Optional[int] = None,
    ) -> Tuple[dict, bool]:
        """
        XTTS uses the reference WAV directly for conditioning.
        We store the path + optional transcript.
        """
        await self.load_model()

        cache_key = (
            "xtts_v2_v1_" + get_cache_key(audio_path, reference_text)
        ) if use_cache else None

        if cache_key:
            cached = get_cached_voice_prompt(cache_key)
            if cached is not None:
                return cached, True

        def _build():
            import librosa
            # Trim to 30s max (XTTS recommended reference: 3–30s)
            wav, sr = librosa.load(audio_path, sr=XTTS_SAMPLE_RATE, mono=True)
            max_s = min(prompt_seconds or 15, 30)
            if len(wav) > max_s * XTTS_SAMPLE_RATE:
                wav = wav[: max_s * XTTS_SAMPLE_RATE]

            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, prefix="xtts_ref_")
            sf.write(tmp.name, wav, XTTS_SAMPLE_RATE)

            return {
                "ref_audio_path": tmp.name,
                "ref_text": reference_text.strip(),
                "sample_rate": XTTS_SAMPLE_RATE,
            }

        prompt = await asyncio.to_thread(_build)

        if cache_key:
            cache_voice_prompt(cache_key, prompt)

        return prompt, False

    async def combine_voice_prompts(self, audio_paths, reference_texts):
        return await _combine_voice_prompts(audio_paths, reference_texts, sample_rate=XTTS_SAMPLE_RATE)

    # ── Generation ───────────────────────────────────────────────────────────

    async def generate(
        self,
        text: str,
        voice_prompt: dict,
        language: str = "hi",
        seed: Optional[int] = None,
        instruct: Optional[str] = None,
    ) -> Tuple[np.ndarray, int]:
        """
        Generate speech with XTTS v2 voice cloning.

        Args:
            text: Input text (Devanagari Hindi/Sanskrit or Latin-script languages)
            voice_prompt: Dict with ref_audio_path and ref_text
            language: BCP-47 language code (e.g. 'hi', 'sa'→'hi', 'en')
            seed: Optional random seed for reproducibility
            instruct: Ignored
        """
        await self.load_model()

        # Remap unsupported languages
        lang = LANG_REMAP.get(language, language)
        if lang not in XTTS_LANGUAGES:
            logger.warning(f"XTTS: language '{lang}' not supported, falling back to 'hi'")
            lang = "hi"

        clean_text = _preprocess_for_xtts(text, lang)
        if not clean_text:
            return np.zeros(XTTS_SAMPLE_RATE, dtype=np.float32), XTTS_SAMPLE_RATE

        ref_audio_path = voice_prompt.get("ref_audio_path", "")

        def _generate_sync():
            import tempfile

            out_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, prefix="xtts_out_").name

            self.model.tts_to_file(
                text=clean_text,
                speaker_wav=ref_audio_path,
                language=lang,
                file_path=out_path,
            )

            audio, sr = sf.read(out_path, dtype="float32")
            try:
                os.unlink(out_path)
            except Exception:
                pass

            audio = audio.squeeze()
            if sr != XTTS_SAMPLE_RATE:
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=XTTS_SAMPLE_RATE)

            return audio, XTTS_SAMPLE_RATE

        return await asyncio.to_thread(_generate_sync)
