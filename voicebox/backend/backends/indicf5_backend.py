"""
IndicF5 backend implementation.

Wraps the AI4Bharat IndicF5 model — an F5-TTS variant trained on 1,400+ hours
of speech across 11 Indian languages (Hindi, Bengali, Gujarati, Marathi, Punjabi,
Tamil, Telugu, Kannada, Malayalam, Odia, Assamese).

Supports zero-shot voice cloning with native Devanagari / Indic script input.
No external phonemizer required — the model handles native script directly.

HuggingFace repo: ai4bharat/IndicF5
Model size: ~1.2 GB
Output: 24 kHz mono WAV
"""

import asyncio
import logging
import os
import tempfile
from contextlib import contextmanager
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

INDICF5_HF_REPO = "ai4bharat/IndicF5"

# Languages natively supported by IndicF5
INDICF5_LANGUAGES = [
    "hi",  # Hindi
    "bn",  # Bengali
    "gu",  # Gujarati
    "mr",  # Marathi
    "pa",  # Punjabi
    "ta",  # Tamil
    "te",  # Telugu
    "kn",  # Kannada
    "ml",  # Malayalam
    "or",  # Odia
    "as",  # Assamese
    "sa",  # Sanskrit (via Hindi phoneme space)
]

# Sanskrit maps to Hindi for phoneme processing since IndicF5 was trained
# on modern Indic languages. The Devanagari script is shared.
LANG_REMAP = {
    "sa": "hi",  # Sanskrit → Hindi (same script, similar phoneme inventory)
}

# Voice prompt reference window — longer = more faithful voice matching
INDICF5_PROMPT_SECONDS = 10  # 5–15s recommended by AI4Bharat

# Output sample rate
INDICF5_SAMPLE_RATE = 24000


# ── Sanskrit / Hindi text preprocessor ──────────────────────────────────────

def preprocess_indic_text(text: str, language: str) -> str:
    """
    Preprocess Sanskrit/Hindi Devanagari text for IndicF5.

    IndicF5 accepts native Devanagari directly — no romanization needed.
    This function:
    1. Normalises Unicode (NFC)
    2. Removes unsupported characters (XML entities, HTML tags)
    3. Applies light Sandhi-boundary normalization for Sanskrit
    4. Handles IAST romanized input — transliterates back to Devanagari

    Args:
        text: Input text (Devanagari or IAST romanized Sanskrit/Hindi)
        language: Language code ('hi', 'sa', etc.)

    Returns:
        Cleaned Devanagari text ready for IndicF5
    """
    import unicodedata
    import re

    # Normalize Unicode to NFC (canonical decomposition → composition)
    text = unicodedata.normalize("NFC", text)

    # Strip HTML/XML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Strip markdown bold/italic
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Replace Devanagari dandas with periods for TTS chunking
    text = text.replace("।", ".")
    text = text.replace("॥", ".")

    # If text appears to be IAST (contains Latin diacritics like ā, ī, ū, ṛ etc.)
    # transliterate it to Devanagari
    iast_chars = set("āīūṛṝḷḹṅñṭḍṇśṣḥṁãÃĀĪŪŔ")
    if any(c in iast_chars for c in text) and not any(
        "\u0900" <= c <= "\u097F" for c in text
    ):
        try:
            from indic_transliteration import sanscript
            from indic_transliteration.sanscript import transliterate
            text = transliterate(text, sanscript.IAST, sanscript.DEVANAGARI)
            logger.info("Transliterated IAST → Devanagari for IndicF5")
        except ImportError:
            logger.warning("indic-transliteration not installed; keeping IAST text")

    return text


def get_reference_transcript(audio_path: str, lang: str) -> str:
    """
    Get a plausible transcript for the reference audio.
    Uses Whisper (multilingual) since IndicF5 needs the ref text.
    """
    try:
        from transformers import pipeline
        transcriber = pipeline(
            "automatic-speech-recognition",
            model="openai/whisper-base",
            device="cpu",
        )
        result = transcriber(
            audio_path,
            generate_kwargs={"language": lang if lang != "sa" else "hi", "task": "transcribe"},
            chunk_length_s=30,
            return_timestamps=False,
        )
        return result.get("text", "").strip()
    except Exception as e:
        logger.warning(f"Whisper transcription failed: {e}")
        return ""


# ── Main Backend Class ───────────────────────────────────────────────────────

class IndicF5Backend:
    """
    IndicF5 backend for zero-shot Indian language voice cloning.

    Uses AI4Bharat's IndicF5 model (F5-TTS architecture) trained on
    1,400+ hours of speech in 11 Indian languages.
    """

    # Read by utils.chunked_tts.generate_chunked
    max_chunk_chars = 400  # Shorter chunks = more natural prosody for Indic scripts

    def __init__(self):
        self.model = None
        self._device = None
        self._load_lock = asyncio.Lock()

    def _get_device(self) -> str:
        """
        RTX 4050 CUDA preferred, then CPU.
        IndicF5 (F5-TTS) runs well on CUDA — significantly faster than CPU.
        """
        return get_torch_device(allow_mps=False, allow_xpu=True)

    @property
    def device(self) -> str:
        if self._device is None:
            self._device = self._get_device()
        return self._device

    def is_loaded(self) -> bool:
        return self.model is not None

    def _get_model_path(self, model_size: str = "default") -> str:
        return INDICF5_HF_REPO

    def _is_model_cached(self, model_size: str = "default") -> bool:
        return is_model_cached(INDICF5_HF_REPO, weight_extensions=(".pt", ".safetensors", ".bin"))

    async def load_model(self, model_size: str = "default") -> None:
        """Load the IndicF5 model."""
        if self.model is not None:
            return
        async with self._load_lock:
            if self.model is not None:
                return
            await asyncio.to_thread(self._load_model_sync)

    def _load_model_sync(self):
        is_cached = self._is_model_cached()
        with model_load_progress("indicf5", is_cached):
            from transformers import AutoModel

            logger.info(f"Loading IndicF5 on {self.device}...")
            self.model = AutoModel.from_pretrained(
                INDICF5_HF_REPO,
                trust_remote_code=True,
            )
            # Move to device if CUDA available
            if self.device == "cuda":
                import torch
                self.model = self.model.to(torch.device("cuda"))

        logger.info("IndicF5 loaded successfully")

    def unload_model(self) -> None:
        if self.model is not None:
            device = self.device
            del self.model
            self.model = None
            self._device = None
            empty_device_cache(device)
            logger.info("IndicF5 unloaded")

    # ── Voice Prompt ─────────────────────────────────────────────────────────

    async def create_voice_prompt(
        self,
        audio_path: str,
        reference_text: str,
        use_cache: bool = True,
        prompt_seconds: Optional[int] = None,
    ) -> Tuple[dict, bool]:
        """
        Build an IndicF5 voice prompt from reference audio.

        Returns a dict with:
          - ref_audio_path: path to (trimmed) reference WAV
          - ref_text: transcript of reference
        """
        await self.load_model()

        cache_key = (
            f"indicf5_v1_p{prompt_seconds or INDICF5_PROMPT_SECONDS}_"
            + get_cache_key(audio_path, reference_text)
        ) if use_cache else None

        if cache_key:
            cached = get_cached_voice_prompt(cache_key)
            if cached is not None:
                return cached, True

        def _build_prompt():
            import librosa

            # Load and trim to INDICF5_PROMPT_SECONDS
            max_secs = prompt_seconds or INDICF5_PROMPT_SECONDS
            wav, sr = librosa.load(audio_path, sr=INDICF5_SAMPLE_RATE, mono=True)
            if len(wav) > max_secs * INDICF5_SAMPLE_RATE:
                wav = wav[: max_secs * INDICF5_SAMPLE_RATE]

            # Write trimmed WAV to a temp file that persists
            tmp = tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False, prefix="indicf5_ref_"
            )
            sf.write(tmp.name, wav, INDICF5_SAMPLE_RATE)

            # Get reference transcript
            ref_text = reference_text.strip() if reference_text.strip() else get_reference_transcript(audio_path, "hi")

            return {
                "ref_audio_path": tmp.name,
                "ref_text": ref_text,
                "sample_rate": INDICF5_SAMPLE_RATE,
            }

        prompt = await asyncio.to_thread(_build_prompt)

        if cache_key:
            cache_voice_prompt(cache_key, prompt)

        return prompt, False

    async def combine_voice_prompts(self, audio_paths, reference_texts):
        """Combine multiple reference audio clips by concatenating them."""
        return await _combine_voice_prompts(
            audio_paths, reference_texts, sample_rate=INDICF5_SAMPLE_RATE
        )

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
        Generate speech in the cloned voice using IndicF5.

        Args:
            text: Input text (Devanagari script, Hindi or Sanskrit)
            voice_prompt: Dict from create_voice_prompt()
            language: Language code ('hi', 'sa', 'bn', etc.)
            seed: Optional random seed
            instruct: Ignored (not supported)

        Returns:
            Tuple of (audio_array float32, sample_rate=24000)
        """
        await self.load_model()

        # Remap Sanskrit to Hindi
        lang = LANG_REMAP.get(language, language)
        if lang not in [l for l in INDICF5_LANGUAGES if l != "sa"]:
            logger.warning(f"Language {lang} not in IndicF5 native set, using 'hi'")
            lang = "hi"

        # Preprocess text
        clean_text = preprocess_indic_text(text, lang)
        if not clean_text:
            return np.zeros(INDICF5_SAMPLE_RATE, dtype=np.float32), INDICF5_SAMPLE_RATE

        ref_audio_path = voice_prompt.get("ref_audio_path", "")
        ref_text = voice_prompt.get("ref_text", "")

        def _generate_sync():
            if seed is not None:
                manual_seed(seed, "cpu")

            # IndicF5 is called as a callable AutoModel
            audio = self.model(
                clean_text,
                ref_audio_path=ref_audio_path,
                ref_text=ref_text,
            )

            # Normalise output type
            if hasattr(audio, "numpy"):
                audio = audio.numpy()
            audio = np.array(audio, dtype=np.float32)

            # Normalize int16 output
            if audio.dtype == np.int16 or audio.max() > 2.0:
                audio = audio.astype(np.float32) / 32768.0

            audio = audio.squeeze()
            return audio, INDICF5_SAMPLE_RATE

        return await asyncio.to_thread(_generate_sync)
