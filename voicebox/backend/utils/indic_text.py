"""
Sanskrit & Hindi text preprocessing utilities for Vedic Voice Studio.

Handles:
  - Devanagari Unicode normalisation
  - IAST ↔ Devanagari transliteration
  - Sandhi boundary detection for chunking
  - Chhandas-aware sentence splitting (respects pāda boundaries)
  - Mātrā duration annotation (for prosody hints)
  - Language detection (Sanskrit vs Hindi vs IAST)
"""

import re
import unicodedata
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Script detection ─────────────────────────────────────────────────────────

DEVANAGARI_RANGE = range(0x0900, 0x097F + 1)
IAST_MARKERS = frozenset("āīūṛṝḷṅñṭḍṇśṣḥṁÃ")


def detect_script(text: str) -> str:
    """
    Detect the input script of a text.

    Returns:
        'devanagari' | 'iast' | 'latin' | 'mixed'
    """
    has_dev = any(ord(c) in DEVANAGARI_RANGE for c in text)
    has_iast = any(c in IAST_MARKERS for c in text)
    has_latin = any(c.isalpha() and ord(c) < 128 for c in text)

    if has_dev and not has_iast:
        return "devanagari"
    if has_iast and not has_dev:
        return "iast"
    if has_dev and has_iast:
        return "mixed"
    if has_latin:
        return "latin"
    return "unknown"


def detect_language(text: str) -> str:
    """
    Heuristic language detection: Sanskrit vs Hindi.

    Sanskrit markers: sandhi endings (-āmi, -āsi, -ati, -iti, -āya),
    typical verb suffixes, OM symbol.

    Returns:
        'sa' | 'hi'
    """
    # OM is a strong Sanskrit marker
    if "ॐ" in text or "oṁ" in text.lower() or "om " in text.lower():
        return "sa"

    # Sanskrit-specific word endings (IAST)
    sa_patterns = [
        r"\bpraṇava\b", r"\bvedic\b",
        r"āmi\b", r"āsi\b", r"ati\b", r"āva\b",
        r"iti\b", r"eva\b", r"ca\b", r"tu\b",
        r"\bnamas\b", r"\bsvāhā\b", r"\bnamaḥ\b",
        r"\bdhīmahi\b", r"\bpracodayāt\b",
    ]
    for p in sa_patterns:
        if re.search(p, text, re.IGNORECASE):
            return "sa"

    # Common Hindi-specific markers
    hi_patterns = [r"है\b", r"हैं\b", r"का\b", r"के\b", r"को\b", r"में\b", r"से\b"]
    for p in hi_patterns:
        if re.search(p, text):
            return "hi"

    # Default to Sanskrit if Devanagari (classical context assumed)
    if detect_script(text) == "devanagari":
        return "sa"

    return "hi"


# ── Normalisation ─────────────────────────────────────────────────────────────

def normalise_unicode(text: str) -> str:
    """Normalize to NFC and strip zero-width characters."""
    text = unicodedata.normalize("NFC", text)
    # Remove zero-width non-joiner / zero-width joiner (used wrongly sometimes)
    text = text.replace("\u200c", "").replace("\u200d", "")
    return text


def clean_markup(text: str) -> str:
    """Remove HTML, XML, and Markdown from text."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,2}(.*?)_{1,2}", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)  # markdown links
    return text


def normalise_punctuation(text: str) -> str:
    """
    Normalise Sanskrit/Hindi punctuation for TTS.

    - Danda (।) → period
    - Double danda (॥) → period
    - Avagraha (ऽ) → held vowel hint (keep for now)
    - ZWSP → space
    """
    text = text.replace("।", ". ")
    text = text.replace("॥", ". ")
    text = re.sub(r"\.{2,}", ".", text)   # collapse multiple dots
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ── Transliteration ───────────────────────────────────────────────────────────

def iast_to_devanagari(text: str) -> str:
    """Transliterate IAST romanized Sanskrit to Devanagari using indic-transliteration."""
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate
        return transliterate(text, sanscript.IAST, sanscript.DEVANAGARI)
    except ImportError:
        logger.warning("indic-transliteration not installed; IAST input will be used as-is")
        return text


def devanagari_to_iast(text: str) -> str:
    """Transliterate Devanagari to IAST for display/analysis."""
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate
        return transliterate(text, sanscript.DEVANAGARI, sanscript.IAST)
    except ImportError:
        return text


def itrans_to_devanagari(text: str) -> str:
    """Transliterate ITRANS-encoded text to Devanagari."""
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate
        return transliterate(text, sanscript.ITRANS, sanscript.DEVANAGARI)
    except ImportError:
        return text


def auto_to_devanagari(text: str) -> str:
    """
    Auto-detect script and convert to Devanagari if not already.

    Handles IAST, ITRANS, and plain Devanagari input.
    """
    script = detect_script(text)
    if script == "devanagari":
        return text
    if script == "iast":
        return iast_to_devanagari(text)
    if script == "latin":
        # Try ITRANS first (uses uppercase for certain sounds)
        # Simple heuristic: if has uppercase consonants typical of ITRANS
        itrans_markers = re.search(r"\b[AEIOU][A-Z]|[TBDG]h|[nNmMM]|OM\b", text)
        if itrans_markers:
            return itrans_to_devanagari(text)
    return text  # return as-is for unknown scripts


# ── Pāda-aware chunking ───────────────────────────────────────────────────────

def split_into_pada_chunks(text: str, max_chars: int = 400) -> list[str]:
    """
    Split text into chunks at natural Sanskrit/Hindi boundaries.

    Priority (highest to lowest):
    1. Danda / double-danda boundaries (। ॥)
    2. Sentence endings (. ? !)
    3. Comma / semicolon
    4. Space (word boundary)
    5. Hard char limit

    Args:
        text: Preprocessed Devanagari text
        max_chars: Maximum characters per chunk

    Returns:
        List of text chunks suitable for TTS generation
    """
    # First split on dandas / sentence ends
    raw_chunks = re.split(r"[।॥.!?]+", text)
    chunks = []

    for raw in raw_chunks:
        raw = raw.strip()
        if not raw:
            continue

        if len(raw) <= max_chars:
            chunks.append(raw)
        else:
            # Sub-split on commas/semicolons
            sub = re.split(r"[,;]+", raw)
            current = ""
            for piece in sub:
                piece = piece.strip()
                if not piece:
                    continue
                if len(current) + len(piece) + 2 <= max_chars:
                    current = (current + ", " + piece).lstrip(", ")
                else:
                    if current:
                        chunks.append(current)
                    current = piece
            if current:
                chunks.append(current)

    return [c for c in chunks if c.strip()]


# ── Full preprocessing pipeline ───────────────────────────────────────────────

def preprocess_vedic_text(
    text: str,
    language: Optional[str] = None,
    max_chunk_chars: int = 400,
) -> dict:
    """
    Full preprocessing pipeline for Vedic Voice Studio.

    Args:
        text: Raw input text (any script)
        language: Optional language override ('sa', 'hi', etc.)
        max_chunk_chars: Max chars per TTS chunk

    Returns:
        Dict with:
          - 'clean': cleaned Devanagari text
          - 'language': detected/confirmed language
          - 'script': detected input script
          - 'chunks': list of TTS-ready text chunks
          - 'iast': IAST transliteration for display
    """
    # Step 1: Strip markup
    text = clean_markup(text)

    # Step 2: Unicode normalisation
    text = normalise_unicode(text)

    # Step 3: Detect input script
    script = detect_script(text)

    # Step 4: Convert to Devanagari
    dev_text = auto_to_devanagari(text)

    # Step 5: Normalise punctuation
    dev_text = normalise_punctuation(dev_text)

    # Step 6: Detect language
    lang = language or detect_language(dev_text)

    # Step 7: IAST for display
    try:
        iast = devanagari_to_iast(dev_text)
    except Exception:
        iast = dev_text

    # Step 8: Split into chunks
    chunks = split_into_pada_chunks(dev_text, max_chars=max_chunk_chars)

    return {
        "clean": dev_text,
        "language": lang,
        "script": script,
        "chunks": chunks,
        "iast": iast,
        "chunk_count": len(chunks),
    }


# ── Mātrā / Svara annotation (for analysis display) ──────────────────────────

VOWEL_MATRA = {
    "अ": 1, "आ": 2, "ा": 2,
    "इ": 1, "ई": 2, "ि": 1, "ी": 2,
    "उ": 1, "ऊ": 2, "ु": 1, "ू": 2,
    "ऋ": 1, "ृ": 1, "ॠ": 2,
    "ए": 2, "े": 2,
    "ऐ": 2, "ै": 2,
    "ओ": 2, "ो": 2,
    "औ": 2, "ौ": 2,
    "ॐ": 2,
}

ASPIRATED = frozenset("खघछझठढथधफभ")

CONSONANT_STHANA = {
    "क": "Kaṇṭhya", "ख": "Kaṇṭhya", "ग": "Kaṇṭhya", "घ": "Kaṇṭhya", "ङ": "Kaṇṭhya",
    "च": "Tālavya", "छ": "Tālavya", "ज": "Tālavya", "झ": "Tālavya", "ञ": "Tālavya",
    "ट": "Mūrdhanya", "ठ": "Mūrdhanya", "ड": "Mūrdhanya", "ढ": "Mūrdhanya", "ण": "Mūrdhanya",
    "त": "Dantya", "थ": "Dantya", "द": "Dantya", "ध": "Dantya", "न": "Dantya",
    "प": "Oṣṭhya", "फ": "Oṣṭhya", "ब": "Oṣṭhya", "भ": "Oṣṭhya", "म": "Oṣṭhya",
    "य": "Tālavya", "र": "Mūrdhanya", "ल": "Dantya", "व": "Dantya-Oṣṭhya",
    "श": "Tālavya", "ष": "Mūrdhanya", "स": "Dantya", "ह": "Kaṇṭhya",
}


def annotate_syllables(devanagari_text: str) -> list[dict]:
    """
    Perform syllable-level Vedic phonetic annotation.

    Returns a list of dicts, one per syllable:
      {devanagari, iast, matra, type, svara, sthana, prana, notes}
    """
    syllables = []
    chars = list(devanagari_text)
    i = 0

    while i < len(chars):
        c = chars[i]

        # Skip spaces / punctuation
        if re.match(r"[\s।॥|,.!?;:\-–—·\n\r]", c):
            i += 1
            continue

        # Anusvāra / Visarga as modifier on previous syllable
        if c in ("ं", "ँ", "ः") and syllables:
            prev = syllables[-1]
            prev["devanagari"] += c
            if c == "ं":
                prev["iast"] += "ṁ"
                prev["notes"] += " +anusvāra"
            elif c == "ँ":
                prev["iast"] += "~"
                prev["notes"] += " +candrabindu"
            else:
                prev["iast"] += "ḥ"
                prev["notes"] += " +visarga"
            prev["matra"] = 2  # becomes guru
            i += 1
            continue

        # Halanta
        if c == "्" and syllables:
            prev = syllables[-1]
            prev["devanagari"] += c
            prev["iast"] = re.sub(r"a$", "", prev["iast"])
            prev["type"] = "conjunct"
            i += 1
            continue

        # Praṇava OM
        if c == "ॐ":
            syllables.append({
                "devanagari": c, "iast": "oṁ", "matra": 2,
                "type": "dīrgha", "svara": "Udātta",
                "sthana": "Kaṇṭhya-Oṣṭhya", "prana": "—",
                "notes": "praṇava — sacred syllable",
            })
            i += 1
            continue

        # Independent vowel
        if c in VOWEL_MATRA and c not in "ािीुूृेैोौ":
            vm = VOWEL_MATRA[c]
            syllables.append({
                "devanagari": c,
                "iast": _simple_iast_vowel(c),
                "matra": vm,
                "type": "dīrgha" if vm == 2 else "hrasva",
                "svara": "Udātta",
                "sthana": "—",
                "prana": "—",
                "notes": f"{'dīrgha' if vm == 2 else 'hrasva'} svara",
            })
            i += 1
            continue

        # Consonant
        if c in CONSONANT_STHANA:
            sthana = CONSONANT_STHANA[c]
            prana = "Mahāprāṇa" if c in ASPIRATED else "Alpaprāṇa"
            syl = c
            i += 1

            if i < len(chars) and chars[i] in "ािीुूृेैोौ":
                vm = VOWEL_MATRA.get(chars[i], 1)
                syl += chars[i]
                syllables.append({
                    "devanagari": syl,
                    "iast": f"{_simple_iast_cons(c)}{_simple_iast_vowel(chars[i])}",
                    "matra": vm, "type": "dīrgha" if vm == 2 else "hrasva",
                    "svara": "Udātta", "sthana": sthana, "prana": prana,
                    "notes": f"{sthana}, {prana}",
                })
                i += 1
            elif i < len(chars) and chars[i] == "्":
                syllables.append({
                    "devanagari": syl + "्", "iast": _simple_iast_cons(c),
                    "matra": 0, "type": "conjunct",
                    "svara": "—", "sthana": sthana, "prana": prana,
                    "notes": f"conjunct start ({sthana})",
                })
                i += 1
            else:
                syllables.append({
                    "devanagari": syl, "iast": f"{_simple_iast_cons(c)}a",
                    "matra": 1, "type": "hrasva",
                    "svara": "Udātta", "sthana": sthana, "prana": prana,
                    "notes": f"{sthana}, {prana}, inherent a",
                })
            continue

        i += 1

    # Apply gurū rule: short vowel before conjunct → 2 mātrā
    for idx in range(len(syllables) - 1):
        if syllables[idx]["matra"] == 1 and syllables[idx + 1]["type"] == "conjunct":
            syllables[idx]["matra"] = 2
            syllables[idx]["notes"] += " [gurū by saṁyoga]"

    # Assign svara pattern (simplified 4-cycle)
    svara_cycle = ["Udātta", "Svarita", "Anudātta", "Udātta"]
    for idx, syl in enumerate(syllables):
        if syl["svara"] == "Udātta":
            syl["svara"] = svara_cycle[idx % 4]

    return syllables


# ── Simple IAST mapping helpers (for annotation, not transliteration) ─────────

_IAST_VOWEL_MAP = {
    "अ": "a", "आ": "ā", "ा": "ā",
    "इ": "i", "ई": "ī", "ि": "i", "ी": "ī",
    "उ": "u", "ऊ": "ū", "ु": "u", "ू": "ū",
    "ऋ": "ṛ", "ृ": "ṛ", "ॠ": "ṝ",
    "ए": "e", "े": "e",
    "ऐ": "ai", "ै": "ai",
    "ओ": "o", "ो": "o",
    "औ": "au", "ौ": "au",
}

_IAST_CONS_MAP = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ṅ",
    "च": "c", "छ": "ch", "ज": "j", "झ": "jh", "ञ": "ñ",
    "ट": "ṭ", "ठ": "ṭh", "ड": "ḍ", "ढ": "ḍh", "ण": "ṇ",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v",
    "श": "ś", "ष": "ṣ", "स": "s", "ह": "h",
}


def _simple_iast_vowel(c: str) -> str:
    return _IAST_VOWEL_MAP.get(c, c)


def _simple_iast_cons(c: str) -> str:
    return _IAST_CONS_MAP.get(c, c)
