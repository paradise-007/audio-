# Architecture — Vedic Voice Studio

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    VEDIC VOICE STUDIO                           │
│                    (Browser Application)                        │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    index.html                              │  │
│  │                                                            │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐  │  │
│  │  │ UI Layer    │  │ Phonetics   │  │ Music Params     │  │  │
│  │  │             │  │ Engine      │  │ Selector         │  │  │
│  │  │ • Audio     │  │             │  │                  │  │  │
│  │  │   Upload    │  │ • Mātrā     │  │ • Rāga (10)     │  │  │
│  │  │ • Text      │  │ • Svara     │  │ • Chhand (9)    │  │  │
│  │  │   Input     │  │ • Sthāna    │  │ • Tāla (7)      │  │  │
│  │  │ • Engine    │  │ • Prāṇa     │  │ • Tempo (3)     │  │  │
│  │  │   Selector  │  │ • Chhandas  │  │                  │  │  │
│  │  │ • Output    │  │   Analysis  │  │                  │  │  │
│  │  │   Player    │  │             │  │                  │  │  │
│  │  └──────┬──────┘  └─────────────┘  └──────────────────┘  │  │
│  │         │                                                  │  │
│  │  ┌──────┴──────────────────────────────────────────────┐  │  │
│  │  │              API Client Layer                        │  │  │
│  │  │  fetch() + EventSource (SSE)                        │  │  │
│  │  └──────┬──────────────────────────────────────────────┘  │  │
│  └─────────┼──────────────────────────────────────────────────┘  │
└────────────┼────────────────────────────────────────────────────┘
             │ HTTP REST + SSE
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VOICEBOX BACKEND                             │
│                    FastAPI · Python 3.12                        │
│                    http://127.0.0.1:8000                        │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐  ┌──────────┐ │
│  │ Routes   │  │ Services │  │ TTS Backends   │  │ Database │ │
│  │          │  │          │  │                │  │          │ │
│  │ /health  │  │ profiles │  │ IndicF5 ◀━━━━ │  │ SQLite   │ │
│  │ /profiles│  │ tts      │  │ XTTS v2       │  │ (SQLAlch)│ │
│  │ /generate│  │ history  │  │ Chatterbox    │  │          │ │
│  │ /audio   │  │ settings │  │ LuxTTS        │  │ Profiles │ │
│  │ /models  │  │ llm      │  │ Qwen · Kokoro │  │ Gens     │ │
│  └──────────┘  └──────────┘  └────────────────┘  └──────────┘ │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ PyTorch 2.2+ · HuggingFace Hub · CUDA/MPS              │   │
│  │ indic-transliteration · f5-tts · coqui-tts              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ utils/indic_text.py — Sanskrit/Hindi text preprocessor  │   │
│  │ • Script detection (Devanagari/IAST/Latin)              │   │
│  │ • IAST ↔ Devanagari transliteration                     │   │
│  │ • Sandhi-aware pāda chunking                            │   │
│  │ • Mātrā/Svara syllable annotation                       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Voice Engines

| Engine | Model | Languages | Voice Cloning | Output | VRAM |
|--------|-------|-----------|---------------|--------|------|
| **IndicF5** (primary) | AI4Bharat F5-TTS | 11 Indian (hi,sa,bn,gu,mr,pa,ta,te,kn,ml,or,as) | Zero-shot, 5–15s ref | 24 kHz | ~2 GB |
| **XTTS v2** (backup) | Coqui XTTS-v2 | 17 lang incl. Hindi | Zero-shot, 6s ref | 24 kHz | ~2 GB |
| **Chatterbox** | ResembleAI | 23 lang incl. Hindi | Zero-shot | 24 kHz | ~3 GB |
| **LuxTTS** | ZipVoice | English only | Zero-shot | 48 kHz | CPU |

---

## Component Details

### 1. Engine Selector (new in v0.2)

The frontend includes a 4-engine selector panel:

```javascript
const ENGINE_MODEL = {
  indicf5: 'indicf5',           // AI4Bharat — 11 Indian languages
  xtts: 'xtts-v2',             // Coqui — 17 languages incl. Hindi
  chatterbox: 'chatterbox-tts', // ResembleAI — 23 languages
  luxtts: 'luxtts',            // ZipVoice — English only
};
```

Language codes are mapped per-engine via `getApiLanguage()`:
- **IndicF5**: passes `sa` / `hi` directly (native support)
- **XTTS v2**: maps Sanskrit → Hindi (`sa` → `hi`)
- **Chatterbox**: maps Sanskrit → Hindi
- **LuxTTS**: always sends `en`

### 2. UI Layer (`index.html` — HTML/CSS)

The interface follows a 5-step workflow:

| Step | Component | Description |
|------|-----------|-------------|
| 0 | Engine Selector | Choose between IndicF5, XTTS v2, Chatterbox, LuxTTS |
| 1 | Reference Audio | Drag-drop upload with auto-segment extraction |
| 2 | Lyrics / Text | Devanāgarī textarea with language/script toggles |
| 3 | Musical Parameters | Tabbed: Composition (Rāga/Chhand/Tāla) + Phonetics |
| 4 | Generate | Trigger button with progress bar and SSE status |
| 5 | Output | Audio player with WAV download |

**Design System:**
- Color palette: Saffron (#e87a24), Gold (#d4a843), Maroon (#8b1a1a) on dark (#0c0a10)
- Typography: Inter (Latin) + Noto Sans Devanagari (Indic)
- CSS custom properties for full theme consistency

### 3. Backend: IndicF5 (`indicf5_backend.py`)

```
Input: Devanagari text + reference audio
  │
  ├── preprocess_indic_text()
  │   ├── Unicode NFC normalization
  │   ├── Strip HTML/Markdown
  │   ├── Detect IAST → transliterate to Devanagari
  │   └── Replace dandas with periods
  │
  ├── create_voice_prompt()
  │   ├── Load + trim reference audio to 10s
  │   ├── Get transcript via Whisper (if no ref_text)
  │   └── Cache voice prompt
  │
  └── generate()
      ├── Remap Sanskrit → Hindi
      ├── Preprocess text
      ├── Call IndicF5 model(text, ref_audio, ref_text)
      └── Output: float32 numpy array @ 24kHz
```

### 4. Backend: XTTS v2 (`xtts_backend.py`)

```
Input: text + reference audio
  │
  ├── _preprocess_for_xtts()
  │   └── Same pipeline as IndicF5
  │
  ├── create_voice_prompt()
  │   └── Trim reference to 15s, cache
  │
  └── generate()
      ├── Remap unsupported languages
      └── Call tts.tts_to_file() → read WAV → return numpy
```

### 5. Backend: indic_text.py (utility)

Server-side Sanskrit/Hindi text processing:

```
Input: any script text
  │
  ├── detect_script()     → 'devanagari' | 'iast' | 'latin' | 'mixed'
  ├── detect_language()   → 'sa' | 'hi'
  ├── auto_to_devanagari() → IAST/ITRANS → Devanagari
  ├── normalise_punctuation() → dandas → periods
  ├── split_into_pada_chunks() → Sandhi-aware chunking
  └── annotate_syllables() → mātrā, svara, sthāna, prāṇa
```

### 6. Vedic Phonetics Engine (client-side JS)

```
Input: Devanāgarī text string
  │
  ├── Character iteration
  │   ├── Independent vowels → mātrā + type lookup
  │   ├── Consonants → sthāna + prāṇa classification
  │   ├── Mātrā signs (ा ि ी ु ू etc.) → duration assignment
  │   ├── Anusvāra (ं), Visarga (ः) → modifier on previous
  │   └── Halanta (्) → suppress inherent 'a'
  │
  ├── Gurū rule application
  │   └── Short vowel + following conjunct → 2 mātrā
  │
  ├── Svara pattern assignment
  │   └── 4-cycle: Udātta → Svarita → Anudātta → Udātta
  │
  └── Output: Array of syllable objects
      └── { devanagari, iast, matra, type, svara, sthana, prana, notes }
```

---

## Data Flow: Voice Generation

```
1. User selects engine (IndicF5 recommended)
   │
2. User uploads reference audio (WAV/MP3)
   │
3. Browser extracts best 12s segment (if > 30s)
   │  └── RMS energy analysis → loudest speech window
   │
4. POST /profiles → create "Vedic Voice Session" profile
   │
5. POST /profiles/{id}/samples → upload reference WAV
   │
6. User enters Sanskrit/Hindi text + selects musical params
   │
7. POST /generate → {profile_id, text, engine: "indicf5", language: "sa"}
   │
8. Backend (IndicF5):
   │  ├── Download model from HuggingFace (~1.2 GB, first time)
   │  ├── Load IndicF5 on CUDA/CPU
   │  ├── Encode reference audio → speaker embedding
   │  ├── Preprocess Devanagari text
   │  ├── Chunk text → 400 char segments
   │  ├── Generate audio per chunk
   │  └── Crossfade + concatenate → final WAV
   │
9. SSE /generate/{id}/status → poll until "completed"
   │
10. GET /audio/{id} → stream 24kHz WAV to browser
```

---

## File Map

### Vedic Voice Studio

| File | Purpose |
|------|---------|
| `index.html` | Complete single-file web application |
| `install.sh` | Dependency installer script |
| `start.sh` | Backend startup + browser open |
| `system_prompts/music_composer.md` | AI music composition spec |
| `system_prompts/vedic_phonetics.md` | Vedic phonetics spec |
| `README.md` | Project overview |
| `PROJECT_HANDOFF.md` | AI agent handoff |
| `ARCHITECTURE.md` | This file |
| `RAGA_REFERENCE.md` | 10 Rāgas documented |
| `CHHANDAS_REFERENCE.md` | 9 Sanskrit meters |
| `VEDIC_PHONETICS_GUIDE.md` | Phonetics guide |
| `CONTRIBUTING.md` | Contribution guidelines |
| `CHANGELOG.md` | Version history |

### Backend Files (in `../voicebox/backend/`)

| File | Purpose |
|------|---------|
| `backends/indicf5_backend.py` | IndicF5 voice cloning engine |
| `backends/xtts_backend.py` | XTTS v2 voice cloning engine |
| `backends/__init__.py` | Engine registry (12 Indic lang codes + 2 new engines) |
| `utils/indic_text.py` | Sanskrit/Hindi text preprocessor |
