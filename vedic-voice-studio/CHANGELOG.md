# Changelog — Vedic Voice Studio

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.2.0] — 2026-10-21

### Added

#### Voice Engines
- **IndicF5 backend** (`indicf5_backend.py`) — AI4Bharat's F5-TTS model trained on 1,400+ hours of Indian speech, supporting 11 Indian languages with zero-shot voice cloning
- **XTTS v2 backend** (`xtts_backend.py`) — Coqui's multilingual 17-language voice cloning engine with native Hindi support
- **Engine selector UI** — 4-engine panel (IndicF5 / XTTS v2 / Chatterbox / LuxTTS) with engine-specific descriptions and auto-switching
- **Engine-aware language mapping** — `getApiLanguage()` sends correct language codes per engine (IndicF5 accepts `sa` directly; XTTS/Chatterbox map `sa`→`hi`; LuxTTS sends `en`)

#### Backend Infrastructure
- **12 Indic language codes** added to `LANGUAGE_CODE_TO_NAME`: hi, sa, bn, gu, mr, pa, ta, te, kn, ml, or, as
- **Indic model configs** — `_get_indic_tts_configs()` returns ModelConfig for IndicF5 and XTTS v2
- **Backend factory** — `get_tts_backend_for_engine()` handles `indicf5` and `xtts` engine types
- **IndicF5 text preprocessor** — Unicode NFC, IAST→Devanagari auto-transliteration, danda normalization
- **XTTS text preprocessor** — Same pipeline adapted for Coqui TTS input format

#### Sanskrit/Hindi Text Processing
- **`indic_text.py`** utility module with:
  - Script detection (Devanagari/IAST/Latin/mixed)
  - Language detection (Sanskrit vs Hindi heuristics)
  - IAST ↔ Devanagari ↔ ITRANS transliteration
  - Sandhi-aware pāda chunking for TTS
  - Syllable-level mātrā/svara/sthāna annotation
  - Gurū-by-saṁyoga rule
  - 35-consonant articulatory position map
  - Praṇava (OM) handling

#### Scripts
- **`install.sh`** — Installs f5-tts, coqui-tts, indic-transliteration into Voicebox venv
- **`start.sh`** — Starts Voicebox backend + opens Vedic Voice Studio in browser

### Changed
- Default engine changed from `luxtts` to `indicf5`
- `MAX_CHUNK_CHARS` reduced from 500 to 400 (better for Indic scripts)
- Profile creation uses engine-aware language code instead of hardcoded `en`/`hi`
- Model warm-up works for all engines (was hardcoded to LuxTTS only)
- Language selector events scoped to `#langRow` to avoid conflicts with engine selector

### Fixed
- Shell scripts properly quote paths with spaces ("audio editor")

---

## [0.1.0] — 2026-10-21

### Added

#### Frontend Application
- Complete single-file web application (`index.html`) with 5-step workflow
- Saffron/gold/dark glassmorphism design theme
- Google Fonts integration (Inter + Noto Sans Devanagari)
- Responsive layout for desktop and mobile

#### Voice Cloning
- Reference audio upload via drag-and-drop or click
- Automatic best-segment extraction for recordings > 30 seconds
- Voice profile creation and management via Voicebox API
- LuxTTS (ZipVoice) 48 kHz voice cloning engine support
- Generation progress tracking via Server-Sent Events (SSE)
- Audio playback and WAV download

#### Language Support
- Sanskrit (संस्कृतम्) — primary language
- Hindi (हिन्दी) — secondary language
- Script toggle: Devanāgarī / IAST / Roman
- Full Devanāgarī text input with Noto Sans Devanagari typography

#### Indian Classical Music Parameters
- 10 Rāga selections (Bhairavī, Yaman, Bhairav, Mālkauṃs, Darbārī, Toḍī, Kāfī, Bāgeśrī, Desh, Khamāj)
- 9 Chhandas meter options (Gāyatrī through Mandākrāntā + Free/Prose)
- 7 Tāla rhythm cycle options (Tīntāl through Kēharvā + Free)
- 3 Tempo/Laya modes (Vilambit, Madhya, Drut)

#### Vedic Phonetic Analysis Engine
- Client-side Devanāgarī syllable decomposition
- Mātrā (beat duration) calculation with Gurū rule
- Svara (3-tone pitch) annotation
- Sthāna (articulatory position) classification for consonants
- Prāṇa (aspiration class) identification
- Chhandas meter identification with syllable/mātrā counts
- Vocal warnings and execution tips panel

#### System Prompts
- `system_prompts/music_composer.md` — AI Indian Classical Music composition spec
- `system_prompts/vedic_phonetics.md` — Vedic phonetics scholar spec

#### Documentation
- `README.md`, `PROJECT_HANDOFF.md`, `ARCHITECTURE.md`
- `RAGA_REFERENCE.md`, `CHHANDAS_REFERENCE.md`, `VEDIC_PHONETICS_GUIDE.md`
- `CONTRIBUTING.md`, `CHANGELOG.md`

---

## [Unreleased]

### Planned
- Browser microphone recording
- Indian Classical Music composition engine
- Sāma Veda 7-svara mode
- Full Sandhi detection and annotation
- Audio examples for each Rāga
